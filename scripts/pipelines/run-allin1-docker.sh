#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: scripts/pipelines/run-allin1-docker.sh <audio-path> <output-dir> [timeout-seconds]" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
AUDIO_PATH="$1"
OUTPUT_DIR="$2"
TIMEOUT_SECONDS="${3:-${PROMPT2MIDI_ALLIN1_DOCKER_TIMEOUT_SECONDS:-300}}"

absolute_file_path() {
  local path="$1"
  if [[ "$path" != /* ]]; then
    path="${PWD}/${path}"
  fi
  local dir
  dir="$(cd "$(dirname "$path")" && pwd)"
  printf '%s/%s' "$dir" "$(basename "$path")"
}

AUDIO_ABS="$(absolute_file_path "$AUDIO_PATH")"
mkdir -p "$OUTPUT_DIR"
OUTPUT_ABS="$(cd "$OUTPUT_DIR" && pwd)"
AUDIO_DIR="$(dirname "$AUDIO_ABS")"
AUDIO_FILE="$(basename "$AUDIO_ABS")"

cd "$REPO_ROOT"
docker compose run --rm \
  -v "$AUDIO_DIR:/input:ro" \
  -v "$OUTPUT_ABS:/job" \
  allin1-worker \
  python docker/allin1/run_allin1.py \
    --audio "/input/$AUDIO_FILE" \
    --output-dir /job \
    --timeout "$TIMEOUT_SECONDS"
