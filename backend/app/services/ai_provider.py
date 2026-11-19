import json
import re
import time
from typing import Callable, Optional
from google import genai
from google.genai import types
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.config import get_settings
from app.models import AISettingsModel
from app.schemas import (
    CompetencyAssessmentAI,
    CriterionEvaluationAI,
    EvaluationAIResponse,
    RubricCriterion,
    SandboxVerificationResult,
)

settings = get_settings()

PROVIDER_CATALOG = [
    {
        "id": "gemini",
        "name": "Google Gemini API (Nube - Gratis en AI Studio)",
        "default_model": "gemini-3.5-flash-lite",
        "default_base_url": "",
        "multimodal": True,
        "cost_info": "Nivel gratuito sin tarjeta de crédito en Google AI Studio (límites por minuto/día).",
        "limitations": "Cuotas por minuto/día; en el nivel gratuito los prompts pueden ser usados por Google para mejora del producto.",
    },
    {
        "id": "groq",
        "name": "Groq Cloud (Nube - Gratis, ultra rápido)",
        "default_model": "llama-3.3-70b-versatile",
        "default_base_url": "https://api.groq.com/openai/v1",
        "multimodal": False,
        "cost_info": "Nivel gratuito sin tarjeta de crédito.",
        "limitations": "Límite estricto de tokens por minuto (TPM); ideal como respaldo rápido de texto y código.",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter (Nube - Multi-modelo :free)",
        "default_model": "meta-llama/llama-3.3-70b-instruct:free",
        "default_base_url": "https://openrouter.ai/api/v1",
        "multimodal": False,
        "cost_info": "Modelos :free gratuitos (~50 req/día sin tarjeta).",
        "limitations": "Disponibilidad variable según proveedor tercero y cuota diaria reducida.",
    },
    {
        "id": "ollama",
        "name": "Ollama (Local - 100% Privado y Gratis)",
        "default_model": "qwen2.5-coder:7b",
        "default_base_url": "http://localhost:11434/v1",
        "multimodal": False,
        "cost_info": "$0 costo por token; corre localmente en tu equipo o servidor propio.",
        "limitations": "Requiere GPU/RAM local adecuada (8-16 GB RAM mínimo) y conexión al host donde corre Ollama.",
    },
]


def get_active_ai_config(db: Session) -> dict:
    row = db.query(AISettingsModel).filter(AISettingsModel.id == 1).first()
    provider = row.provider if row else settings.AI_PROVIDER
    model_name = row.model_name if row else settings.GEMINI_MODEL
    base_url = row.base_url if row else ""
    api_key = (row.api_key_override or "").strip() if row else ""

    if provider == "gemini":
        api_key = api_key or settings.GEMINI_API_KEY
        model_name = model_name or settings.GEMINI_MODEL
    elif provider == "ollama":
        api_key = api_key or "ollama"
        base_url = base_url or settings.OLLAMA_BASE_URL
        model_name = model_name or settings.OLLAMA_MODEL
    elif provider == "groq":
        api_key = api_key or settings.OPENAI_COMPAT_API_KEY
        base_url = base_url or "https://api.groq.com/openai/v1"
        model_name = model_name or "llama-3.3-70b-versatile"
    elif provider == "openrouter":
        api_key = api_key or settings.OPENAI_COMPAT_API_KEY
        base_url = base_url or "https://openrouter.ai/api/v1"
        model_name = model_name or "meta-llama/llama-3.3-70b-instruct:free"

    return {
        "provider": provider,
        "model_name": model_name,
        "base_url": base_url,
        "api_key": api_key,
        "has_api_key": bool(api_key and api_key != "ollama") or provider == "ollama",
    }


def _extract_json_block(text: str) -> str:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        return fenced.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def call_structured_llm(
    config: dict,
    system_prompt: str,
    user_prompt: str,
    response_schema: type[BaseModel],
    images: Optional[list[tuple[bytes, str]]] = None,
    on_status: Optional[Callable[[str], None]] = None,
) -> tuple[BaseModel, dict]:
    """
    Invoke configured LLM (Gemini multimodal or OpenAI-compatible/Ollama)
    and enforce strict Pydantic schema validation.
    """
    provider = config["provider"]
    model_name = config["model_name"]
    api_key = config["api_key"]
    base_url = config["base_url"]

    if provider == "gemini":
        if not api_key:
            raise RuntimeError("No hay GEMINI_API_KEY configurada.")
        client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=45_000))
        contents: list = [user_prompt]
        if images:
            for img_bytes, mime in images:
                contents.append(types.Part.from_bytes(data=img_bytes, mime_type=mime))

        candidate_models = [model_name]
        for alt in (
            "gemini-3.8-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.7-flash",
            "gemini-3.5-flash",
            "gemini-flash-latest",
            "gemini-flash-lite-latest",
        ):
            if alt not in candidate_models:
                candidate_models.append(alt)

        last_exc = None
        for cand_model in candidate_models:
            for attempt in range(2):
                try:
                    if on_status:
                        img_txt = f" + {len(images)} imagen(es)" if images else ""
                        on_status(f"Consultando Google Gemini ({cand_model}{img_txt}) — intento {attempt + 1}...")
                    response = client.models.generate_content(
                        model=cand_model,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=0.2,
                            response_mime_type="application/json",
                            response_schema=response_schema,
                        ),
                    )
                    raw_text = response.text or "{}"
                    parsed = response_schema.model_validate_json(raw_text)
                    config["_resolved_model"] = cand_model
                    return parsed, json.loads(raw_text)
                except Exception as exc:
                    last_exc = exc
                    msg = str(exc)
                    # Retry briefly on transient 503/429 spikes before trying next model
                    if ("503" in msg or "429" in msg or "UNAVAILABLE" in msg) and attempt == 0:
                        if on_status:
                            on_status(f"Alta demanda temporal en {cand_model} (503/429). Reintentando en breve...")
                        time.sleep(1.5)
                        continue
                    if on_status:
                        on_status(f"{cand_model} no disponible; probando modelo alternativo...")
                    break
        raise last_exc or RuntimeError("No se pudo obtener respuesta de Gemini.")

    # OpenAI-compatible path: Groq, OpenRouter, or local Ollama
    if not api_key and provider != "ollama":
        raise RuntimeError(f"No hay API Key configurada para el proveedor {provider}.")

    if on_status:
        on_status(f"Consultando {provider} ({model_name})...")
    client = OpenAI(api_key=api_key or "ollama", base_url=base_url, timeout=45.0)
    schema_json = json.dumps(response_schema.model_json_schema(), ensure_ascii=False)
    full_system = (
        f"{system_prompt}\n\n"
        f"DEBES responder ÚNICAMENTE con un objeto JSON válido que cumpla exactamente este JSON Schema:\n{schema_json}"
    )

    completion = client.chat.completions.create(
        model=model_name,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw_text = completion.choices[0].message.content or "{}"
    cleaned = _extract_json_block(raw_text)
    parsed = response_schema.model_validate_json(cleaned)
    return parsed, json.loads(cleaned)


def build_offline_heuristic_evaluation(
    lab_title: str,
    ai_topics: list[str],
    criteria: list[RubricCriterion],
    pdf_text: str,
    code_snippets: str,
    sandbox: SandboxVerificationResult,
) -> tuple[EvaluationAIResponse, dict]:
    """
    Transparent fallback used ONLY when no LLM API key is configured yet.
    Uses real sandbox verification + document coverage signals to produce a valid
    Pydantic EvaluationAIResponse so the user can test every workflow locally.
    """
    pdf_words = len(pdf_text.split())
    has_good_pdf = pdf_words >= 80
    has_code = len(sandbox.files_analyzed) > 0
    doc_ratio = 0.88 if pdf_words >= 200 else (0.76 if has_good_pdf else 0.5)
    tech_ratio = min(1.0, max(0.35, sandbox.technical_score_hint / 5.0)) if has_code else doc_ratio

    criteria_evals: list[CriterionEvaluationAI] = []
    for crit in criteria:
        is_code_crit = any(
            kw in (crit.name + " " + crit.competency).lower()
            for kw in ("código", "codigo", "implementa", "prueba", "test", "calidad", "algoritmo", "modelo")
        )
        ratio = round(tech_ratio if is_code_crit else (doc_ratio * 0.6 + tech_ratio * 0.4), 2)
        ratio = min(1.0, max(0.25, ratio))

        if ratio >= 0.9:
            level = "excelente"
        elif ratio >= 0.75:
            level = "sobresaliente"
        elif ratio >= 0.6:
            level = "aceptable"
        else:
            level = "insuficiente"

        evidences = []
        if sandbox.files_analyzed:
            evidences.append(
                f"Código analizado ({sandbox.total_lines_of_code} líneas en {len(sandbox.files_analyzed)} archivos): {', '.join(sandbox.files_analyzed[:3])}."
            )
        if sandbox.unit_tests_found:
            evidences.append(
                f"Pruebas unitarias en sandbox ({sandbox.sandbox_mode}, red bloqueada): {sandbox.unit_tests_passed} aprobadas, {sandbox.unit_tests_failed} fallidas."
            )
        if pdf_text.strip():
            excerpt = " ".join(pdf_text.split()[:28])
            evidences.append(f'Extracto del informe PDF ({pdf_words} palabras): "{excerpt}..."')
        if not evidences:
            evidences.append("Evidencia mínima detectada en la entrega cargada.")

        criteria_evals.append(
            CriterionEvaluationAI(
                criterion_id=crit.id,
                criterion_name=crit.name,
                competency=crit.competency,
                level_achieved=level,
                score_ratio=ratio,
                evidences=evidences,
                justification=(
                    f"Evaluación basada en verificación técnica objetiva (sintaxis {'OK' if sandbox.syntax_ok else 'con errores'}, "
                    f"{sandbox.static_issues_count} hallazgos estáticos) y análisis del informe PDF ({pdf_words} palabras). "
                    f"Configura tu GEMINI_API_KEY en Configuración IA para obtener análisis semántico profundo multimodal."
                ),
            )
        )

    topics = ai_topics or ["Fundamentos de IA", "Implementación Técnica"]
    competencies: list[CompetencyAssessmentAI] = []
    avg_ratio = sum(c.score_ratio for c in criteria_evals) / max(1, len(criteria_evals))
    score_5 = round(avg_ratio * 5.0, 2)
    mastery = (
        "avanzado" if score_5 >= 4.3 else
        "intermedio" if score_5 >= 3.5 else
        "basico" if score_5 >= 2.8 else
        "por_fortalecer"
    )
    for topic in topics:
        competencies.append(
            CompetencyAssessmentAI(
                topic=topic,
                category="Inteligencia Artificial Aplicada",
                mastery_level=mastery,
                mastery_score=score_5,
                evidence=f"Aplicado en '{lab_title}' con {sandbox.total_lines_of_code} líneas de código y {sandbox.unit_tests_passed} pruebas aprobadas.",
                needs_deepening=(
                    ["Ampliar cobertura de pruebas unitarias y casos borde."]
                    if sandbox.unit_tests_failed > 0 or not sandbox.unit_tests_found
                    else ["Profundizar en análisis comparativo de hiperparámetros y métricas."]
                ),
            )
        )

    strengths = [
        f"Entrega estructurada con informe PDF legible ({pdf_words} palabras) y código fuente verificable.",
        f"Verificación de sintaxis Python: {'sin errores' if sandbox.syntax_ok else 'requiere corrección'}.",
    ]
    if sandbox.unit_tests_passed > 0:
        strengths.append(f"Incluye pruebas unitarias automatizadas ({sandbox.unit_tests_passed} pruebas pasaron en sandbox).")

    weaknesses = []
    if sandbox.static_issues_count > 0:
        weaknesses.append(f"El análisis estático (ruff) detectó {sandbox.static_issues_count} advertencias de estilo o calidad.")
    if not sandbox.unit_tests_found:
        weaknesses.append("No se incluyeron pruebas unitarias (test_*.py) para validar automáticamente la solución.")
    if sandbox.unit_tests_failed > 0:
        weaknesses.append(f"Fallaron {sandbox.unit_tests_failed} pruebas unitarias durante la ejecución aislada.")
    if not weaknesses:
        weaknesses.append("Se recomienda enriquecer la discusión crítica de limitaciones del enfoque implementado.")

    recommendations = [
        "Configura tu API Key gratuita de Google Gemini en la pestaña 'Configuración IA' para habilitar evaluación semántica y multimodal completa.",
        "Agrega pruebas unitarias que cubran casos límite y valida el código con `ruff check` antes de entregar.",
        "Relaciona explícitamente cada métrica del informe PDF con las funciones implementadas en el código fuente.",
    ]

    result = EvaluationAIResponse(
        summary=(
            f"Evaluación preliminar en modo respaldo local para '{lab_title}'. "
            f"Se analizaron {len(sandbox.files_analyzed)} archivos de código y el informe documental ({pdf_words} palabras). "
            f"Puedes volver a ejecutar 'Re-evaluar' para obtener el análisis semántico completo de IA."
        ),
        what_student_learned=(
            f"El estudiante evidencia aplicación práctica de {', '.join(topics)} mediante código estructurado "
            f"y documentación técnica en el informe del laboratorio."
        ),
        how_applied_knowledge=(
            f"Implementó {sandbox.total_lines_of_code} líneas de código con validación técnica "
            f"({sandbox.unit_tests_passed} pruebas aprobadas, {sandbox.static_issues_count} alertas estáticas) "
            f"respaldadas por un informe de {pdf_words} palabras."
        ),
        criteria_evaluations=criteria_evals,
        strengths=strengths,
        weaknesses=weaknesses,
        recommendations=recommendations,
        competencies=competencies,
    )
    return result, result.model_dump()
