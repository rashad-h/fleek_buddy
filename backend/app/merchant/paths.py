"""Resolve Vision tooling paths for host and Docker layouts."""

from __future__ import annotations

import os
from pathlib import Path


def _env_path(name: str) -> Path | None:
    raw = (os.getenv(name) or "").strip()
    return Path(raw) if raw else None


def repo_root() -> Path:
    override = _env_path("REPO_ROOT")
    if override is not None:
        return override
    # Host layout: <repo>/backend/app/merchant/paths.py → parents[3] = <repo>
    here = Path(__file__).resolve()
    candidate = here.parents[3]
    if (candidate / "Vision" / "pySceneDetect").is_dir():
        return candidate
    # Docker layout is /app/app/... — Vision is not in the image. Callers should
    # use make dev-backend-host (or set VISION_ROOT / REPO_ROOT).
    return candidate


def vision_root() -> Path:
    override = _env_path("VISION_ROOT")
    if override is not None:
        return override
    return repo_root() / "Vision"


def pyscene_dir() -> Path:
    return vision_root() / "pySceneDetect"


def vlm_dir() -> Path:
    return vision_root() / "vlm"


def sample_video_dir() -> Path:
    return vision_root() / "sample_video"


def require_extract_script() -> Path:
    """Return extract.py or raise a clear host-vs-Docker error."""
    script = pyscene_dir() / "extract.py"
    if script.is_file():
        return script
    raise RuntimeError(
        f"Missing extractor: {script}. "
        "Merchant video processing needs the host API "
        "(make setup-vision-envs && make dev-backend-host), "
        "not the Docker backend."
    )


def jobs_root() -> Path:
    override = _env_path("MERCHANT_JOBS_DIR")
    if override is not None:
        return override
    return Path(__file__).resolve().parents[2] / "data" / "merchant_jobs"


def python_for(venv_dir: Path, *, label: str) -> str:
    candidate = venv_dir / ".venv" / "bin" / "python"
    if candidate.is_file():
        return str(candidate)
    setup_hint = f"cd {venv_dir} && ./setup_env.sh" if label == "vlm" else f"cd {venv_dir} && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    raise RuntimeError(
        f"Missing {label} virtualenv at {venv_dir}/.venv. Run: {setup_hint}"
    )
