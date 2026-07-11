#!/usr/bin/env bash
# Create an isolated Python env for SAM 3 video (HF Transformers).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

export PATH="${HOME}/.local/bin:${PATH}"

if command -v uv >/dev/null 2>&1; then
  echo "Using uv"
  uv python install 3.12
  if [[ ! -d .venv ]]; then
    uv venv --python 3.12 .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  uv pip install -r requirements.txt
else
  PY=""
  for candidate in python3.12 python3.13 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      ver="$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
      major="${ver%%.*}"
      minor="${ver#*.}"
      if [[ "$major" -gt 3 || ( "$major" -eq 3 && "$minor" -ge 10 ) ]]; then
        PY="$candidate"
        break
      fi
    fi
  done

  if [[ -z "$PY" ]]; then
    echo "Need Python 3.10+ (3.12 recommended). Install uv (https://github.com/astral-sh/uv) or:"
    echo "  brew install python@3.12"
    exit 1
  fi

  echo "Using $PY ($("$PY" --version))"
  if [[ ! -d .venv ]]; then
    "$PY" -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install -U pip
  pip install -r requirements.txt
fi

echo
echo "Env ready: $ROOT/.venv"
echo "Next:"
echo "  1. hf auth login"
echo "  2. Accept license at https://huggingface.co/facebook/sam3 (403 = not approved yet)"
echo "  3. source .venv/bin/activate"
echo "  4. python run_video.py data/your_clip.mp4 --max-frames 50"
