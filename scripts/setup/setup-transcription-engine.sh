#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${PROMPT2MIDI_BASIC_PITCH_PYTHON:-}"

if [[ -z "$PYTHON" ]]; then
  if command -v python3.10 >/dev/null 2>&1; then
    PYTHON="$(command -v python3.10)"
  elif command -v python3.11 >/dev/null 2>&1; then
    PYTHON="$(command -v python3.11)"
  else
    echo "Python 3.10 or 3.11 is required for Basic Pitch."
    exit 1
  fi
fi

cd "$ROOT"
uv venv --python "$PYTHON" .venv-basic-pitch
uv pip install --python .venv-basic-pitch/bin/python -r requirements/basic-pitch.txt

echo "Basic Pitch engine ready at $ROOT/.venv-basic-pitch/bin/basic-pitch"
