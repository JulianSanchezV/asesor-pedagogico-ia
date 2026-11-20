from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(180), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="student")  # student | teacher
    created_at = Column(DateTime(timezone=True), default=utcnow)

    submissions = relationship("Submission", back_populates="student", foreign_keys="Submission.student_id")


class Cohort(Base):
    __tablename__ = "cohorts"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(Integer, unique=True, nullable=False)  # 1 or 2
    name = Column(String(120), nullable=False)
    description = Column(Text, default="")

    labs = relationship("Lab", back_populates="cohort", cascade="all, delete-orphan")


class Lab(Base):
    __tablename__ = "labs"

    id = Column(Integer, primary_key=True, index=True)
    cohort_id = Column(Integer, ForeignKey("cohorts.id"), nullable=False)
    code = Column(String(30), unique=True, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    objectives = Column(JSON, default=list)  # list[str]
    ai_topics = Column(JSON, default=list)  # list[str]
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    cohort = relationship("Cohort", back_populates="labs")
    rubrics = relationship("RubricVersion", back_populates="lab", cascade="all, delete-orphan", order_by="RubricVersion.version_number.desc()")
    submissions = relationship("Submission", back_populates="lab", cascade="all, delete-orphan")


class RubricVersion(Base):
    __tablename__ = "rubric_versions"

    id = Column(Integer, primary_key=True, index=True)
    lab_id = Column(Integer, ForeignKey("labs.id"), nullable=False)
    version_number = Column(Integer, nullable=False, default=1)
    title = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)
    criteria_json = Column(JSON, nullable=False)  # list[RubricCriterion]
    total_weight = Column(Float, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    lab = relationship("Lab", back_populates="rubrics")


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    lab_id = Column(Integer, ForeignKey("labs.id"), nullable=False)
    rubric_version_id = Column(Integer, ForeignKey("rubric_versions.id"), nullable=False)

    pdf_filename = Column(String(255), nullable=False)
    pdf_storage_path = Column(String(500), nullable=False)
    pdf_extracted_text = Column(Text, default="")
    pdf_page_count = Column(Integer, default=0)
    pdf_image_count = Column(Integer, default=0)

    code_source_type = Column(String(20), nullable=False)  # zip | github
    code_filename = Column(String(255), nullable=True)
    code_storage_path = Column(String(500), nullable=True)
    github_url = Column(String(500), nullable=True)

    optional_media_url = Column(String(500), nullable=True)
    optional_media_notes = Column(Text, nullable=True)

    status = Column(String(30), default="uploaded")  # uploaded | pending_review | approved
    created_at = Column(DateTime(timezone=True), default=utcnow)

    student = relationship("User", back_populates="submissions", foreign_keys=[student_id])
    lab = relationship("Lab", back_populates="submissions")
    rubric_version = relationship("RubricVersion")
    evaluations = relationship("Evaluation", back_populates="submission", cascade="all, delete-orphan", order_by="Evaluation.created_at.desc()")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False)
    rubric_version_id = Column(Integer, ForeignKey("rubric_versions.id"), nullable=False)

    ai_provider = Column(String(50), nullable=False)
    ai_model_used = Column(String(120), nullable=False)
    status = Column(String(30), default="pending_review")  # pending_review | approved

    # Calculated strictly by backend math (0.0 to 5.0)
    preliminary_grade = Column(Float, nullable=False)
    final_grade = Column(Float, nullable=False)

    summary = Column(Text, default="")
    what_student_learned = Column(Text, default="")
    how_applied_knowledge = Column(Text, default="")
    criteria_evaluations_json = Column(JSON, default=list)
    strengths_json = Column(JSON, default=list)
    weaknesses_json = Column(JSON, default=list)
    recommendations_json = Column(JSON, default=list)
    competencies_snapshot_json = Column(JSON, default=list)

    sandbox_result_json = Column(JSON, default=dict)
    evidence_snapshot_json = Column(JSON, default=dict)
    ai_raw_output_json = Column(JSON, default=dict)

    teacher_comments = Column(Text, default="")
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    submission = relationship("Submission", back_populates="evaluations")
    rubric_version = relationship("RubricVersion")
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    audit_logs = relationship("EvaluationAuditLog", back_populates="evaluation", cascade="all, delete-orphan", order_by="EvaluationAuditLog.created_at.desc()")


class EvaluationAuditLog(Base):
    __tablename__ = "evaluation_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(Integer, ForeignKey("evaluations.id"), nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(50), nullable=False)
    previous_grade = Column(Float, nullable=True)
    new_grade = Column(Float, nullable=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=utcnow)

    evaluation = relationship("Evaluation", back_populates="audit_logs")
    actor = relationship("User")


class AISettingsModel(Base):
    __tablename__ = "ai_settings"

    id = Column(Integer, primary_key=True, default=1)
    provider = Column(String(30), default="gemini")  # gemini | groq | openrouter | ollama
    model_name = Column(String(120), default="gemini-3.5-flash-lite")
    base_url = Column(String(300), default="")
    api_key_override = Column(String(300), default="")
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class StoredFile(Base):
    __tablename__ = "stored_files"

    id = Column(String(64), primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    content = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
