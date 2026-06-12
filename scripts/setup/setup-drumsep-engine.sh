#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${PROMPT2MIDI_DRUMSEP_PYTHON:-}"

if [[ -z "$PYTHON" ]]; then
  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON="$(command -v python3.11)"
  elif command -v python3.10 >/dev/null 2>&1; then
    PYTHON="$(command -v python3.10)"
  else
    echo "Python 3.10 or 3.11 is required for the DrumSep engine."
    exit 1
  fi
fi

cd "$ROOT"
uv venv --allow-existing --python "$PYTHON" .venv-drumsep
uv pip install --python .venv-drumsep/bin/python -r requirements/drumsep.txt

cat > .venv-drumsep/bin/prompt2midi-drumsep <<SH
#!/usr/bin/env bash
set -euo pipefail
ROOT="$ROOT"
cd "\$ROOT"
exec "\$ROOT/.venv-drumsep/bin/python" -m analysis.drums.drumsep_onnx_runner "\$@"
SH
chmod +x .venv-drumsep/bin/prompt2midi-drumsep

echo "DrumSep dependencies installed at $ROOT/.venv-drumsep"
echo "Model target: https://huggingface.co/splitzo/drumsep"
echo "Runner installed at $ROOT/.venv-drumsep/bin/prompt2midi-drumsep"
