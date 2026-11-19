from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


# ===========================
# Auth & Users
# ===========================
class UserCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)
    role: Literal["student", "teacher"] = "student"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ===========================
# Cohorts & Labs
# ===========================
class CohortOut(BaseModel):
    id: int
    number: int
    name: str
    description: str

    model_config = {"from_attributes": True}


class LabCreate(BaseModel):
    cohort_id: int
    code: str = Field(..., min_length=2, max_length=30)
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)
    objectives: list[str] = Field(default_factory=list)
    ai_topics: list[str] = Field(default_factory=list)


class LabUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    objectives: Optional[list[str]] = None
    ai_topics: Optional[list[str]] = None


class LabOut(BaseModel):
    id: int
    cohort_id: int
    cohort_number: Optional[int] = None
    code: str
    title: str
    description: str
    objectives: list[str]
    ai_topics: list[str]
    active_rubric_id: Optional[int] = None
    active_rubric_version: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ===========================
# Rubrics (Strict 100% validation)
# ===========================
class PerformanceLevel(BaseModel):
    level: Literal["excelente", "sobresaliente", "aceptable", "insuficiente"]
    label: str
    score_ratio: float = Field(..., ge=0.0, le=1.0, description="Proporción entre 0.0 y 1.0 sobre la nota máxima 5.0")
    descriptor: str = Field(..., min_length=5)


class RubricCriterion(BaseModel):
    id: str = Field(..., min_length=1, max_length=40)
    name: str = Field(..., min_length=2, max_length=150)
    competency: str = Field(..., min_length=2, max_length=150)
    weight_percent: float = Field(..., gt=0, le=100)
    levels: list[PerformanceLevel] = Field(..., min_length=2)

    @field_validator("levels")
    @classmethod
    def check_unique_levels(cls, v: list[PerformanceLevel]):
        names = [lvl.level for lvl in v]
        if len(names) != len(set(names)):
            raise ValueError("Los niveles de desempeño dentro de un criterio no pueden repetirse.")
        return v


class RubricCreate(BaseModel):
    lab_id: int
    title: str = Field(..., min_length=3, max_length=200)
    criteria: list[RubricCriterion] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_weights_and_ids(self):
        ids = [c.id for c in self.criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("Los IDs de los criterios en la rúbrica deben ser únicos.")
        total = round(sum(c.weight_percent for c in self.criteria), 2)
        if abs(total - 100.0) > 0.01:
            raise ValueError(
                f"Inconsistencia en rúbrica: la suma de ponderaciones es {total}%, debe ser exactamente 100%."
            )
        return self


class RubricParseRequest(BaseModel):
    raw_text: str = Field(..., min_length=20)
    lab_title: str = ""


class RubricValidationResult(BaseModel):
    is_valid: bool
    total_weight: float
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RubricVersionOut(BaseModel):
    id: int
    lab_id: int
    version_number: int
    title: str
    is_active: bool
    criteria: list[RubricCriterion]
    total_weight: float
    created_at: datetime


# ===========================
# Structured AI Output Schemas (Pydantic strict contract)
# ===========================
class CriterionEvaluationAI(BaseModel):
    criterion_id: str
    criterion_name: str
    competency: str
    level_achieved: Literal["excelente", "sobresaliente", "aceptable", "insuficiente"]
    score_ratio: float = Field(..., ge=0.0, le=1.0, description="Proporción alcanzada en el criterio entre 0.0 y 1.0")
    evidences: list[str] = Field(..., min_length=1, description="Citas concretas del informe PDF o código fuente")
    justification: str = Field(..., min_length=15)


class CompetencyAssessmentAI(BaseModel):
    topic: str = Field(..., description="Temática de IA evaluada, ej. Redes Neuronales, Búsqueda Heurística")
    category: str = Field(..., description="Categoría superior, ej. Machine Learning, Deep Learning, Agentes, NLP")
    mastery_level: Literal["avanzado", "intermedio", "basico", "por_fortalecer"]
    mastery_score: float = Field(..., ge=0.0, le=5.0)
    evidence: str
    needs_deepening: list[str] = Field(default_factory=list)


class EvaluationAIResponse(BaseModel):
    """Strict structured schema required from any LLM. Final numeric grade is NOT trusted from LLM; backend computes it."""
    summary: str = Field(..., min_length=20)
    what_student_learned: str = Field(..., min_length=20)
    how_applied_knowledge: str = Field(..., min_length=20)
    criteria_evaluations: list[CriterionEvaluationAI] = Field(..., min_length=1)
    strengths: list[str] = Field(..., min_length=1)
    weaknesses: list[str] = Field(..., min_length=1)
    recommendations: list[str] = Field(..., min_length=1)
    competencies: list[CompetencyAssessmentAI] = Field(..., min_length=1)


# ===========================
# Sandbox Verification Schema
# ===========================
class SandboxVerificationResult(BaseModel):
    sandbox_mode: str = "subprocess"
    network_blocked: bool = True
    timeout_seconds: int = 15
    memory_limit_mb: int = 256
    files_analyzed: list[str] = Field(default_factory=list)
    total_lines_of_code: int = 0
    syntax_ok: bool = True
    syntax_errors: list[str] = Field(default_factory=list)
    static_issues_count: int = 0
    static_issues: list[str] = Field(default_factory=list)
    unit_tests_found: bool = False
    unit_tests_passed: int = 0
    unit_tests_failed: int = 0
    unit_tests_output: str = ""
    execution_time_ms: int = 0
    technical_score_hint: float = Field(0.0, ge=0.0, le=5.0)


# ===========================
# Submissions & Evaluations
# ===========================
class SubmissionOut(BaseModel):
    id: int
    student_id: int
    student_name: Optional[str] = None
    lab_id: int
    lab_code: Optional[str] = None
    lab_title: Optional[str] = None
    cohort_number: Optional[int] = None
    rubric_version_id: int
    rubric_version_number: Optional[int] = None
    pdf_filename: str
    pdf_page_count: int
    pdf_image_count: int
    code_source_type: str
    code_filename: Optional[str] = None
    github_url: Optional[str] = None
    optional_media_url: Optional[str] = None
    optional_media_notes: Optional[str] = None
    status: str
    latest_evaluation_id: Optional[int] = None
    latest_grade: Optional[float] = None
    latest_eval_status: Optional[str] = None
    created_at: datetime


class CriterionEvaluationComputed(CriterionEvaluationAI):
    weight_percent: float
    criterion_grade_5: float
    weighted_contribution: float


class AuditLogOut(BaseModel):
    id: int
    actor_name: Optional[str] = None
    action: str
    previous_grade: Optional[float] = None
    new_grade: Optional[float] = None
    notes: str
    created_at: datetime


class EvaluationOut(BaseModel):
    id: int
    submission_id: int
    student_id: int
    student_name: str
    lab_id: int
    lab_code: str
    lab_title: str
    cohort_number: int
    rubric_version_id: int
    rubric_version_number: int
    rubric_title: str
    ai_provider: str
    ai_model_used: str
    status: str
    preliminary_grade: float
    final_grade: float
    summary: str
    what_student_learned: str
    how_applied_knowledge: str
    criteria_evaluations: list[CriterionEvaluationComputed]
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]
    competencies: list[CompetencyAssessmentAI]
    sandbox_result: SandboxVerificationResult
    evidence_snapshot: dict
    teacher_comments: str
    reviewed_by_name: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    audit_logs: list[AuditLogOut] = Field(default_factory=list)


class TeacherReviewRequest(BaseModel):
    adjusted_criteria_ratios: Optional[dict[str, float]] = None  # criterion_id -> ratio (0.0..1.0)
    manual_final_grade: Optional[float] = Field(default=None, ge=0.0, le=5.0)
    teacher_comments: str = ""
    approve: bool = False


# ===========================
# AI Settings
# ===========================
class AISettingsUpdate(BaseModel):
    provider: Literal["gemini", "groq", "openrouter", "ollama"]
    model_name: str = Field(..., min_length=2, max_length=120)
    base_url: str = ""
    api_key_override: str = ""


class AISettingsOut(BaseModel):
    provider: str
    model_name: str
    base_url: str
    has_api_key: bool
    sandbox_mode: str
    available_providers: list[dict]
