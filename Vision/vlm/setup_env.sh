#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

export PATH="${HOME}/.local/bin:${PATH}"

if command -v uv >/dev/null 2>&1; then
  uv python install 3.12
  if [[ ! -d .venv ]]; then
    uv venv --python 3.12 .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  uv pip install -r requirements.txt
else
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install -U pip
  pip install -r requirements.txt
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env — add GEMINI_API_KEY or DASHSCOPE_API_KEY"
fi

echo
echo "Env ready: $ROOT/.venv"
echo "Next:"
echo "  1. Edit Vision/vlm/.env with an API key"
echo "  2. source .venv/bin/activate"
echo "  3. python describe_crops.py ../sam3/outputs/crops --limit 1"
