import time
from threading import Lock

_LOCK = Lock()
_PROGRESS: dict[int, dict] = {}

DEFAULT_STEPS = [
    {"id": "pdf", "label": "1. Leyendo informe técnico (PDF/DOCX)"},
    {"id": "sandbox", "label": "2. Verificación objetiva de código en Sandbox"},
    {"id": "ai", "label": "3. Analizando evidencias con modelo de IA"},
    {"id": "grade", "label": "4. Cálculo de nota en Backend y trazabilidad"},
]


def start_progress(submission_id: int, lab_label: str) -> None:
    with _LOCK:
        _PROGRESS[submission_id] = {
            "submission_id": submission_id,
            "lab_label": lab_label,
            "status": "running",
            "percent": 5,
            "current_step_id": "pdf",
            "detail": "Iniciando pipeline de evaluación...",
            "started_at": time.time(),
            "steps": [
                {**s, "state": "active" if idx == 0 else "pending", "note": ""}
                for idx, s in enumerate(DEFAULT_STEPS)
            ],
        }


def update_progress(submission_id: int, step_id: str, percent: int, detail: str, note: str = "") -> None:
    with _LOCK:
        entry = _PROGRESS.get(submission_id)
        if not entry:
            return
        entry["percent"] = max(entry["percent"], min(99, percent))
        entry["current_step_id"] = step_id
        entry["detail"] = detail

        found_current = False
        for step in entry["steps"]:
            if step["id"] == step_id:
                step["state"] = "active"
                if note:
                    step["note"] = note
                found_current = True
            elif not found_current:
                step["state"] = "done"
            else:
                step["state"] = "pending"


def finish_progress(submission_id: int, detail: str = "Evaluación completada.", error: bool = False) -> None:
    with _LOCK:
        entry = _PROGRESS.get(submission_id)
        if not entry:
            return
        entry["status"] = "error" if error else "done"
        entry["percent"] = 100 if not error else entry["percent"]
        entry["detail"] = detail
        if not error:
            for step in entry["steps"]:
                step["state"] = "done"


def get_progress(submission_id: int) -> dict:
    with _LOCK:
        entry = _PROGRESS.get(submission_id)
        if not entry:
            return {
                "submission_id": submission_id,
                "status": "idle",
                "percent": 0,
                "detail": "Preparando evaluación...",
                "elapsed_seconds": 0,
                "steps": [{**s, "state": "pending", "note": ""} for s in DEFAULT_STEPS],
            }
        elapsed = int(time.time() - entry["started_at"])
        return {
            **entry,
            "elapsed_seconds": elapsed,
            "steps": [dict(s) for s in entry["steps"]],
        }
