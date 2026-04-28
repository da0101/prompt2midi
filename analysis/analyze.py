#!/usr/bin/env python3
"""CLI bridge called by the local Node orchestrator."""

from __future__ import annotations

import argparse
import json
import os
import sys

from bass_transcription import transcribe_bassline
from feature_extraction import AnalysisError, analyze_wav
from midi_extraction import write_note_events_midi, write_reference_sketch_midi
from source_transcription import transcribe_with_model


def run(audio_path: str, output_dir: str) -> dict:
    analysis = analyze_wav(audio_path)
    os.makedirs(output_dir, exist_ok=True)

    sketch_path = write_reference_sketch_midi(
        os.path.join(output_dir, "reference-sketch.mid"),
        key=analysis.get("key") or "C major",
        bpm=analysis.get("bpm") or 120.0,
    )
    bass = transcribe_bassline(audio_path, analysis.get("bpm"))
    midi_files = {"reference_sketch": sketch_path}
    midi_assets = [
        {
            "key": "reference_sketch",
            "path": sketch_path,
            "label": "Generated reference sketch",
            "kind": "generated_sketch",
            "is_transcription": False,
            "source_method": "estimated_bpm_key_pattern",
            "confidence": min(float(analysis.get("bpm_confidence") or 0), float(analysis.get("key_confidence") or 0)),
            "limitations": ["Generated from estimated BPM/key only; not transcribed from the track."],
        }
    ]

    model = transcribe_with_model(audio_path, output_dir, analysis.get("bpm"))
    for track in model["tracks"]:
        midi_files[track["key"]] = track["path"]
        midi_assets.append(
            {
                "key": track["key"],
                "path": track["path"],
                "label": track["label"],
                "kind": "model_transcription",
                "is_transcription": True,
                "source_method": model["method"],
                "confidence": track["confidence"],
                "note_count": track["note_count"],
                "limitations": track["limitations"],
            }
        )

    if bass["events"]:
        midi_files["bass_transcription"] = write_note_events_midi(
            os.path.join(output_dir, "bass-transcription.mid"),
            bass["events"],
            bpm=analysis.get("bpm") or 120.0,
        )
        midi_assets.append(
            {
                "key": "bass_transcription",
                "path": midi_files["bass_transcription"],
                "label": "Experimental heuristic bass MIDI",
                "kind": "heuristic_transcription",
                "is_transcription": False,
                "source_method": "full_mix_low_frequency_tracking",
                "confidence": bass["confidence"],
                "note_count": len(bass["events"]),
                "limitations": bass["warnings"],
            }
        )

    analysis["bass_transcription"] = {
        "event_count": len(bass["events"]),
        "confidence": bass["confidence"],
        "warnings": bass["warnings"],
        "method": "full_mix_low_frequency_tracking",
    }
    analysis["model_transcription"] = {
        "available": model["available"],
        "method": model["method"],
        "track_count": len(model["tracks"]),
        "warnings": model["warnings"],
    }
    return {
        "ok": True,
        "analysis": analysis,
        "midi_files": midi_files,
        "midi_assets": midi_assets,
        "midi_notes": [
            "reference-sketch.mid is generated from estimated BPM/key only.",
            "model-transcription.mid is produced by Basic Pitch when the local engine is installed.",
            "model-bass-transcription.mid is pitch-filtered model output, not source-separated bass.",
            "bass-transcription.mid is legacy experimental monophonic low-frequency tracking when present.",
        ],
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
