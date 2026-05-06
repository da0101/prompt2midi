#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

export PROMPT2MIDI_ACE_PROXY_AUTOSTART="${PROMPT2MIDI_ACE_PROXY_AUTOSTART:-0}"

echo "Starting ACE proxy API at http://127.0.0.1:${PROMPT2MIDI_ACE_UI_PORT:-47322}"
if [ "$PROMPT2MIDI_ACE_PROXY_AUTOSTART" = "0" ]; then
  echo "ACE-Step auto-start is disabled. Start scripts/launchers/start-ace-step-model-api.sh in another terminal."
fi
exec node --env-file=.env scripts/dev/ace-proxy-ui.js
