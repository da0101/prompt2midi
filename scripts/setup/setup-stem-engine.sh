#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${PROMPT2MIDI_STEM_PYTHON:-}"

if [[ -z "$PYTHON" ]]; then
  if command -v python3.10 >/dev/null 2>&1; then
    PYTHON="$(command -v python3.10)"
  elif command -v python3.11 >/dev/null 2>&1; then
    PYTHON="$(command -v python3.11)"
  else
    echo "Python 3.10 or 3.11 is required for the Demucs stem engine."
    exit 1
  fi
fi

cd "$ROOT"
uv venv --allow-existing --python "$PYTHON" .venv-stems
uv pip install --python .venv-stems/bin/python -r requirements/demucs.txt

echo "Stem engine ready at $ROOT/.venv-stems/bin/demucs"
