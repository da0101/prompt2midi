#!/usr/bin/env python3
"""CLI bridge called by the local Node orchestrator."""

from __future__ import annotations

import argparse
import json
import os
import sys

from feature_extraction import AnalysisError, analyze_wav
from midi_extraction import write_bassline_midi


def run(audio_path: str, output_dir: str) -> dict:
    analysis = analyze_wav(audio_path)
    midi_path = write_bassline_midi(
        os.path.join(output_dir, "bassline.mid"),
        key=analysis.get("key") or "C major",
        bpm=analysis.get("bpm") or 120.0,
    )
    return {
        "ok": True,
        "analysis": analysis,
        "midi_files": {"bass": midi_path},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run prompt2midi local analysis.")
    parser.add_argument("--audio", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        payload = run(args.audio, args.output_dir)
    except AnalysisError as exc:
        payload = {"ok": False, "error": {"code": exc.code, "message": exc.message}}
    except Exception as exc:  # Defensive boundary for the Node bridge.
        payload = {"ok": False, "error": {"code": "analysis_failed", "message": str(exc)}}

    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True))
    sys.stdout.write("\n")
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
