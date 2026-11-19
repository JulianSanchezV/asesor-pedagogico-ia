import re
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.auth import get_current_user, require_teacher
from app.database import get_db
from app.models import Cohort, Evaluation, EvaluationAuditLog, Lab, RubricVersion, Submission, User
from app.schemas import CohortOut, LabCreate, LabOut, LabUpdate
from app.services.ai_provider import call_structured_llm, get_active_ai_config
from app.services.document_parser import extract_document_content

router = APIRouter(prefix="/api/labs", tags=["Cohortes y Laboratorios"])


class ParsedLabDraft(BaseModel):
    code: str = Field(..., description="Código sugerido corto para el laboratorio, ej. LAB-1.1")
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=15, description="Resumen técnico claro del laboratorio y sus entregables")
    objectives: list[str] = Field(default_factory=list, description="Lista de 2 a 5 objetivos de aprendizaje concretos")
    ai_topics: list[str] = Field(default_factory=list, description="Lista de 2 a 5 temáticas/conceptos de IA abordados")


def _serialize_lab(lab: Lab) -> LabOut:
    active_rubric = next((r for r in lab.rubrics if r.is_active), None)
    return LabOut(
        id=lab.id,
        cohort_id=lab.cohort_id,
        cohort_number=lab.cohort.number if lab.cohort else None,
        code=lab.code,
        title=lab.title,
        description=lab.description,
        objectives=lab.objectives or [],
        ai_topics=lab.ai_topics or [],
        active_rubric_id=active_rubric.id if active_rubric else None,
        active_rubric_version=active_rubric.version_number if active_rubric else None,
        created_at=lab.created_at,
    )


@router.get("/cohorts", response_model=list[CohortOut])
def list_cohorts(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Cohort).order_by(Cohort.number.asc()).all()


@router.get("", response_model=list[LabOut])
def list_labs(
    cohort_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(Lab)
    if cohort_id:
        q = q.filter(Lab.cohort_id == cohort_id)
    labs = q.order_by(Lab.cohort_id.asc(), Lab.code.asc()).all()
    return [_serialize_lab(lab) for lab in labs]


@router.get("/{lab_id}", response_model=LabOut)
def get_lab(lab_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    lab = db.query(Lab).filter(Lab.id == lab_id).first()
    if not lab:
        raise HTTPException(status_code=404, detail="Laboratorio no encontrado.")
    return _serialize_lab(lab)


@router.post("", response_model=LabOut, status_code=status.HTTP_201_CREATED)
def create_lab(
    payload: LabCreate,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
):
    cohort = db.query(Cohort).filter(Cohort.id == payload.cohort_id).first()
    if not cohort:
        raise HTTPException(status_code=404, detail="Cohorte no encontrada.")
    if db.query(Lab).filter(Lab.code == payload.code.strip()).first():
        raise HTTPException(status_code=400, detail=f"Ya existe un laboratorio con código {payload.code}.")

    lab = Lab(
        cohort_id=payload.cohort_id,
        code=payload.code.strip().upper(),
        title=payload.title.strip(),
        description=payload.description.strip(),
        objectives=[o.strip() for o in payload.objectives if o.strip()],
        ai_topics=[t.strip() for t in payload.ai_topics if t.strip()],
        created_by=teacher.id,
    )
    db.add(lab)
    db.commit()
    db.refresh(lab)
    return _serialize_lab(lab)


@router.put("/{lab_id}", response_model=LabOut)
def update_lab(
    lab_id: int,
    payload: LabUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    lab = db.query(Lab).filter(Lab.id == lab_id).first()
    if not lab:
        raise HTTPException(status_code=404, detail="Laboratorio no encontrado.")

    if payload.title is not None:
        lab.title = payload.title.strip()
    if payload.description is not None:
        lab.description = payload.description.strip()
    if payload.objectives is not None:
        lab.objectives = [o.strip() for o in payload.objectives if o.strip()]
    if payload.ai_topics is not None:
        lab.ai_topics = [t.strip() for t in payload.ai_topics if t.strip()]

    db.commit()
    db.refresh(lab)
    return _serialize_lab(lab)


@router.delete("/{lab_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lab(
    lab_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    lab = db.query(Lab).filter(Lab.id == lab_id).first()
    if not lab:
        raise HTTPException(status_code=404, detail="Laboratorio no encontrado.")

    # Delete dependent records in explicit FK-safe order (SQLite & PostgreSQL)
    sub_ids = [s.id for s in db.query(Submission.id).filter(Submission.lab_id == lab_id).all()]
    if sub_ids:
        eval_ids = [e.id for e in db.query(Evaluation.id).filter(Evaluation.submission_id.in_(sub_ids)).all()]
        if eval_ids:
            db.query(EvaluationAuditLog).filter(EvaluationAuditLog.evaluation_id.in_(eval_ids)).delete(synchronize_session=False)
            db.query(Evaluation).filter(Evaluation.id.in_(eval_ids)).delete(synchronize_session=False)
        db.query(Submission).filter(Submission.id.in_(sub_ids)).delete(synchronize_session=False)

    db.query(RubricVersion).filter(RubricVersion.lab_id == lab_id).delete(synchronize_session=False)
    db.delete(lab)
    db.commit()
    return None


def _fallback_parse_lab_document(text: str, filename: str, cohort_number: int, next_seq: int) -> ParsedLabDraft:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    base_name = re.sub(r"\.[^.]+$", "", filename or "Laboratorio").replace("_", " ").replace("-", " ").strip()
    title = lines[0][:140] if lines and 6 <= len(lines[0]) <= 140 else (base_name or f"Laboratorio Cohorte {cohort_number}")

    # Extract bullet/numbered objectives if present
    objectives = []
    for ln in lines:
        if re.match(r"^([\-\•\*]|\d+[\.\)])\s+.{12,}", ln):
            cleaned = re.sub(r"^([\-\•\*]|\d+[\.\)])\s+", "", ln).strip()
            if cleaned not in objectives:
                objectives.append(cleaned[:180])
        if len(objectives) >= 4:
            break
    if not objectives:
        objectives = [
            f"Comprender y aplicar los fundamentos de {title}.",
            "Implementar la solución práctica con código verificable y pruebas.",
            "Documentar resultados, métricas y conclusiones en el informe técnico.",
        ]

    # Simple AI keyword detector for topics
    keyword_topics = [
        ("búsqueda", "Búsqueda Heurística"),
        ("a*", "Algoritmo A*"),
        ("regresión", "Regresión y Modelado Predictivo"),
        ("clasific", "Clasificación Supervisada"),
        ("clustering", "Aprendizaje No Supervisado"),
        ("red neuronal", "Redes Neuronales"),
        ("redes neuronales", "Redes Neuronales"),
        ("deep learning", "Deep Learning"),
        ("cnn", "Visión Artificial (CNN)"),
        ("visión", "Visión Artificial"),
        ("nlp", "Procesamiento de Lenguaje Natural (NLP)"),
        ("lenguaje natural", "Procesamiento de Lenguaje Natural (NLP)"),
        ("llm", "Modelos de Lenguaje (LLMs)"),
        ("rag", "Retrieval-Augmented Generation (RAG)"),
        ("agente", "Agentes Inteligentes"),
        ("árbol", "Árboles de Decisión"),
        ("random forest", "Ensambles y Random Forest"),
        ("svm", "Máquinas de Vectores de Soporte (SVM)"),
        ("prompt", "Ingeniería de Prompts"),
    ]
    lower_text = text.lower()
    detected_topics = []
    for kw, label in keyword_topics:
        if kw in lower_text and label not in detected_topics:
            detected_topics.append(label)
        if len(detected_topics) >= 4:
            break
    if not detected_topics:
        detected_topics = ["Inteligencia Artificial Aplicada", "Análisis y Modelado"]

    description_snippet = " ".join(lines[:8])[:650]
    if len(description_snippet) < 20:
        description_snippet = f"Laboratorio práctico basado en el documento '{filename}'."

    return ParsedLabDraft(
        code=f"LAB-{cohort_number}.{next_seq}",
        title=title,
        description=description_snippet,
        objectives=objectives,
        ai_topics=detected_topics,
    )


@router.post("/parse-document")
async def parse_lab_from_document(
    file: UploadFile = File(...),
    cohort_id: int = Form(1),
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    """
    Upload a lab guide document (.pdf, .docx, .txt, .md) and analyze it with the configured AI
    to automatically extract code, title, description, learning objectives, and AI topics.
    """
    cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
    cohort_number = cohort.number if cohort else 1
    existing_count = db.query(Lab).filter(Lab.cohort_id == cohort_id).count()
    next_seq = existing_count + 1

    data = await file.read()
    if len(data) < 20:
        raise HTTPException(status_code=400, detail="El archivo cargado está vacío.")

    try:
        doc_info = extract_document_content(data, file.filename or "documento.pdf", max_images=2)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo leer el documento: {exc}")

    if not doc_info["is_readable"]:
        raise HTTPException(
            status_code=400,
            detail="El documento no contiene suficiente texto legible (evita PDFs escaneados solo como imagen).",
        )

    ai_cfg = get_active_ai_config(db)
    parsed_by = "extractor-local"
    draft: ParsedLabDraft

    if ai_cfg["has_api_key"]:
        sys_prompt = (
            "Eres un experto en diseño curricular universitario de Inteligencia Artificial. "
            "Analiza la guía de laboratorio suministrada y extrae de forma precisa y en español:\n"
            f"- code: usa '{f'LAB-{cohort_number}.{next_seq}'}' o el código oficial si aparece en el documento.\n"
            "- title: título claro y conciso del laboratorio.\n"
            "- description: síntesis técnica clara (2 a 4 oraciones) de qué debe hacer el estudiante.\n"
            "- objectives: lista de 2 a 5 objetivos de aprendizaje concretos.\n"
            "- ai_topics: lista de 2 a 5 temáticas/conceptos clave de Inteligencia Artificial abordados."
        )
        usr_prompt = f"Archivo: {file.filename}\nCohorte: {cohort_number}\n\nContenido extraído:\n{doc_info['text'][:16000]}"
        try:
            draft, _ = call_structured_llm(
                config=ai_cfg,
                system_prompt=sys_prompt,
                user_prompt=usr_prompt,
                response_schema=ParsedLabDraft,
                images=doc_info["extracted_images"] if ai_cfg["provider"] == "gemini" else None,
            )
            parsed_by = f"{ai_cfg['provider']}/{ai_cfg['model_name']}"
        except Exception:
            draft = _fallback_parse_lab_document(doc_info["text"], file.filename or "", cohort_number, next_seq)
    else:
        draft = _fallback_parse_lab_document(doc_info["text"], file.filename or "", cohort_number, next_seq)

    # Ensure unique code suggestion
    candidate_code = draft.code.strip().upper()
    if db.query(Lab).filter(Lab.code == candidate_code).first():
        candidate_code = f"LAB-{cohort_number}.{next_seq}"
        while db.query(Lab).filter(Lab.code == candidate_code).first():
            next_seq += 1
            candidate_code = f"LAB-{cohort_number}.{next_seq}"
    draft.code = candidate_code

    return {
        "parsed_by": parsed_by,
        "filename": file.filename,
        "format": doc_info["format"],
        "word_count": len(doc_info["text"].split()),
        "draft": draft.model_dump(),
    }
