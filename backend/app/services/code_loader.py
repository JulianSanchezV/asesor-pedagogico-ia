import io
import re
import zipfile
from pathlib import Path
import httpx

ALLOWED_CODE_EXTENSIONS = {
    ".py", ".ipynb", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".java", ".cpp", ".c", ".h",
    ".json", ".yaml", ".yml", ".toml", ".md", ".txt", ".sql", ".sh", ".r",
}
IGNORED_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", ".pytest_cache"}
MAX_ZIP_BYTES = 15 * 1024 * 1024  # 15 MB safety limit
MAX_FILES = 150


def safe_extract_zip(zip_bytes: bytes, dest_dir: Path) -> list[Path]:
    """Extract ZIP safely protecting against zip-slip path traversal and oversized archives."""
    if len(zip_bytes) > MAX_ZIP_BYTES:
        raise ValueError("El archivo ZIP supera el límite permitido de 15 MB.")

    dest_resolved = dest_dir.resolve()
    extracted_files: list[Path] = []

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > MAX_FILES:
            infos = infos[:MAX_FILES]

        for info in infos:
            parts = Path(info.filename).parts
            if any(p in IGNORED_DIRS or p.startswith("..") for p in parts):
                continue
            target = (dest_resolved / info.filename).resolve()
            if not str(target).startswith(str(dest_resolved)):
                raise ValueError("Archivo ZIP inválido: intento de path traversal detectado.")
            if info.file_size > 2 * 1024 * 1024:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                dst.write(src.read())
            extracted_files.append(target)

    return extracted_files


def _github_zip_urls(repo_url: str) -> list[str]:
    clean = repo_url.strip().rstrip("/")
    clean = re.sub(r"\.git$", "", clean)
    match = re.match(r"^https?://github\.com/([^/]+)/([^/]+)", clean)
    if not match:
        raise ValueError("La URL de GitHub debe tener el formato https://github.com/usuario/repositorio")
    owner, repo = match.group(1), match.group(2)
    return [
        f"https://api.github.com/repos/{owner}/{repo}/zipball/main",
        f"https://api.github.com/repos/{owner}/{repo}/zipball/master",
        f"https://github.com/{owner}/{repo}/archive/refs/heads/main.zip",
        f"https://github.com/{owner}/{repo}/archive/refs/heads/master.zip",
    ]


def download_github_repo_zip(repo_url: str) -> bytes:
    """Download public GitHub repository as ZIP."""
    last_err = None
    for url in _github_zip_urls(repo_url):
        try:
            resp = httpx.get(url, follow_redirects=True, timeout=25.0, headers={"User-Agent": "AsesorPedagogicoIA/1.0"})
            if resp.status_code == 200 and len(resp.content) > 100:
                return resp.content
        except Exception as exc:
            last_err = exc
    raise ValueError(
        f"No se pudo descargar el repositorio público de GitHub ({repo_url}). Verifica que sea público y exista. Detalle: {last_err}"
    )


def collect_code_snippets(root_dir: Path, max_total_chars: int = 24000) -> tuple[list[str], str, int]:
    """Read source files for AI analysis and return (relative_paths, combined_snippet, total_loc)."""
    rel_paths: list[str] = []
    chunks: list[str] = []
    total_loc = 0
    used_chars = 0

    all_files = sorted(p for p in root_dir.rglob("*") if p.is_file())
    for file_path in all_files:
        if any(part in IGNORED_DIRS for part in file_path.parts):
            continue
        if file_path.suffix.lower() not in ALLOWED_CODE_EXTENSIONS:
            continue

        rel = str(file_path.relative_to(root_dir)).replace("\\", "/")
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        loc = len(content.splitlines())
        total_loc += loc
        rel_paths.append(rel)

        if used_chars < max_total_chars:
            header = f"\n### Archivo: {rel} ({loc} líneas)\n"
            remaining = max_total_chars - used_chars - len(header)
            if remaining > 200:
                snippet = content[:remaining]
                chunks.append(header + snippet)
                used_chars += len(header) + len(snippet)

    return rel_paths, "\n".join(chunks), total_loc
