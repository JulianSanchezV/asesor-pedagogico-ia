import re
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.auth import get_current_user, require_teacher
from app.database import get_db
from app.models import Lab, RubricVersion, User
from app.schemas import (
    PerformanceLevel,
    RubricCreate,
    RubricCriterion,
    RubricParseRequest,
    RubricValidationResult,
    RubricVersionOut,
)
from app.services.ai_provider import call_structured_llm, get_active_ai_config
from app.services.document_parser import extract_document_content

router = APIRouter(prefix="/api/rubrics", tags=["Gestión y Versionamiento de Rúbricas"])


class ParsedRubricDraft(BaseModel):
    title: str
    criteria: list[RubricCriterion] = Field(..., min_length=1)


def _serialize_rubric(rv: RubricVersion) -> RubricVersionOut:
    return RubricVersionOut(
        id=rv.id,
        lab_id=rv.lab_id,
        version_number=rv.version_number,
        title=rv.title,
        is_active=rv.is_active,
        criteria=[RubricCriterion.model_validate(c) for c in rv.criteria_json],
        total_weight=rv.total_weight,
        created_at=rv.created_at,
    )


@router.get("/lab/{lab_id}", response_model=list[RubricVersionOut])
def list_lab_rubrics(lab_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    versions = (
        db.query(RubricVersion)
        .filter(RubricVersion.lab_id == lab_id)
        .order_by(RubricVersion.version_number.desc())
        .all()
    )
    return [_serialize_rubric(rv) for rv in versions]


@router.post("/validate", response_model=RubricValidationResult)
def validate_rubric_draft(payload: dict, _: User = Depends(get_current_user)):
    """
    Detect inconsistencies in a rubric BEFORE saving or running any evaluation:
    - Weights must sum to 100%
    - Duplicate criterion IDs or invalid levels
    - Missing descriptors
    """
    errors: list[str] = []
    warnings: list[str] = []
    criteria_raw = payload.get("criteria") or []

    if not criteria_raw:
        return RubricValidationResult(
            is_valid=False,
            total_weight=0.0,
            errors=["La rúbrica debe contener al menos un criterio de evaluación."],
        )

    total_weight = 0.0
    seen_ids = set()
    for idx, c in enumerate(criteria_raw, start=1):
        cid = str(c.get("id", "")).strip()
        cname = str(c.get("name", "")).strip()
        comp = str(c.get("competency", "")).strip()
        weight = float(c.get("weight_percent") or 0)
        total_weight += weight

        if not cid:
            errors.append(f"Criterio #{idx}: falta el identificador (id).")
        elif cid in seen_ids:
            errors.append(f"Criterio #{idx}: identificador duplicado '{cid}'.")
        seen_ids.add(cid)

        if len(cname) < 2:
            errors.append(f"Criterio #{idx}: el nombre es obligatorio.")
        if len(comp) < 2:
            errors.append(f"Criterio #{idx}: la competencia asociada es obligatoria.")
        if weight <= 0 or weight > 100:
            errors.append(f"Criterio '{cname or idx}': la ponderación debe ser mayor a 0% y menor o igual a 100%.")

        levels = c.get("levels") or []
        if len(levels) < 2:
            errors.append(f"Criterio '{cname or idx}': debe definir al menos 2 niveles de desempeño.")
        elif len(levels) < 4:
            warnings.append(f"Criterio '{cname or idx}': se recomienda definir los 4 niveles estándar.")

        ratios = [float(lvl.get("score_ratio", -1)) for lvl in levels]
        if any(r < 0 or r > 1 for r in ratios):
            errors.append(f"Criterio '{cname or idx}': los score_ratio deben estar entre 0.0 y 1.0.")

    total_weight = round(total_weight, 2)
    if abs(total_weight - 100.0) > 0.01:
        diff = round(100.0 - total_weight, 2)
        direction = f"faltan {diff}%" if diff > 0 else f"sobran {abs(diff)}%"
        errors.append(
            f"La suma de ponderaciones es {total_weight}% y debe ser exactamente 100% ({direction})."
        )

    return RubricValidationResult(
        is_valid=len(errors) == 0,
        total_weight=total_weight,
        errors=errors,
        warnings=warnings,
    )


@router.post("", response_model=RubricVersionOut, status_code=status.HTTP_201_CREATED)
def create_rubric_version(
    payload: RubricCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new immutable version of a rubric for a lab.
    Pydantic enforces exact 100% total weight before persisting.
    """
    lab = db.query(Lab).filter(Lab.id == payload.lab_id).first()
    if not lab:
        raise HTTPException(status_code=404, detail="Laboratorio no encontrado.")

    latest = (
        db.query(RubricVersion)
        .filter(RubricVersion.lab_id == payload.lab_id)
        .order_by(RubricVersion.version_number.desc())
        .first()
    )
    next_version = (latest.version_number + 1) if latest else 1

    # Deactivate previous active rubrics for this lab while keeping them immutable for traceability
    db.query(RubricVersion).filter(RubricVersion.lab_id == payload.lab_id).update({"is_active": False})

    total_weight = round(sum(c.weight_percent for c in payload.criteria), 2)
    rv = RubricVersion(
        lab_id=payload.lab_id,
        version_number=next_version,
        title=payload.title.strip(),
        is_active=True,
        criteria_json=[c.model_dump() for c in payload.criteria],
        total_weight=total_weight,
        created_by=current_user.id,
    )
    db.add(rv)
    db.commit()
    db.refresh(rv)
    return _serialize_rubric(rv)


def _fallback_parse_rubric_text(raw_text: str, lab_title: str) -> ParsedRubricDraft:
    """Parse plain-text rubric heuristically when no LLM API key is configured."""
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    matches = []
    for ln in lines:
        m = re.search(r"(.+?)[\(\-\:,\s]+(\d+(?:\.\d+)?)\s*%", ln)
        if m:
            name = m.group(1).strip(" -•*:")
            weight = float(m.group(2))
            if name and weight > 0:
                matches.append((name, weight))

    if not matches:
        matches = [
            ("Aplicación conceptual de IA", 40.0),
            ("Implementación y verificación técnica", 35.0),
            ("Análisis y comunicación en informe", 25.0),
        ]

    criteria = []
    for idx, (name, weight) in enumerate(matches, start=1):
        criteria.append(
            RubricCriterion(
                id=f"c{idx}",
                name=name[:140],
                competency=f"Competencia asociada a {name[:90]}",
                weight_percent=round(weight, 2),
                levels=[
                    PerformanceLevel(level="excelente", label="Excelente (4.5 - 5.0)", score_ratio=1.0, descriptor=f"Domina y evidencia de forma sobresaliente: {name}."),
                    PerformanceLevel(level="sobresaliente", label="Sobresaliente (3.8 - 4.4)", score_ratio=0.85, descriptor=f"Aplica correctamente {name} con observaciones menores."),
                    PerformanceLevel(level="aceptable", label="Aceptable (3.0 - 3.7)", score_ratio=0.68, descriptor=f"Cumple parcialmente {name} con brechas identificables."),
                    PerformanceLevel(level="insuficiente", label="Insuficiente (< 3.0)", score_ratio=0.35, descriptor=f"No evidencia dominio suficiente en {name}."),
                ],
            )
        )
    return ParsedRubricDraft(title=f"Rúbrica importada - {lab_title or 'Laboratorio'}", criteria=criteria)


@router.post("/parse")
def parse_rubric_from_text(
    payload: RubricParseRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Interpret a plain-text rubric using configured AI (or structured heuristic fallback) for review & correction."""
    ai_cfg = get_active_ai_config(db)
    draft: ParsedRubricDraft
    parsed_by = "heuristic"

    if ai_cfg["has_api_key"]:
        sys_prompt = (
            "Eres un experto en diseño curricular universitario. Convierte el texto de una rúbrica en un objeto estructurado "
            "con criterios (id c1, c2...), competencia, weight_percent (números positivos) y los 4 niveles "
            "(excelente=1.0, sobresaliente=0.85, aceptable=0.68, insuficiente=0.35). "
            "Respeta las ponderaciones del texto original para que el sistema pueda detectar si no suman 100%."
        )
        usr_prompt = f"Laboratorio: {payload.lab_title}\n\nTexto de la rúbrica:\n{payload.raw_text[:10000]}"
        try:
            draft, _ = call_structured_llm(ai_cfg, sys_prompt, usr_prompt, ParsedRubricDraft)
            parsed_by = f"{ai_cfg['provider']}/{ai_cfg['model_name']}"
        except Exception:
            draft = _fallback_parse_rubric_text(payload.raw_text, payload.lab_title)
    else:
        draft = _fallback_parse_rubric_text(payload.raw_text, payload.lab_title)

    validation = validate_rubric_draft(draft.model_dump())
    return {
        "parsed_by": parsed_by,
        "draft": draft.model_dump(),
        "validation": validation.model_dump(),
    }


@router.post("/parse-pdf")
async def parse_rubric_from_pdf(
    file: UploadFile = File(...),
    lab_title: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = await file.read()
    try:
        extracted = extract_document_content(data, file.filename or "rubrica.pdf", max_images=0)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not extracted["is_readable"]:
        raise HTTPException(status_code=400, detail="El documento de la rúbrica no contiene texto legible.")
    return parse_rubric_from_text(
        RubricParseRequest(raw_text=extracted["text"], lab_title=lab_title),
        db=db,
        _=user,
    )
