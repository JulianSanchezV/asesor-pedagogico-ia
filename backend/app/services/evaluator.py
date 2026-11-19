import json
import shutil
import tempfile
from pathlib import Path
from sqlalchemy.orm import Session
from app.models import Evaluation, EvaluationAuditLog, Lab, RubricVersion, Submission
from app.schemas import (
    CriterionEvaluationComputed,
    EvaluationAIResponse,
    RubricCriterion,
    SandboxVerificationResult,
)
from app.services.ai_provider import (
    build_offline_heuristic_evaluation,
    call_structured_llm,
    get_active_ai_config,
)
from app.services.code_loader import (
    collect_code_snippets,
    download_github_repo_zip,
    safe_extract_zip,
)
from app.services.document_parser import extract_document_content
from app.services.eval_progress import finish_progress, start_progress, update_progress
from app.services.sandbox import verify_code_in_sandbox
from app.services.storage import load_bytes


def calculate_weighted_grade(
    rubric_criteria: list[RubricCriterion],
    ai_criteria_evals: list,
) -> tuple[float, list[CriterionEvaluationComputed]]:
    """
    ENGINEERING CONDITION #2 (CRITICAL):
    The final numeric grade between 0.0 and 5.0 is ALWAYS calculated deterministically
    by the backend applying the exact rubric weights (summing 100%), NEVER trusted to free LLM math.
    """
    ai_by_id = {c.criterion_id: c for c in ai_criteria_evals}
    computed: list[CriterionEvaluationComputed] = []
    total_grade = 0.0

    for crit in rubric_criteria:
        ai_item = ai_by_id.get(crit.id)
        if ai_item is None:
            # Match fallback by normalized name if LLM altered criterion_id slightly
            for cand in ai_criteria_evals:
                if cand.criterion_name.strip().lower() == crit.name.strip().lower():
                    ai_item = cand
                    break

        ratio = float(ai_item.score_ratio) if ai_item else 0.0
        ratio = max(0.0, min(1.0, ratio))
        criterion_grade_5 = round(ratio * 5.0, 2)
        weighted_contribution = round((crit.weight_percent / 100.0) * criterion_grade_5, 4)
        total_grade += weighted_contribution

        computed.append(
            CriterionEvaluationComputed(
                criterion_id=crit.id,
                criterion_name=crit.name,
                competency=crit.competency,
                level_achieved=ai_item.level_achieved if ai_item else "insuficiente",
                score_ratio=round(ratio, 3),
                evidences=ai_item.evidences if ai_item else ["No se encontraron evidencias suficientes para este criterio."],
                justification=ai_item.justification if ai_item else "El modelo no devolvió justificación para este criterio.",
                weight_percent=crit.weight_percent,
                criterion_grade_5=criterion_grade_5,
                weighted_contribution=round(weighted_contribution, 3),
            )
        )

    final_score = round(min(5.0, max(0.0, total_grade)), 2)
    return final_score, computed


def _build_evaluation_prompts(
    lab: Lab,
    rubric_criteria: list[RubricCriterion],
    pdf_text: str,
    code_snippets: str,
    sandbox: SandboxVerificationResult,
    optional_media_url: str | None,
    optional_media_notes: str | None,
) -> tuple[str, str]:
    system_prompt = (
        "Eres un Asesor Pedagógico Inteligente universitario experto en Inteligencia Artificial e Ingeniería de Software. "
        "Tu tarea es evaluar de forma objetiva, explicable y rigurosa la entrega de un estudiante usando ÚNICAMENTE "
        "la rúbrica dada, las evidencias del informe PDF, el código fuente y los resultados reales del sandbox técnico.\n"
        "REGLAS ESTRICTAS:\n"
        "1. Evalúa CADA criterio de la rúbrica usando su `criterion_id` exacto.\n"
        "2. Cita evidencias concretas (nombres de archivo, funciones, resultados de pruebas o frases del informe PDF).\n"
        "3. Asigna `score_ratio` entre 0.0 y 1.0 acorde al nivel de desempeño elegido en la rúbrica. "
        "NO calcules la nota final global (el backend la calcula matemáticamente).\n"
        "4. Si el sandbox reporta errores de sintaxis o pruebas unitarias fallidas, refléjalo con rigor en los criterios técnicos.\n"
        "5. Identifica claramente qué aprendió el estudiante, cómo aplicó sus conocimientos, fortalezas, debilidades, "
        "recomendaciones personalizadas y el nivel de dominio en cada temática de IA.\n"
        "6. Responde siempre en español claro y académico."
    )

    rubric_serialized = json.dumps([c.model_dump() for c in rubric_criteria], ensure_ascii=False, indent=2)
    sandbox_serialized = json.dumps(sandbox.model_dump(), ensure_ascii=False, indent=2)

    media_block = ""
    if optional_media_url or optional_media_notes:
        media_block = (
            f"\n=== MATERIAL OPCIONAL (VIDEO / PRESENTACIÓN) ===\n"
            f"URL: {optional_media_url or 'N/A'}\nNotas: {optional_media_notes or 'N/A'}\n"
        )

    user_prompt = f"""
=== LABORATORIO ===
Código: {lab.code}
Título: {lab.title}
Descripción: {lab.description}
Objetivos: {json.dumps(lab.objectives or [], ensure_ascii=False)}
Temáticas de IA esperadas: {json.dumps(lab.ai_topics or [], ensure_ascii=False)}

=== RÚBRICA OFICIAL (Ponderaciones suman 100%) ===
{rubric_serialized}

=== VERIFICACIÓN TÉCNICA OBJETIVA EN SANDBOX ===
{sandbox_serialized}

=== INFORME DEL ESTUDIANTE (PDF EXTRAÍDO) ===
{pdf_text[:16000]}

=== CÓDIGO FUENTE ENTREGADO ===
{code_snippets[:18000]}
{media_block}
Evalúa la entrega devolviendo estrictamente el esquema estructurado solicitado.
""".strip()
    return system_prompt, user_prompt


def run_submission_evaluation(db: Session, submission: Submission, actor_id: int) -> Evaluation:
    """
    Full evaluation pipeline:
    1. Load student PDF (text + images) & Code (ZIP or GitHub)
    2. Run objective technical verification inside isolated Sandbox
    3. Call configured AI provider (Gemini multimodal / Groq / OpenRouter / Ollama) with Pydantic schema
    4. Compute weighted grade (0.0-5.0) deterministically in backend
    5. Save full traceable Evaluation + Audit Log (pending teacher approval)
    """
    lab = db.query(Lab).filter(Lab.id == submission.lab_id).first()
    rubric = db.query(RubricVersion).filter(RubricVersion.id == submission.rubric_version_id).first()
    if not lab or not rubric:
        raise ValueError("Laboratorio o versión de rúbrica no encontrados para esta entrega.")

    rubric_criteria = [RubricCriterion.model_validate(c) for c in rubric.criteria_json]
    total_w = round(sum(c.weight_percent for c in rubric_criteria), 2)
    if abs(total_w - 100.0) > 0.01:
        raise ValueError(f"La rúbrica asociada tiene inconsistencia de ponderación ({total_w}% != 100%).")

    start_progress(submission.id, f"{lab.code} — {lab.title}")
    try:
        # 1. Load report document (PDF/DOCX/TXT/MD text + images for multimodal Gemini)
        update_progress(
            submission.id,
            "pdf",
            15,
            f"Extrayendo texto e imágenes de '{submission.pdf_filename}'...",
            note=submission.pdf_filename,
        )
        pdf_bytes = load_bytes(submission.pdf_storage_path)
        pdf_data = extract_document_content(pdf_bytes, submission.pdf_filename, max_images=3)
        pdf_text = pdf_data["text"] or submission.pdf_extracted_text or ""
        word_count = len(pdf_text.split())
        update_progress(
            submission.id,
            "pdf",
            25,
            f"Informe leído: {pdf_data['page_count']} pág., {word_count} palabras, {len(pdf_data['extracted_images'])} imágenes.",
            note=f"{word_count} palabras · {pdf_data['page_count']} pág.",
        )

        # 2. Optional code loading & Sandbox verification
        has_code = (
            (submission.code_source_type == "github" and bool(submission.github_url))
            or (submission.code_source_type == "zip" and bool(submission.code_storage_path))
        )

        if has_code:
            source_label = submission.github_url or submission.code_filename or "código"
            update_progress(
                submission.id,
                "sandbox",
                38,
                f"Descargando/descomprimiendo '{source_label}' y ejecutando AST, Ruff y Pytest en Sandbox aislado...",
                note=source_label,
            )
            temp_dir = Path(tempfile.mkdtemp(prefix="eval_code_"))
            try:
                if submission.code_source_type == "github" and submission.github_url:
                    zip_bytes = download_github_repo_zip(submission.github_url)
                else:
                    zip_bytes = load_bytes(submission.code_storage_path)

                safe_extract_zip(zip_bytes, temp_dir)
                rel_files, code_snippets, total_loc = collect_code_snippets(temp_dir)
                update_progress(
                    submission.id,
                    "sandbox",
                    50,
                    f"Ejecutando verificación en Sandbox sobre {len(rel_files)} archivo(s) ({total_loc} líneas)...",
                    note=f"{len(rel_files)} archivos · {total_loc} líneas",
                )
                sandbox_result = verify_code_in_sandbox(temp_dir, rel_files, total_loc)
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
        else:
            update_progress(
                submission.id,
                "sandbox",
                48,
                "Entrega sin código adjunto (campo opcional) — pasando directo al análisis documental.",
                note="Omitido (solo informe)",
            )
            code_snippets = "(Entrega documental sin archivo de código fuente adjunto. Evalúa con base en el informe y las evidencias presentadas.)"
            sandbox_result = SandboxVerificationResult(
                sandbox_mode="omitido",
                network_blocked=True,
                files_analyzed=[],
                total_lines_of_code=0,
                syntax_ok=True,
                syntax_errors=[],
                static_issues_count=0,
                static_issues=[],
                unit_tests_found=False,
                unit_tests_passed=0,
                unit_tests_failed=0,
                unit_tests_output="No se adjuntó código fuente en esta entrega (campo opcional); evaluación centrada en el informe documental.",
                execution_time_ms=0,
                technical_score_hint=0.0,
            )

        # 3. Call configured AI provider with strict Pydantic validation
        ai_cfg = get_active_ai_config(db)
        used_provider = ai_cfg["provider"]
        used_model = ai_cfg["model_name"]
        fallback_note = ""

        if ai_cfg["has_api_key"]:
            update_progress(
                submission.id,
                "ai",
                65,
                f"Enviando evidencias y rúbrica v{rubric.version_number} a {used_provider} ({used_model})...",
                note=f"{used_provider} / {used_model}",
            )
            sys_prompt, usr_prompt = _build_evaluation_prompts(
                lab=lab,
                rubric_criteria=rubric_criteria,
                pdf_text=pdf_text,
                code_snippets=code_snippets,
                sandbox=sandbox_result,
                optional_media_url=submission.optional_media_url,
                optional_media_notes=submission.optional_media_notes,
            )
            try:
                ai_response, raw_json = call_structured_llm(
                    config=ai_cfg,
                    system_prompt=sys_prompt,
                    user_prompt=usr_prompt,
                    response_schema=EvaluationAIResponse,
                    images=pdf_data["extracted_images"] if used_provider == "gemini" else None,
                    on_status=lambda msg: update_progress(submission.id, "ai", 74, msg, note=used_provider),
                )
                used_model = ai_cfg.get("_resolved_model", used_model)
            except Exception as exc:
                update_progress(
                    submission.id,
                    "ai",
                    80,
                    "El proveedor IA no respondió a tiempo; aplicando respaldo local verificable...",
                    note="Respaldo local",
                )
                ai_response, raw_json = build_offline_heuristic_evaluation(
                    lab_title=lab.title,
                    ai_topics=lab.ai_topics or [],
                    criteria=rubric_criteria,
                    pdf_text=pdf_text,
                    code_snippets=code_snippets,
                    sandbox=sandbox_result,
                )
                used_provider = f"{used_provider}-fallback"
                used_model = "verificador-heuristico-local"
                fallback_note = f"Fallback automático aplicado por error del proveedor IA: {str(exc)[:240]}"
        else:
            update_progress(
                submission.id,
                "ai",
                75,
                "Sin API Key configurada; generando evaluación heurística local...",
                note="Modo local",
            )
            ai_response, raw_json = build_offline_heuristic_evaluation(
                lab_title=lab.title,
                ai_topics=lab.ai_topics or [],
                criteria=rubric_criteria,
                pdf_text=pdf_text,
                code_snippets=code_snippets,
                sandbox=sandbox_result,
            )
            used_provider = "local-sin-apikey"
            used_model = "verificador-heuristico-local"
            fallback_note = "Evaluación ejecutada sin API Key de IA configurada (solo verificación sandbox + heurística)."

        # 4. Deterministic backend grade calculation (NEVER LLM free math)
        update_progress(
            submission.id,
            "grade",
            90,
            f"Validando esquema Pydantic y calculando nota ponderada (0.0–5.0) con rúbrica v{rubric.version_number}...",
            note="Cálculo determinista",
        )
        preliminary_grade, computed_criteria = calculate_weighted_grade(
            rubric_criteria=rubric_criteria,
            ai_criteria_evals=ai_response.criteria_evaluations,
        )

        evidence_snapshot = {
            "pdf_filename": submission.pdf_filename,
            "pdf_pages": pdf_data["page_count"],
            "pdf_images_analyzed": len(pdf_data["extracted_images"]),
            "pdf_word_count": word_count,
            "code_source_type": submission.code_source_type,
            "code_reference": submission.github_url or submission.code_filename,
            "files_analyzed": sandbox_result.files_analyzed,
            "total_lines_of_code": sandbox_result.total_lines_of_code,
            "fallback_note": fallback_note,
        }

        evaluation = Evaluation(
            submission_id=submission.id,
            rubric_version_id=rubric.id,
            ai_provider=used_provider,
            ai_model_used=used_model,
            status="pending_review",
            preliminary_grade=preliminary_grade,
            final_grade=preliminary_grade,
            summary=ai_response.summary,
            what_student_learned=ai_response.what_student_learned,
            how_applied_knowledge=ai_response.how_applied_knowledge,
            criteria_evaluations_json=[c.model_dump() for c in computed_criteria],
            strengths_json=ai_response.strengths,
            weaknesses_json=ai_response.weaknesses,
            recommendations_json=ai_response.recommendations,
            competencies_snapshot_json=[c.model_dump() for c in ai_response.competencies],
            sandbox_result_json=sandbox_result.model_dump(),
            evidence_snapshot_json=evidence_snapshot,
            ai_raw_output_json=raw_json,
            teacher_comments="",
        )
        db.add(evaluation)
        submission.status = "pending_review"
        db.flush()

        audit = EvaluationAuditLog(
            evaluation_id=evaluation.id,
            actor_id=actor_id,
            action="ai_evaluated",
            previous_grade=None,
            new_grade=preliminary_grade,
            notes=f"Evaluación ejecutada con {used_provider}/{used_model} sobre rúbrica v{rubric.version_number}. {fallback_note}".strip(),
        )
        db.add(audit)
        db.commit()
        db.refresh(evaluation)
        finish_progress(submission.id, f"¡Evaluación completada! Nota preliminar: {preliminary_grade}/5.0.")
        return evaluation
    except Exception as exc:
        finish_progress(submission.id, f"Error: {str(exc)[:180]}", error=True)
        raise
