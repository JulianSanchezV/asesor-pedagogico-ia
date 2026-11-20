import os
import re
import uuid
from pathlib import Path
import httpx
from app.config import get_settings
from app.database import SessionLocal
from app.models import StoredFile

settings = get_settings()


def _safe_filename(filename: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9._-]", "_", filename or "file")
    return f"{uuid.uuid4().hex[:10]}_{clean}"


def _supabase_headers(include_bearer: bool = True, content_type: str | None = None) -> dict[str, str]:
    key = settings.SUPABASE_SERVICE_KEY.strip()
    headers = {"apikey": key}
    if include_bearer:
        headers["Authorization"] = f"Bearer {key}"
    if content_type:
        headers["Content-Type"] = content_type
        headers["x-upsert"] = "true"
    return headers


def _save_to_postgres(data: bytes, filename: str) -> str:
    file_id = uuid.uuid4().hex
    db = SessionLocal()
    try:
        db.add(StoredFile(id=file_id, filename=filename or "file", content=data))
        db.commit()
        return f"db://{file_id}"
    finally:
        db.close()


def _load_from_postgres(file_id: str) -> bytes:
    db = SessionLocal()
    try:
        row = db.query(StoredFile).filter(StoredFile.id == file_id).first()
        if not row:
            raise FileNotFoundError(f"Archivo no encontrado en base de datos: {file_id}")
        return bytes(row.content)
    finally:
        db.close()


def save_bytes(data: bytes, filename: str, subfolder: str = "general") -> str:
    """
    Persist uploaded bytes:
    - In 'supabase' mode: tries Supabase Storage first (both header variants),
      and automatically falls back to persistent PostgreSQL blob storage (db://)
      so uploads never fail with 500 even if bucket/key rules vary.
    - In 'local' mode: saves to local disk.
    """
    safe_name = _safe_filename(filename)
    rel_key = f"{subfolder}/{safe_name}"

    if settings.STORAGE_MODE == "supabase":
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY:
            url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/{settings.SUPABASE_BUCKET}/{rel_key}"
            key = settings.SUPABASE_SERVICE_KEY.strip()
            # Try preferred auth format first, then alternate format
            bearer_attempts = [False, True] if key.startswith("sb_") else [True, False]
            for use_bearer in bearer_attempts:
                try:
                    headers = _supabase_headers(
                        include_bearer=use_bearer, content_type="application/octet-stream"
                    )
                    resp = httpx.post(url, headers=headers, content=data, timeout=25.0)
                    if resp.status_code in (200, 201):
                        return f"supabase://{rel_key}"
                except Exception:
                    continue
        # Persistent PostgreSQL fallback (survives Render restarts cleanly)
        return _save_to_postgres(data, filename)

    base_dir = Path(settings.LOCAL_UPLOAD_DIR).resolve()
    target = base_dir / subfolder / safe_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return str(target)


def load_bytes(storage_path: str) -> bytes:
    """Retrieve stored bytes from PostgreSQL fallback, Supabase Storage, or local filesystem."""
    if storage_path.startswith("db://"):
        return _load_from_postgres(storage_path.replace("db://", "", 1))

    if storage_path.startswith("supabase://"):
        rel_key = storage_path.replace("supabase://", "", 1)
        url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/{settings.SUPABASE_BUCKET}/{rel_key}"
        key = settings.SUPABASE_SERVICE_KEY.strip()
        bearer_attempts = [False, True] if key.startswith("sb_") else [True, False]
        last_err = None
        for use_bearer in bearer_attempts:
            try:
                resp = httpx.get(url, headers=_supabase_headers(include_bearer=use_bearer), timeout=25.0)
                if resp.status_code == 200:
                    return resp.content
                last_err = f"HTTP {resp.status_code}: {resp.text[:160]}"
            except Exception as exc:
                last_err = str(exc)
        raise FileNotFoundError(f"No se pudo recuperar el archivo desde Supabase Storage ({last_err}).")

    path = Path(storage_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado en almacenamiento: {storage_path}")
    return path.read_bytes()


def ensure_local_upload_dir() -> None:
    os.makedirs(settings.LOCAL_UPLOAD_DIR, exist_ok=True)
