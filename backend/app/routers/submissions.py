import re
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.database import get_db
from app.models import Evaluation, EvaluationAuditLog, Lab, RubricVersion, Submission, User
from app.schemas import SubmissionOut
from app.services.document_parser import extract_document_content
from app.services.storage import load_bytes, save_bytes

router = APIRouter(prefix="/api/submissions", tags=["Portafolio Académico y Entregas"])


def _serialize_submission(sub: Submission) -> SubmissionOut:
    latest_eval = sub.evaluations[0] if sub.evaluations else None
    return SubmissionOut(
        id=sub.id,
        student_id=sub.student_id,
        student_name=sub.student.full_name if sub.student else None,
        lab_id=sub.lab_id,
        lab_code=sub.lab.code if sub.lab else None,
        lab_title=sub.lab.title if sub.lab else None,
        cohort_number=sub.lab.cohort.number if (sub.lab and sub.lab.cohort) else None,
        rubric_version_id=sub.rubric_version_id,
        rubric_version_number=sub.rubric_version.version_number if sub.rubric_version else None,
        pdf_filename=sub.pdf_filename,
        pdf_page_count=sub.pdf_page_count,
        pdf_image_count=sub.pdf_image_count,
        code_source_type=sub.code_source_type,
        code_filename=sub.code_filename,
        github_url=sub.github_url,
        optional_media_url=sub.optional_media_url,
        optional_media_notes=sub.optional_media_notes,
        status=sub.status,
        latest_evaluation_id=latest_eval.id if latest_eval else None,
        latest_grade=latest_eval.final_grade if latest_eval else None,
        latest_eval_status=latest_eval.status if latest_eval else None,
        created_at=sub.created_at,
    )


@router.get("", response_model=list[SubmissionOut])
def list_submissions(
    cohort_number: int | None = None,
    lab_id: int | None = None,
    student_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Submission)
    if current_user.role == "student":
        q = q.filter(Submission.student_id == current_user.id)
    elif student_id:
        q = q.filter(Submission.student_id == student_id)

    if lab_id:
        q = q.filter(Submission.lab_id == lab_id)

    items = q.order_by(Submission.created_at.desc()).all()
    if cohort_number:
        items = [s for s in items if s.lab and s.lab.cohort and s.lab.cohort.number == cohort_number]

    return [_serialize_submission(s) for s in items]


@router.post("", response_model=SubmissionOut, status_code=status.HTTP_201_CREATED)
async def create_submission(
    lab_id: int = Form(...),
    rubric_version_id: int | None = Form(None),
    code_source_type: str = Form("none"),  # none | zip | github
    github_url: str | None = Form(None),
    optional_media_url: str | None = Form(None),
    optional_media_notes: str | None = Form(None),
    pdf_file: UploadFile = File(...),
    code_zip: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lab = db.query(Lab).filter(Lab.id == lab_id).first()
    if not lab:
        raise HTTPException(status_code=404, detail="Laboratorio no encontrado.")

    # Resolve rubric version (specific or active) and enforce 100% weight check
    if rubric_version_id:
        rubric = db.query(RubricVersion).filter(
            RubricVersion.id == rubric_version_id, RubricVersion.lab_id == lab_id
        ).first()
    else:
        rubric = db.query(RubricVersion).filter(
            RubricVersion.lab_id == lab_id, RubricVersion.is_active.is_(True)
        ).first()

    if not rubric:
        raise HTTPException(
            status_code=400,
            detail="Este laboratorio no tiene una rúbrica válida configurada. Crea y valida la rúbrica primero.",
        )
    if abs(rubric.total_weight - 100.0) > 0.01:
        raise HTTPException(
            status_code=400,
            detail="La rúbrica seleccionada tiene inconsistencias en sus ponderaciones (no suma 100%).",
        )

    # Validate readable report document (.pdf preferred, also supports .docx/.txt/.md)
    pdf_bytes = await pdf_file.read()
    if len(pdf_bytes) < 50:
        raise HTTPException(status_code=400, detail="El archivo de informe está vacío o corrupto.")

    try:
        pdf_info = extract_document_content(pdf_bytes, pdf_file.filename or "informe.pdf", max_images=0)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo leer el documento entregado: {exc}")

    if not pdf_info["is_readable"]:
        raise HTTPException(
            status_code=400,
            detail="El documento no contiene texto legible (evita PDFs escaneados como imagen sin OCR).",
        )

    # Optional code source (none, ZIP, or GitHub URL)
    code_source_type = (code_source_type or "none").lower().strip()
    code_storage_path = None
    code_filename = None
    clean_github_url = None

    if code_source_type == "zip":
        if code_zip and code_zip.filename:
            if not code_zip.filename.lower().endswith(".zip"):
                raise HTTPException(status_code=400, detail="El archivo de código fuente debe tener extensión .zip.")
            zip_bytes = await code_zip.read()
            if len(zip_bytes) > 0:
                code_storage_path = save_bytes(
                    zip_bytes, code_zip.filename, subfolder=f"student_{current_user.id}/lab_{lab_id}"
                )
                code_filename = code_zip.filename
            else:
                code_source_type = "none"
        else:
            code_source_type = "none"
    elif code_source_type == "github":
        clean_github_url = (github_url or "").strip()
        if clean_github_url:
            if not re.match(r"^https?://github\.com/[^/]+/[^/]+", clean_github_url):
                raise HTTPException(
                    status_code=400,
                    detail="Ingresa una URL de repositorio GitHub válida (https://github.com/usuario/repositorio).",
                )
        else:
            clean_github_url = None
            code_source_type = "none"
    elif code_source_type == "none":
        pass
    else:
        raise HTTPException(status_code=400, detail="code_source_type debe ser 'none', 'zip' o 'github'.")

    pdf_storage_path = save_bytes(
        pdf_bytes, pdf_file.filename, subfolder=f"student_{current_user.id}/lab_{lab_id}"
    )

    sub = Submission(
        student_id=current_user.id,
        lab_id=lab_id,
        rubric_version_id=rubric.id,
        pdf_filename=pdf_file.filename,
        pdf_storage_path=pdf_storage_path,
        pdf_extracted_text=pdf_info["text"][:30000],
        pdf_page_count=pdf_info["page_count"],
        pdf_image_count=pdf_info["image_count"],
        code_source_type=code_source_type,
        code_filename=code_filename,
        code_storage_path=code_storage_path,
        github_url=clean_github_url,
        optional_media_url=(optional_media_url or "").strip() or None,
        optional_media_notes=(optional_media_notes or "").strip() or None,
        status="uploaded",
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return _serialize_submission(sub)


@router.get("/{submission_id}/download/pdf")
def download_submission_pdf(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Entrega no encontrada.")
    if current_user.role == "student" and sub.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permisos para acceder a esta entrega.")

    data = load_bytes(sub.pdf_storage_path)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{sub.pdf_filename}"'},
    )


@router.delete("/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Entrega no encontrada.")
    if current_user.role == "student" and sub.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permisos para eliminar esta entrega.")
    eval_ids = [e.id for e in db.query(Evaluation.id).filter(Evaluation.submission_id == submission_id).all()]
    if eval_ids:
        db.query(EvaluationAuditLog).filter(EvaluationAuditLog.evaluation_id.in_(eval_ids)).delete(synchronize_session=False)
        db.query(Evaluation).filter(Evaluation.id.in_(eval_ids)).delete(synchronize_session=False)
    db.delete(sub)
    db.commit()
    return None
