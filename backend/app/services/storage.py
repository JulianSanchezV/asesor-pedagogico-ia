import os
import re
import uuid
from pathlib import Path
import httpx
from app.config import get_settings

settings = get_settings()


def _safe_filename(filename: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9._-]", "_", filename or "file")
    return f"{uuid.uuid4().hex[:10]}_{clean}"


def save_bytes(data: bytes, filename: str, subfolder: str = "general") -> str:
    """Persist uploaded bytes either to Supabase Storage (prod) or local disk (dev)."""
    safe_name = _safe_filename(filename)
    rel_key = f"{subfolder}/{safe_name}"

    if settings.STORAGE_MODE == "supabase" and settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY:
        url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/{settings.SUPABASE_BUCKET}/{rel_key}"
        headers = {
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
            "apikey": settings.SUPABASE_SERVICE_KEY,
            "Content-Type": "application/octet-stream",
            "x-upsert": "true",
        }
        resp = httpx.post(url, headers=headers, content=data, timeout=30.0)
        resp.raise_for_status()
        return f"supabase://{rel_key}"

    base_dir = Path(settings.LOCAL_UPLOAD_DIR).resolve()
    target = base_dir / subfolder / safe_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return str(target)


def load_bytes(storage_path: str) -> bytes:
    """Retrieve stored bytes from Supabase Storage or local filesystem."""
    if storage_path.startswith("supabase://"):
        rel_key = storage_path.replace("supabase://", "", 1)
        url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/{settings.SUPABASE_BUCKET}/{rel_key}"
        headers = {
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
            "apikey": settings.SUPABASE_SERVICE_KEY,
        }
        resp = httpx.get(url, headers=headers, timeout=30.0)
        resp.raise_for_status()
        return resp.content

    path = Path(storage_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado en almacenamiento: {storage_path}")
    return path.read_bytes()


def ensure_local_upload_dir() -> None:
    os.makedirs(settings.LOCAL_UPLOAD_DIR, exist_ok=True)
