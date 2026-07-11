"""Load Gemini / VLM API keys for merchant Vision subprocesses."""

from __future__ import annotations

import os
from pathlib import Path

from app.merchant.paths import repo_root, vlm_dir


def parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, raw = stripped.partition("=")
        key = key.strip()
        value = raw.strip().strip('"').strip("'")
        # Paste from browsers/docs often includes zero-width chars that break HTTP headers.
        value = "".join(ch for ch in value if ch.isascii() and not ch.isspace())
        if key and value:
            values[key] = value
    return values


def vlm_subprocess_env() -> dict[str, str]:
    """Merge VLM env files; root .env wins over empty Vision/vlm/.env placeholders."""
    env = os.environ.copy()
    merged = parse_env_file(vlm_dir() / ".env")
    merged.update(parse_env_file(repo_root() / ".env"))
    for key, value in merged.items():
        env[key] = value
    return env
