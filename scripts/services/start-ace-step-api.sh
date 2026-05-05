#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ACE_ROOT="${PROMPT2MIDI_ACE_STEP_ROOT:-$ROOT/.cache/ace-step/ACE-Step-1.5}"

if [ ! -d "$ACE_ROOT" ]; then
  echo "ACE-Step is not installed at $ACE_ROOT. Run npm run setup:ace-step first." >&2
  exit 1
fi

cd "$ACE_ROOT"

export ACESTEP_API_HOST="${ACESTEP_API_HOST:-127.0.0.1}"
export ACESTEP_API_PORT="${ACESTEP_API_PORT:-8001}"
export ACESTEP_CONFIG_PATH="${ACESTEP_CONFIG_PATH:-acestep-v15-turbo}"
export ACESTEP_LM_MODEL_PATH="${ACESTEP_LM_MODEL_PATH:-acestep-5Hz-lm-0.6B}"
export ACESTEP_LM_BACKEND="${ACESTEP_LM_BACKEND:-mlx}"
export ACESTEP_DEVICE="${ACESTEP_DEVICE:-auto}"
export HF_HOME="${HF_HOME:-$ROOT/.cache/ace-step/huggingface}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$ROOT/.cache/ace-step/xdg}"

ARGS=(
  acestep-api
  --host "$ACESTEP_API_HOST"
  --port "$ACESTEP_API_PORT"
  --lm-model-path "$ACESTEP_LM_MODEL_PATH"
)

if [ "${ACESTEP_DOWNLOAD_SOURCE:-auto}" != "auto" ]; then
  ARGS+=(--download-source "$ACESTEP_DOWNLOAD_SOURCE")
fi

exec uv run "${ARGS[@]}"
