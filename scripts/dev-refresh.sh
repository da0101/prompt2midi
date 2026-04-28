#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="$ROOT/Builds/MacOSX/prompt2midi.xcodeproj"
DERIVED_DATA="$ROOT/Builds/DerivedData"
APP="$ROOT/Builds/MacOSX/build/Debug/prompt2midi.app"
SCHEME="${PROMPT2MIDI_SCHEME:-prompt2midi - All}"
PORT="${PROMPT2MIDI_PORT:-47321}"
SERVER_PID=""

cleanup() {
  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" >/dev/null 2>&1; then
    echo
    echo "Stopping backend..."
    kill "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

if pgrep -x "prompt2midi" >/dev/null 2>&1; then
  echo "Quitting open prompt2midi app..."
  osascript -e 'tell application "prompt2midi" to quit' >/dev/null 2>&1 || true
  sleep 1
fi

existing_pids="$(lsof -ti "tcp:$PORT" -sTCP:LISTEN 2>/dev/null || true)"
if [[ -n "$existing_pids" ]]; then
  echo "Stopping existing backend on port $PORT..."
  kill $existing_pids >/dev/null 2>&1 || true
  sleep 1
fi

echo "Building $SCHEME..."
xcodebuild \
  -project "$PROJECT" \
  -scheme "$SCHEME" \
  -configuration Debug \
  -derivedDataPath "$DERIVED_DATA" \
  CODE_SIGNING_ALLOWED=NO \
  build

echo "Starting backend on http://127.0.0.1:$PORT ..."
(
  cd "$ROOT"
  PROMPT2MIDI_PORT="$PORT" npm start
) &
SERVER_PID="$!"

sleep 1
if ! kill -0 "$SERVER_PID" >/dev/null 2>&1; then
  echo "Backend exited during startup."
  wait "$SERVER_PID"
fi

echo "Opening $APP..."
open "$APP"

echo
echo "Backend logs are live below. Press Ctrl-C here to stop the backend."
wait "$SERVER_PID"
