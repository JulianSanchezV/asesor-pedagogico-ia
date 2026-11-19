from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.auth import get_current_user, require_teacher
from app.config import get_settings
from app.database import get_db
from app.models import AISettingsModel, User
from app.schemas import AISettingsOut, AISettingsUpdate
from app.services.ai_provider import PROVIDER_CATALOG, get_active_ai_config

router = APIRouter(prefix="/api/settings", tags=["Configuración de Modelos IA y Proyecto"])
settings = get_settings()


@router.get("/ai", response_model=AISettingsOut)
def get_ai_settings(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    cfg = get_active_ai_config(db)
    return AISettingsOut(
        provider=cfg["provider"],
        model_name=cfg["model_name"],
        base_url=cfg["base_url"],
        has_api_key=cfg["has_api_key"],
        sandbox_mode=settings.SANDBOX_MODE,
        available_providers=PROVIDER_CATALOG,
    )


@router.put("/ai", response_model=AISettingsOut)
def update_ai_settings(
    payload: AISettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    row = db.query(AISettingsModel).filter(AISettingsModel.id == 1).first()
    if not row:
        row = AISettingsModel(id=1)
        db.add(row)

    row.provider = payload.provider
    row.model_name = payload.model_name.strip()
    row.base_url = payload.base_url.strip()
    if payload.api_key_override.strip():
        row.api_key_override = payload.api_key_override.strip()

    db.commit()
    cfg = get_active_ai_config(db)
    return AISettingsOut(
        provider=cfg["provider"],
        model_name=cfg["model_name"],
        base_url=cfg["base_url"],
        has_api_key=cfg["has_api_key"],
        sandbox_mode=settings.SANDBOX_MODE,
        available_providers=PROVIDER_CATALOG,
    )


@router.get("/project-info")
def get_project_info():
    """Public metadata for Project Abstract & AI-Augmented Engineering documentation."""
    return {
        "project_name": "Asesor Pedagógico Inteligente",
        "institution": "Universidad de Manizales — Facultad de Ciencias e Ingeniería",
        "program": "Ingeniería de Sistemas y Telecomunicaciones (Profundización I - Inteligencia Artificial)",
        "abstract": (
            "Asesor Pedagógico Inteligente es una plataforma web diseñada para evaluar, retroalimentar y fortalecer "
            "las competencias adquiridas por estudiantes universitarios durante las Cohortes 1 y 2 de un curso de "
            "Inteligencia Artificial. Combina modelos de IA multimodales con salidas estructuradas validadas mediante "
            "Pydantic, cálculo determinista de calificaciones (0.0 a 5.0) en el backend, verificación objetiva del código "
            "fuente en un sandbox aislado (sintaxis AST, análisis estático con Ruff y pruebas unitarias Pytest sin acceso a red), "
            "flujo de trazabilidad y aprobación docente, un informe integral descargable en PDF y un mapa mental interactivo "
            "de competencias."
        ),
        "technologies": [
            {"layer": "Frontend", "stack": "React 19 + Vite + Tailwind CSS + React Flow + Recharts"},
            {"layer": "Backend", "stack": "Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy"},
            {"layer": "Inteligencia Artificial", "stack": "Google Gemini API (multimodal) + adaptador Groq / OpenRouter / Ollama"},
            {"layer": "Sandbox Técnico", "stack": "AST + Ruff + Pytest en entorno aislado sin red (Subprocess Linux / Docker)"},
            {"layer": "Datos y Despliegue", "stack": "PostgreSQL & Storage (Supabase) + Render + GitHub Pages"},
        ],
        "ai_engineering_log": [
            {
                "phase": "Análisis de Requisitos y Arquitectura",
                "tools": "Antigravity / Gemini",
                "contribution": "Descomposición del documento del reto en 7 funcionalidades obligatorias, 6 condiciones técnicas y modelo relacional con versionamiento de rúbricas.",
                "human_decision": "Separar Frontend estático (GitHub Pages) + Backend API (Render) + Supabase para lograr despliegue gratuito sin exponer claves API.",
            },
            {
                "phase": "Implementación Backend y Confiabilidad",
                "tools": "Antigravity / Asistentes de código IA",
                "contribution": "Generación de contratos estrictos Pydantic, pipeline determinista de notas y sandbox con bloqueo de sockets y límites de recursos.",
                "human_decision": "Prohibir cálculos libres del LLM para la nota final y conservar versiones inmutables de cada rúbrica y logs de auditoría docente.",
            },
            {
                "phase": "Interfaz Interactiva y Visualización",
                "tools": "Antigravity / React Flow / Recharts",
                "contribution": "Diseño del mapa mental interactivo exportable, dashboard de evolución entre cohortes y constructor de rúbricas con validación en vivo del 100%.",
                "human_decision": "Usar HashRouter en React para garantizar compatibilidad total con GitHub Pages sin errores 404.",
            },
        ],
    }
