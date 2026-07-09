#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ACE_ROOT="${PROMPT2MIDI_ACE_STEP_ROOT:-$ROOT/.cache/ace-step/ACE-Step-1.5}"
PYTHON="${PYTHON:-/opt/homebrew/opt/python@3.11/bin/python3.11}"

mkdir -p "$(dirname "$ACE_ROOT")"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it first, then rerun npm run setup:ace-step." >&2
  exit 1
fi

if ! "$PYTHON" --version >/dev/null 2>&1; then
  echo "Python 3.11 not found at $PYTHON. Set PYTHON=/path/to/python3.11 and retry." >&2
  exit 1
fi

if [ ! -d "$ACE_ROOT/.git" ]; then
  git clone https://github.com/ace-step/ACE-Step-1.5.git "$ACE_ROOT"
fi

cd "$ACE_ROOT"
git fetch --depth 1 origin main
git checkout main
git pull --ff-only origin main

PATCH="$ROOT/scripts/setup/patches/ace-step-use-mlx-dit-env.patch"
PATCH_TARGET="$ACE_ROOT/acestep/core/generation/handler/init_service_orchestrator.py"
if [ -f "$PATCH" ] && ! grep -q "ACESTEP_USE_MLX_DIT" "$PATCH_TARGET"; then
  git apply "$PATCH"
  echo "Applied prompt2midi ACE-Step patch: ACESTEP_USE_MLX_DIT env override"
fi

uv sync --python "$PYTHON"

echo "ACE-Step engine ready at $ACE_ROOT"
echo "Start it with: npm run ace-step:start"
