from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth import get_current_user, require_teacher
from app.database import get_db
from app.models import Evaluation, EvaluationAuditLog, RubricVersion, Submission, User
from app.schemas import (
    AuditLogOut,
    CompetencyAssessmentAI,
    CriterionEvaluationComputed,
    EvaluationOut,
    SandboxVerificationResult,
    TeacherReviewRequest,
)
from app.services.eval_progress import get_progress
from app.services.evaluator import run_submission_evaluation

router = APIRouter(prefix="/api/evaluations", tags=["Evaluación Inteligente y Supervisión Docente"])


def _serialize_evaluation(ev: Evaluation) -> EvaluationOut:
    sub = ev.submission
    lab = sub.lab
    rv = ev.rubric_version
    return EvaluationOut(
        id=ev.id,
        submission_id=ev.submission_id,
        student_id=sub.student_id,
        student_name=sub.student.full_name,
        lab_id=lab.id,
        lab_code=lab.code,
        lab_title=lab.title,
        cohort_number=lab.cohort.number,
        rubric_version_id=rv.id,
        rubric_version_number=rv.version_number,
        rubric_title=rv.title,
        ai_provider=ev.ai_provider,
        ai_model_used=ev.ai_model_used,
        status=ev.status,
        preliminary_grade=ev.preliminary_grade,
        final_grade=ev.final_grade,
        summary=ev.summary or "",
        what_student_learned=ev.what_student_learned or "",
        how_applied_knowledge=ev.how_applied_knowledge or "",
        criteria_evaluations=[CriterionEvaluationComputed.model_validate(c) for c in (ev.criteria_evaluations_json or [])],
        strengths=ev.strengths_json or [],
        weaknesses=ev.weaknesses_json or [],
        recommendations=ev.recommendations_json or [],
        competencies=[CompetencyAssessmentAI.model_validate(c) for c in (ev.competencies_snapshot_json or [])],
        sandbox_result=SandboxVerificationResult.model_validate(ev.sandbox_result_json or {}),
        evidence_snapshot=ev.evidence_snapshot_json or {},
        teacher_comments=ev.teacher_comments or "",
        reviewed_by_name=ev.reviewer.full_name if ev.reviewer else None,
        reviewed_at=ev.reviewed_at,
        created_at=ev.created_at,
        audit_logs=[
            AuditLogOut(
                id=log.id,
                actor_name=log.actor.full_name if log.actor else "Sistema",
                action=log.action,
                previous_grade=log.previous_grade,
                new_grade=log.new_grade,
                notes=log.notes or "",
                created_at=log.created_at,
            )
            for log in ev.audit_logs
        ],
    )


@router.get("", response_model=list[EvaluationOut])
def list_evaluations(
    status_filter: str | None = None,
    student_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Evaluation).join(Submission)
    if current_user.role == "student":
        q = q.filter(Submission.student_id == current_user.id)
    elif student_id:
        q = q.filter(Submission.student_id == student_id)

    if status_filter:
        q = q.filter(Evaluation.status == status_filter)

    items = q.order_by(Evaluation.created_at.desc()).all()
    return [_serialize_evaluation(ev) for ev in items]


@router.get("/progress/{submission_id}")
async def get_evaluation_progress(
    submission_id: int,
    _: User = Depends(get_current_user),
):
    return get_progress(submission_id)


@router.get("/{evaluation_id}", response_model=EvaluationOut)
def get_evaluation(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ev = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada.")
    if current_user.role == "student" and ev.submission.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permisos para consultar esta evaluación.")
    return _serialize_evaluation(ev)


@router.post("/run/{submission_id}", response_model=EvaluationOut)
def trigger_evaluation(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Entrega no encontrada.")
    if current_user.role == "student" and sub.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="No puedes evaluar entregas de otro estudiante.")

    try:
        ev = run_submission_evaluation(db=db, submission=sub, actor_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error durante el proceso de evaluación: {exc}")

    return _serialize_evaluation(ev)


@router.put("/{evaluation_id}/review", response_model=EvaluationOut)
def teacher_review_and_approve(
    evaluation_id: int,
    payload: TeacherReviewRequest,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
):
    """
    Mandatory Feature #4 & Engineering Condition #6:
    Allows the teacher to review, adjust criterion ratios (recalculating grade in backend)
    or final grade, add comments, and approve the evaluation before official publication.
    """
    ev = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada.")

    prev_grade = ev.final_grade
    updated_criteria = list(ev.criteria_evaluations_json or [])

    if payload.adjusted_criteria_ratios:
        new_total = 0.0
        for item in updated_criteria:
            cid = item["criterion_id"]
            if cid in payload.adjusted_criteria_ratios:
                ratio = max(0.0, min(1.0, float(payload.adjusted_criteria_ratios[cid])))
                item["score_ratio"] = round(ratio, 3)
                item["criterion_grade_5"] = round(ratio * 5.0, 2)
                item["weighted_contribution"] = round((item["weight_percent"] / 100.0) * item["criterion_grade_5"], 3)
                if ratio >= 0.9:
                    item["level_achieved"] = "excelente"
                elif ratio >= 0.75:
                    item["level_achieved"] = "sobresaliente"
                elif ratio >= 0.6:
                    item["level_achieved"] = "aceptable"
                else:
                    item["level_achieved"] = "insuficiente"
            new_total += (item["weight_percent"] / 100.0) * item["criterion_grade_5"]
        ev.criteria_evaluations_json = updated_criteria
        ev.final_grade = round(min(5.0, max(0.0, new_total)), 2)

    if payload.manual_final_grade is not None:
        ev.final_grade = round(payload.manual_final_grade, 2)

    ev.teacher_comments = payload.teacher_comments.strip()
    ev.reviewed_by = teacher.id
    ev.reviewed_at = datetime.now(timezone.utc)

    action = "teacher_adjusted"
    if payload.approve:
        ev.status = "approved"
        ev.submission.status = "approved"
        action = "teacher_approved"

    db.add(
        EvaluationAuditLog(
            evaluation_id=ev.id,
            actor_id=teacher.id,
            action=action,
            previous_grade=prev_grade,
            new_grade=ev.final_grade,
            notes=payload.teacher_comments.strip() or (
                "Evaluación aprobada por el docente." if payload.approve else "Ajuste docente registrado."
            ),
        )
    )
    db.commit()
    db.refresh(ev)
    return _serialize_evaluation(ev)
