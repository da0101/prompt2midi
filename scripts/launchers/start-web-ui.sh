#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

echo "Starting Vue web UI at http://127.0.0.1:${PROMPT2MIDI_WEB_PORT:-5173}"
exec npm run dev --prefix web -- --host 127.0.0.1 --port "${PROMPT2MIDI_WEB_PORT:-5173}"
