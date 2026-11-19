from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.services.analytics import build_integrated_report, build_interactive_mind_map
from app.services.pdf_report import generate_integrated_report_pdf

router = APIRouter(prefix="/api/reports", tags=["Informe Integrado y Mapa Mental"])


def _resolve_target_student_id(student_id: int | None, current_user: User, db: Session) -> int:
    if current_user.role == "student":
        return current_user.id
    if student_id:
        return student_id
    first_student = db.query(User).filter(User.role == "student").order_by(User.id.asc()).first()
    if not first_student:
        raise HTTPException(status_code=404, detail="No hay estudiantes registrados todavía.")
    return first_student.id


@router.get("/integrated")
def get_integrated_report(
    student_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target_id = _resolve_target_student_id(student_id, current_user, db)
    try:
        return build_integrated_report(db, target_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/integrated/pdf")
def download_integrated_report_pdf(
    student_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target_id = _resolve_target_student_id(student_id, current_user, db)
    try:
        report = build_integrated_report(db, target_id)
        pdf_bytes = generate_integrated_report_pdf(report)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    safe_name = report["student"]["full_name"].lower().replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="informe_integral_{safe_name}.pdf"'},
    )


@router.get("/mindmap")
def get_mind_map(
    student_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target_id = _resolve_target_student_id(student_id, current_user, db)
    try:
        return build_interactive_mind_map(db, target_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
