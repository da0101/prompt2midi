#!/usr/bin/env python3
"""Optional model-backed transcription using a local Basic Pitch engine."""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from midi_extraction import write_note_events_midi


@dataclass(frozen=True)
class ModelTrack:
    key: str
    path: str
    label: str
    note_count: int
    confidence: float
    limitations: list[str]


def transcribe_with_model(audio_path: str, output_dir: str, bpm: float | None) -> dict:
    if os.environ.get("PROMPT2MIDI_DISABLE_MODEL") == "1":
        return {
            "available": False,
            "method": "basic_pitch",
            "tracks": [],
            "warnings": ["Model transcription disabled by PROMPT2MIDI_DISABLE_MODEL."],
        }

    engine = _find_basic_pitch()
    limitations = [
        "Model transcription uses Basic Pitch on the supplied mix; best results come from isolated instruments.",
        "Review and correct MIDI by ear before using it as production material.",
    ]
    if engine is None:
        return {
            "available": False,
            "method": "basic_pitch",
            "tracks": [],
            "warnings": ["Basic Pitch engine not installed. Run npm run setup:transcription."],
        }

    model_dir = Path(output_dir) / "basic-pitch"
    runtime_dir = Path(output_dir) / "basic-pitch-runtime"
    model_dir.mkdir(parents=True, exist_ok=True)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    command = [
        engine,
        str(model_dir),
        audio_path,
        "--save-midi",
        "--save-note-events",
        "--midi-tempo",
        str(round(bpm or 120)),
        "--minimum-frequency",
        "35",
        "--maximum-frequency",
        "1200",
    ]
    env = os.environ.copy()
    env["TMPDIR"] = str(runtime_dir)
    try:
        completed = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parent.parent,
            env=env,
            text=True,
            capture_output=True,
            timeout=240,
        )
    except subprocess.TimeoutExpired:
        return {
            "available": False,
            "method": "basic_pitch",
            "tracks": [],
            "warnings": ["Basic Pitch timed out after 240 seconds."],
        }
    if completed.returncode != 0:
        return {
            "available": False,
            "method": "basic_pitch",
            "tracks": [],
            "warnings": ["Basic Pitch failed: " + _last_error(completed.stderr or completed.stdout)],
        }

    midi_path = _single_output(model_dir, ".mid")
    csv_path = _single_output(model_dir, ".csv")
    if midi_path is None or csv_path is None:
        return {
            "available": False,
            "method": "basic_pitch",
            "tracks": [],
            "warnings": ["Basic Pitch completed but did not produce MIDI and note-event outputs."],
        }

    notes = _read_note_events(csv_path)
    full_path = str(Path(output_dir) / "model-transcription.mid")
    shutil.copyfile(midi_path, full_path)

    tracks = [
        ModelTrack(
            key="model_transcription",
            path=os.path.abspath(full_path),
            label="Model MIDI transcription",
            note_count=len(notes),
            confidence=_confidence_from_notes(notes),
            limitations=limitations,
        )
    ]

    bass_notes = _extract_bassline(notes)
    if bass_notes:
        bass_path = write_note_events_midi(str(Path(output_dir) / "model-bass-transcription.mid"), bass_notes, bpm=bpm or 120)
        tracks.append(
            ModelTrack(
                key="model_bass_transcription",
                path=bass_path,
                label="Model-filtered bass MIDI",
                note_count=len(bass_notes),
                confidence=_confidence_from_notes(bass_notes),
                limitations=[
                    "Bass MIDI is filtered from model notes by pitch range; it is not stem-separated.",
                    "Dense guitars, vocals, or low percussion may still create false notes.",
                ],
            )
        )

    return {
        "available": True,
        "method": "basic_pitch_coreml",
        "tracks": [track.__dict__ for track in tracks],
        "warnings": limitations,
    }


def _find_basic_pitch() -> str | None:
    configured = os.environ.get("PROMPT2MIDI_BASIC_PITCH")
    candidates = [configured] if configured else []
    repo_engine = Path(__file__).resolve().parent.parent / ".venv-basic-pitch" / "bin" / "basic-pitch"
    candidates.extend([str(repo_engine), shutil.which("basic-pitch")])
    for candidate in candidates:
        if candidate and os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _single_output(directory: Path, suffix: str) -> str | None:
    matches = sorted(directory.glob(f"*{suffix}"), key=lambda path: path.stat().st_mtime, reverse=True)
    return str(matches[0]) if matches else None


def _read_note_events(path: str) -> list[dict]:
    events: list[dict] = []
    with open(path, newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                start = float(row["start_time_s"])
                end = float(row["end_time_s"])
                note = int(float(row["pitch_midi"]))
                velocity = int(float(row["velocity"]))
            except (KeyError, TypeError, ValueError):
                continue
            events.append(
                {
                    "start": round(start, 3),
                    "duration": round(max(0.05, end - start), 3),
                    "midi_note": note,
                    "velocity": max(1, min(127, velocity)),
                    "confidence": 0.72,
                }
            )
    return events


def _extract_bassline(events: list[dict]) -> list[dict]:
    low_notes = [event for event in events if 36 <= int(event["midi_note"]) <= 60 and int(event["velocity"]) >= 45]
    if not low_notes:
        return []

    bin_seconds = 0.25
    bins: dict[int, dict] = {}
    for event in low_notes:
        index = int(float(event["start"]) / bin_seconds)
        current = bins.get(index)
        if current is None:
            bins[index] = event
            continue
        if (int(event["midi_note"]), -int(event["velocity"])) < (int(current["midi_note"]), -int(current["velocity"])):
            bins[index] = event

    collapsed: list[dict] = []
    current: dict | None = None
    for index in sorted(bins):
        event = dict(bins[index])
        event["start"] = round(index * bin_seconds, 3)
        event["duration"] = bin_seconds
        if current and current["midi_note"] == event["midi_note"] and event["start"] <= current["start"] + current["duration"] + 0.001:
            current["duration"] = round((event["start"] + event["duration"]) - current["start"], 3)
            current["velocity"] = max(int(current["velocity"]), int(event["velocity"]))
        else:
            if current:
                collapsed.append(current)
            current = event
    if current:
        collapsed.append(current)
    return collapsed


def _confidence_from_notes(events: list[dict]) -> float:
    if not events:
        return 0.0
    density = min(1.0, len(events) / 80.0)
    return round(0.45 + density * 0.35, 2)


def _last_error(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-1] if lines else "unknown error"
