#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="$ROOT/Builds/MacOSX/prompt2midi.xcodeproj"
DERIVED_DATA="$ROOT/Builds/DerivedData"
APP="$ROOT/Builds/MacOSX/build/Debug/prompt2midi.app"
SCHEME="${PROMPT2MIDI_SCHEME:-prompt2midi - All}"

if pgrep -x "prompt2midi" >/dev/null 2>&1; then
  echo "Quitting open prompt2midi app..."
  osascript -e 'tell application "prompt2midi" to quit' >/dev/null 2>&1 || true
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

echo "Opening $APP..."
open "$APP"

