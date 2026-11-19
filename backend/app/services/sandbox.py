import ast
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from app.config import get_settings
from app.schemas import SandboxVerificationResult

settings = get_settings()

# Injected into PYTHONPATH when executing student pytest suites in subprocess sandbox mode.
# Blocks outbound/inbound network sockets by default as required by Engineering Condition #3.
NETWORK_BLOCK_SITECUSTOMIZE = """
import socket

class _SandboxNetworkBlockedError(PermissionError):
    pass

def _blocked_network(*args, **kwargs):
    raise _SandboxNetworkBlockedError("Acceso a red bloqueado por el sandbox de evaluación.")

socket.socket.connect = _blocked_network
socket.socket.connect_ex = _blocked_network
socket.create_connection = _blocked_network
socket.getaddrinfo = _blocked_network
"""


def _check_python_syntax(py_files: list[Path], root_dir: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    for path in py_files:
        rel = str(path.relative_to(root_dir)).replace("\\", "/")
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            ast.parse(source, filename=rel)
        except SyntaxError as exc:
            errors.append(f"{rel}:{exc.lineno}: {exc.msg}")
        except Exception as exc:
            errors.append(f"{rel}: {exc}")
    return len(errors) == 0, errors


def _run_ruff_static_analysis(root_dir: Path, timeout: int) -> tuple[int, list[str]]:
    ruff_bin = shutil.which("ruff") or str(Path(sys.executable).parent / ("ruff.exe" if os.name == "nt" else "ruff"))
    if not Path(ruff_bin).exists() and shutil.which("ruff") is None:
        return 0, []

    try:
        proc = subprocess.run(
            [ruff_bin, "check", "--no-fix", "--output-format", "concise", str(root_dir)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(root_dir),
            env={"PATH": os.environ.get("PATH", ""), "HOME": str(root_dir)},
        )
        lines = [
            line.strip()
            for line in proc.stdout.splitlines()
            if line.strip()
            and not line.startswith("Found ")
            and not line.startswith("[*]")
            and line.strip() != "All checks passed!"
        ]
        # Clean absolute path prefix for readable reports
        cleaned = [line.replace(str(root_dir) + os.sep, "").replace(str(root_dir) + "/", "") for line in lines]
        return len(cleaned), cleaned[:25]
    except subprocess.TimeoutExpired:
        return 1, ["El análisis estático (ruff) excedió el tiempo límite."]
    except Exception as exc:
        return 0, [f"Análisis estático omitido: {exc}"]


def _linux_preexec_limits(memory_mb: int, timeout_seconds: int):
    def _apply():
        try:
            import resource
            mem_bytes = memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
            resource.setrlimit(resource.RLIMIT_CPU, (timeout_seconds, timeout_seconds))
            resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))
        except Exception:
            pass
    return _apply


def _parse_pytest_counts(output: str) -> tuple[int, int]:
    passed_match = re.search(r"(\d+)\s+passed", output)
    failed_match = re.search(r"(\d+)\s+(?:failed|error)", output)
    passed = int(passed_match.group(1)) if passed_match else 0
    failed = int(failed_match.group(1)) if failed_match else 0
    return passed, failed


def _run_pytest_docker(root_dir: Path, timeout: int, memory_mb: int) -> tuple[int, int, str]:
    cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", f"{memory_mb}m",
        "--cpus", "0.5",
        "--pids-limit", "64",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=32m",
        "-v", f"{root_dir.resolve()}:/workspace:ro",
        "-w", "/workspace",
        "python:3.12-slim",
        "python", "-m", "pytest", "-q", "--tb=short", "-o", "cache_dir=/tmp/pytest_cache",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        out = (proc.stdout + "\n" + proc.stderr).strip()
        passed, failed = _parse_pytest_counts(out)
        return passed, failed, out[:2000]
    except subprocess.TimeoutExpired:
        return 0, 1, f"Ejecución en sandbox Docker cancelada por timeout ({timeout}s)."
    except Exception as exc:
        return 0, 1, f"Error en sandbox Docker: {exc}"


def _run_pytest_subprocess(root_dir: Path, timeout: int, memory_mb: int) -> tuple[int, int, str]:
    guard_dir = Path(tempfile.mkdtemp(prefix="sandbox_guard_"))
    try:
        (guard_dir / "sitecustomize.py").write_text(NETWORK_BLOCK_SITECUSTOMIZE, encoding="utf-8")

        safe_env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": f"{guard_dir}{os.pathsep}{root_dir}",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "HOME": str(root_dir),
            "TMP": str(guard_dir),
            "TEMP": str(guard_dir),
            "NO_PROXY": "*",
            "HTTP_PROXY": "http://127.0.0.1:0",
            "HTTPS_PROXY": "http://127.0.0.1:0",
        }
        if os.name == "nt":
            safe_env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")

        kwargs: dict = {
            "capture_output": True,
            "text": True,
            "timeout": timeout,
            "cwd": str(root_dir),
            "env": safe_env,
        }
        if platform.system() == "Linux":
            kwargs["preexec_fn"] = _linux_preexec_limits(memory_mb, timeout)

        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-p", "no:anyio", "-q", "--tb=short", "-o", f"cache_dir={guard_dir / 'cache'}"],
            **kwargs,
        )
        out = (proc.stdout + "\n" + proc.stderr).strip()
        passed, failed = _parse_pytest_counts(out)
        if proc.returncode != 0 and passed == 0 and failed == 0:
            failed = 1
        return passed, failed, out[:2000]
    except subprocess.TimeoutExpired:
        return 0, 1, f"Ejecución cancelada por exceder el tiempo máximo del sandbox ({timeout}s)."
    except Exception as exc:
        return 0, 1, f"Error al ejecutar pruebas en sandbox: {exc}"
    finally:
        shutil.rmtree(guard_dir, ignore_errors=True)


def verify_code_in_sandbox(code_dir: Path, files_analyzed: list[str], total_loc: int) -> SandboxVerificationResult:
    """
    Objective technical verification pipeline:
    1. Python AST syntax validation
    2. Static code analysis (ruff)
    3. Unit test execution (pytest) inside isolated sandbox (no network, resource & time limits)
    """
    start = time.perf_counter()
    timeout = settings.SANDBOX_TIMEOUT_SECONDS
    memory_mb = settings.SANDBOX_MEMORY_MB
    mode = settings.SANDBOX_MODE

    py_files = [
        p for p in code_dir.rglob("*.py")
        if "__pycache__" not in p.parts and ".venv" not in p.parts
    ]

    syntax_ok, syntax_errors = _check_python_syntax(py_files, code_dir)
    static_count, static_issues = _run_ruff_static_analysis(code_dir, timeout) if py_files else (0, [])

    test_files = [p for p in py_files if p.name.startswith("test_") or p.name.endswith("_test.py")]
    unit_tests_found = len(test_files) > 0
    passed, failed, test_output = 0, 0, "No se encontraron archivos de pruebas unitarias (test_*.py)."

    if unit_tests_found and syntax_ok:
        if mode == "docker" and shutil.which("docker"):
            passed, failed, test_output = _run_pytest_docker(code_dir, timeout, memory_mb)
        else:
            mode = "subprocess"
            passed, failed, test_output = _run_pytest_subprocess(code_dir, timeout, memory_mb)
    elif unit_tests_found and not syntax_ok:
        failed = len(test_files)
        test_output = "Pruebas omitidas debido a errores de sintaxis en el código entregado."

    # Objective technical score hint (0.0 to 5.0) to guide transparent verification
    score = 0.0
    if py_files or files_analyzed:
        score += 1.5 if syntax_ok else 0.3
        if static_count == 0:
            score += 1.5
        elif static_count <= 5:
            score += 1.0
        elif static_count <= 15:
            score += 0.6
        else:
            score += 0.3

        if unit_tests_found:
            total_tests = passed + failed
            if total_tests > 0:
                score += round(2.0 * (passed / total_tests), 2)
        else:
            score += 0.8  # partial credit when no unit tests included

    elapsed_ms = int((time.perf_counter() - start) * 1000)

    return SandboxVerificationResult(
        sandbox_mode=mode,
        network_blocked=True,
        timeout_seconds=timeout,
        memory_limit_mb=memory_mb,
        files_analyzed=files_analyzed[:40],
        total_lines_of_code=total_loc,
        syntax_ok=syntax_ok,
        syntax_errors=syntax_errors,
        static_issues_count=static_count,
        static_issues=static_issues,
        unit_tests_found=unit_tests_found,
        unit_tests_passed=passed,
        unit_tests_failed=failed,
        unit_tests_output=test_output,
        execution_time_ms=elapsed_ms,
        technical_score_hint=min(5.0, round(score, 2)),
    )
