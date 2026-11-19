import io
import tempfile
import zipfile
from pathlib import Path
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.auth import create_access_token, verify_password
from app.database import Base
from app.models import Cohort, Evaluation, Lab, RubricVersion, Submission, User
from app.routers.evaluations import teacher_review_and_approve
from app.routers.rubrics import validate_rubric_draft
from app.schemas import (
    CriterionEvaluationAI,
    PerformanceLevel,
    RubricCreate,
    RubricCriterion,
    TeacherReviewRequest,
)
from app.services.analytics import build_integrated_report, build_interactive_mind_map
from app.services.document_parser import extract_document_content
from app.services.evaluator import calculate_weighted_grade, run_submission_evaluation
from app.services.pdf_report import generate_integrated_report_pdf
from app.services.sandbox import verify_code_in_sandbox
from app.services.seed import seed_initial_data
from app.services.storage import ensure_local_upload_dir, save_bytes


def _sample_levels():
    return [
        PerformanceLevel(level="excelente", label="Excelente", score_ratio=1.0, descriptor="Cumple completamente."),
        PerformanceLevel(level="sobresaliente", label="Sobresaliente", score_ratio=0.8, descriptor="Cumple bien."),
        PerformanceLevel(level="aceptable", label="Aceptable", score_ratio=0.6, descriptor="Cumple parcial."),
        PerformanceLevel(level="insuficiente", label="Insuficiente", score_ratio=0.2, descriptor="No cumple."),
    ]


def test_rubric_rejects_weights_not_equal_100():
    with pytest.raises(ValidationError) as exc_info:
        RubricCreate(
            lab_id=1,
            title="Rúbrica inválida",
            criteria=[
                RubricCriterion(id="c1", name="C1", competency="Comp 1", weight_percent=60.0, levels=_sample_levels()),
                RubricCriterion(id="c2", name="C2", competency="Comp 2", weight_percent=30.0, levels=_sample_levels()),
            ],
        )
    assert "100%" in str(exc_info.value)

    val = validate_rubric_draft(
        {
            "criteria": [
                {"id": "c1", "name": "C1", "competency": "IA", "weight_percent": 50, "levels": [{"score_ratio": 1.0}, {"score_ratio": 0.5}]},
                {"id": "c2", "name": "C2", "competency": "IA", "weight_percent": 30, "levels": [{"score_ratio": 1.0}, {"score_ratio": 0.5}]},
            ]
        },
        _=None,
    )
    assert val.is_valid is False
    assert val.total_weight == 80.0


def test_deterministic_backend_grade_calculation():
    criteria = [
        RubricCriterion(id="c1", name="Algoritmo", competency="IA", weight_percent=60.0, levels=_sample_levels()),
        RubricCriterion(id="c2", name="Informe", competency="Análisis", weight_percent=40.0, levels=_sample_levels()),
    ]
    ai_evals = [
        CriterionEvaluationAI(
            criterion_id="c1",
            criterion_name="Algoritmo",
            competency="IA",
            level_achieved="excelente",
            score_ratio=1.0,  # 5.0 * 0.60 = 3.0
            evidences=["archivo.py línea 12"],
            justification="Implementación óptima verificada con pruebas unitarias.",
        ),
        CriterionEvaluationAI(
            criterion_id="c2",
            criterion_name="Informe",
            competency="Análisis",
            level_achieved="aceptable",
            score_ratio=0.5,  # 2.5 * 0.40 = 1.0
            evidences=["informe.pdf pág 2"],
            justification="Análisis básico pero correcto de resultados.",
        ),
    ]
    grade, computed = calculate_weighted_grade(criteria, ai_evals)
    assert grade == 4.0
    assert len(computed) == 2
    assert computed[0].weighted_contribution == 3.0
    assert computed[1].weighted_contribution == 1.0


def test_sandbox_verifies_tests_and_blocks_network():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "algo.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        (root / "test_algo.py").write_text(
            "import socket\n"
            "import pytest\n"
            "from algo import add\n\n"
            "def test_add():\n"
            "    assert add(2, 3) == 5\n\n"
            "def test_network_is_blocked():\n"
            "    with pytest.raises(PermissionError):\n"
            "        socket.create_connection(('example.com', 80), timeout=1)\n",
            encoding="utf-8",
        )
        res = verify_code_in_sandbox(root, ["algo.py", "test_algo.py"], 12)
        assert res.syntax_ok is True
        assert res.static_issues_count == 0
        assert res.network_blocked is True
        assert res.unit_tests_found is True
        assert res.unit_tests_passed == 2
        assert res.unit_tests_failed == 0


def test_sandbox_catches_syntax_error():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "broken.py").write_text("def broken(:\n    pass\n", encoding="utf-8")
        res = verify_code_in_sandbox(root, ["broken.py"], 2)
        assert res.syntax_ok is False
        assert len(res.syntax_errors) == 1


def test_docx_document_extraction():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>Laboratorio de Redes Neuronales en Python con PyTorch</w:t></w:r></w:p></w:body>"
            "</w:document>",
        )
    res = extract_document_content(buf.getvalue(), "guia_lab.docx")
    assert res["is_readable"] is True
    assert res["format"] == "docx"
    assert "Redes Neuronales" in res["text"]


def test_full_domain_flow_seed_reports_mindmap_and_teacher_review():
    ensure_local_upload_dir()
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    db = TestSession()
    try:
        seed_initial_data(db)

        student = db.query(User).filter(User.email == "estudiante@umanizales.edu.co").first()
        teacher = db.query(User).filter(User.email == "docente@umanizales.edu.co").first()
        assert student is not None and teacher is not None
        assert verify_password("Estudiante123!", student.hashed_password)
        assert len(create_access_token(student.id, student.role)) > 20

        assert db.query(Cohort).count() == 2
        labs = db.query(Lab).order_by(Lab.cohort_id, Lab.code).all()
        assert len(labs) == 3

        # Create a real submission (txt report + zip with python & pytest) and run evaluation
        lab_c1 = labs[0]
        rubric_c1 = db.query(RubricVersion).filter(RubricVersion.lab_id == lab_c1.id).first()
        report_path = save_bytes(
            b"Informe tecnico detallado del Laboratorio 2 Mzls Resiliente con analisis de resultados y metricas.",
            "informe_test.txt",
            subfolder="test_tmp",
        )
        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w") as zf:
            zf.writestr("main.py", "def score(x):\n    return x * 2\n")
            zf.writestr("test_main.py", "from main import score\n\ndef test_score():\n    assert score(2) == 4\n")
        zip_path = save_bytes(zbuf.getvalue(), "codigo_test.zip", subfolder="test_tmp")

        sub = Submission(
            student_id=student.id,
            lab_id=lab_c1.id,
            rubric_version_id=rubric_c1.id,
            pdf_filename="informe_test.txt",
            pdf_storage_path=report_path,
            pdf_extracted_text="Informe tecnico detallado del Laboratorio 2 Mzls Resiliente.",
            pdf_page_count=1,
            pdf_image_count=0,
            code_source_type="zip",
            code_filename="codigo_test.zip",
            code_storage_path=zip_path,
            status="uploaded",
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)

        ev = run_submission_evaluation(db=db, submission=sub, actor_id=student.id)
        assert 0.0 <= ev.preliminary_grade <= 5.0
        assert ev.sandbox_result_json["unit_tests_passed"] == 1

        # Integrated report & PDF download
        report = build_integrated_report(db, student.id)
        assert report["overview"]["labs_evaluated"] == 1
        assert report["overview"]["cohort_1_average"] is not None

        pdf_bytes = generate_integrated_report_pdf(report)
        assert pdf_bytes.startswith(b"%PDF")
        assert len(pdf_bytes) > 1500

        # Interactive Mind Map
        mm = build_interactive_mind_map(db, student.id)
        assert len(mm["nodes"]) >= 5
        assert len(mm["edges"]) >= 4

        # Teacher review & audit traceability
        reviewed = teacher_review_and_approve(
            evaluation_id=ev.id,
            payload=TeacherReviewRequest(
                manual_final_grade=ev.final_grade,
                teacher_comments="Validación de prueba automatizada.",
                approve=True,
            ),
            db=db,
            teacher=teacher,
        )
        assert reviewed.status == "approved"
        assert len(reviewed.audit_logs) >= 2
    finally:
        db.close()
