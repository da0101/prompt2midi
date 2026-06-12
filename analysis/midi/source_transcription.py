#!/usr/bin/env python3
"""Optional model-backed transcription using a local Basic Pitch engine."""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from analysis.midi.midi_extraction import write_note_events_midi


@dataclass(frozen=True)
class ModelTrack:
    key: str
    path: str
    label: str
    kind: str
    note_count: int
    confidence: float
    limitations: list[str]
    source_method: str | None = None
    source_audio: str | None = None
    source_stem: str | None = None
    source_stage: str = "full_mix"


def can_run_model_transcription() -> bool:
    return os.environ.get("PROMPT2MIDI_DISABLE_MODEL") != "1" and _find_basic_pitch() is not None


def transcribe_with_model(audio_path: str, output_dir: str, bpm: float | None, stem_result: dict | None = None) -> dict:
    if os.environ.get("PROMPT2MIDI_DISABLE_MODEL") == "1":
        _progress("model transcription: disabled by environment")
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
        _progress("model transcription: Basic Pitch not installed")
        return {
            "available": False,
            "method": "basic_pitch",
            "tracks": [],
            "warnings": ["Basic Pitch engine not installed. Run npm run setup:transcription."],
        }

    _progress("model transcription: running Basic Pitch on full mix")
    mix_run = _run_basic_pitch(
        engine,
        audio_path,
        output_dir,
        run_name="full-mix",
        bpm=bpm,
        minimum_frequency=35,
        maximum_frequency=1200,
    )
    if not mix_run["ok"]:
        return {
            "available": False,
            "method": "basic_pitch",
            "tracks": [],
            "warnings": [mix_run["warning"]],
        }

    notes = mix_run["notes"]
    full_path = str(Path(output_dir) / "model-transcription.mid")
    shutil.copyfile(mix_run["midi_path"], full_path)

    tracks = [
        ModelTrack(
            key="model_transcription",
            path=os.path.abspath(full_path),
            label="Model MIDI transcription",
            kind="model_transcription",
            note_count=len(notes),
            confidence=_confidence_from_notes(notes),
            limitations=limitations,
            source_method="basic_pitch_coreml",
            source_audio=os.path.abspath(audio_path),
            source_stage="full_mix",
        )
    ]

    warnings = list(limitations)
    stem_bass = ((stem_result or {}).get("stems") or {}).get("bass")
    if stem_bass:
        stem_run = _run_basic_pitch(
            engine,
            stem_bass,
            output_dir,
            run_name="bass-stem",
            bpm=bpm,
            minimum_frequency=30,
            maximum_frequency=450,
        )
        if stem_run["ok"]:
            stem_bass_notes = _extract_bassline(
                stem_run["notes"],
                bpm=bpm,
                minimum_note=28,
                maximum_note=60,
                velocity_floor=35,
                house_cleanup=True,
            )
            if stem_bass_notes:
                stem_bass_path = write_note_events_midi(
                    str(Path(output_dir) / "source-bass-transcription.mid"),
                    stem_bass_notes,
                    bpm=bpm or 120,
                )
                stem_method = f"{(stem_result or {}).get('method', 'stem_separation')}+basic_pitch_coreml+house_bass_grid_cleanup"
                tracks.append(
                    ModelTrack(
                        key="source_bass_transcription",
                        path=stem_bass_path,
                        label="Stem-aware bass MIDI",
                        kind="source_aware_transcription",
                        note_count=len(stem_bass_notes),
                        confidence=_confidence_from_notes(stem_bass_notes),
                        limitations=[
                            "Bass MIDI was transcribed from a separated bass stem.",
                            "Sub-bass notes down to MIDI 28 are allowed for generated house/electro bass lines.",
                            "Bass starts are snapped to the 16th-note producer grid and repeated-position clutter is reduced.",
                            "Stem separation can still leak kick, guitar, vocal, or synth lows; verify by ear.",
                        ],
                        source_method=stem_method,
                        source_audio=os.path.abspath(stem_bass),
                        source_stem="bass",
                        source_stage="separated_stem",
                    )
                )
                _progress(f"model transcription: wrote source-bass-transcription.mid with {len(stem_bass_notes)} notes")
            else:
                warnings.append("Basic Pitch ran on the bass stem but produced no usable low-note bass events.")
        else:
            warnings.append("Stem-aware Basic Pitch failed: " + stem_run["warning"])

    bass_notes = _extract_bassline(notes, bpm=bpm, minimum_note=36, maximum_note=60, velocity_floor=45)
    if bass_notes:
        bass_path = write_note_events_midi(str(Path(output_dir) / "model-bass-transcription.mid"), bass_notes, bpm=bpm or 120)
        _progress(f"model transcription: wrote model-bass-transcription.mid with {len(bass_notes)} notes")
        tracks.append(
            ModelTrack(
                key="model_bass_transcription",
                path=bass_path,
                label="Full-mix model-filtered bass MIDI",
                kind="model_transcription",
                note_count=len(bass_notes),
                confidence=_confidence_from_notes(bass_notes),
                limitations=[
                    "Bass MIDI is filtered from model notes by pitch range; it is not stem-separated.",
                    "Dense guitars, vocals, or low percussion may still create false notes.",
                ],
                source_method="basic_pitch_coreml",
                source_audio=os.path.abspath(audio_path),
                source_stage="full_mix_filtered",
            )
        )

    return {
        "available": True,
        "method": "basic_pitch_coreml",
        "tracks": [track.__dict__ for track in tracks],
        "warnings": warnings,
    }


def _run_basic_pitch(
    engine: str,
    audio_path: str,
    output_dir: str,
    *,
    run_name: str,
    bpm: float | None,
    minimum_frequency: int,
    maximum_frequency: int,
) -> dict:
    _progress(f"model transcription: Basic Pitch {run_name} frequency range {minimum_frequency}-{maximum_frequency} Hz")
    model_dir = Path(output_dir) / "basic-pitch" / run_name
    runtime_dir = Path(output_dir) / "basic-pitch-runtime" / run_name
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
        str(minimum_frequency),
        "--maximum-frequency",
        str(maximum_frequency),
    ]
    env = os.environ.copy()
    env["TMPDIR"] = str(runtime_dir)
    try:
        completed = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            text=True,
            capture_output=True,
            timeout=240,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "warning": f"Basic Pitch {run_name} timed out after 240 seconds."}
    if completed.returncode != 0:
        return {"ok": False, "warning": f"Basic Pitch {run_name} failed: " + _last_error(completed.stderr or completed.stdout)}

    midi_path = _single_output(model_dir, ".mid")
    csv_path = _single_output(model_dir, ".csv")
    if midi_path is None or csv_path is None:
        return {"ok": False, "warning": f"Basic Pitch {run_name} completed but did not produce MIDI and note-event outputs."}

    notes = _read_note_events(csv_path)
    _progress(f"model transcription: Basic Pitch {run_name} produced {len(notes)} note events")
    return {"ok": True, "midi_path": midi_path, "notes": notes}


def _find_basic_pitch() -> str | None:
    configured = os.environ.get("PROMPT2MIDI_BASIC_PITCH")
    candidates = [configured] if configured else []
    repo_engine = Path(__file__).resolve().parents[2] / ".venv-basic-pitch" / "bin" / "basic-pitch"
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


def _extract_bassline(
    events: list[dict],
    *,
    bpm: float | None = None,
    minimum_note: int = 36,
    maximum_note: int = 60,
    velocity_floor: int = 45,
    house_cleanup: bool = False,
) -> list[dict]:
    low_notes = [
        event
        for event in events
        if minimum_note <= int(event["midi_note"]) <= maximum_note and int(event["velocity"]) >= velocity_floor
    ]
    if not low_notes:
        return []

    bin_seconds = _bass_grid_seconds(bpm) if bpm else 0.25
    bins: dict[int, dict] = {}
    for event in low_notes:
        index = int(round(float(event["start"]) / bin_seconds))
        current = bins.get(index)
        if current is None:
            bins[index] = event
            continue
        if _bass_candidate_rank(event) < _bass_candidate_rank(current):
            bins[index] = event

    if house_cleanup:
        bins = _reduce_to_repeating_house_positions(bins, bin_seconds)

    collapsed: list[dict] = []
    current: dict | None = None
    for index in sorted(bins):
        event = dict(bins[index])
        event["start"] = round(index * bin_seconds, 3)
        event["duration"] = round(_bass_note_duration(event, bin_seconds), 3)
        event["midi_note"] = _normalize_sub_bass_register(int(event["midi_note"]), minimum_note, maximum_note)
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


def _bass_grid_seconds(bpm: float | None) -> float:
    beat = 60.0 / max(40.0, min(220.0, bpm or 120.0))
    return max(0.068, min(0.18, beat / 4.0))


def _bass_candidate_rank(event: dict) -> tuple[int, int]:
    note = int(event["midi_note"])
    velocity = int(event["velocity"])
    return (note, -velocity)


def _bass_note_duration(event: dict, bin_seconds: float) -> float:
    duration = float(event.get("duration") or bin_seconds)
    if duration <= bin_seconds * 1.25:
        return bin_seconds
    return min(duration, bin_seconds * 4.0)


def _normalize_sub_bass_register(note: int, minimum_note: int, maximum_note: int) -> int:
    while note > maximum_note:
        note -= 12
    while note < minimum_note and note + 12 <= maximum_note:
        note += 12
    return max(minimum_note, min(maximum_note, note))


def _reduce_to_repeating_house_positions(bins: dict[int, dict], bin_seconds: float) -> dict[int, dict]:
    if len(bins) <= 8:
        return bins
    max_index = max(bins)
    bars = max(1.0, (max_index + 1) / 16.0)
    counts: dict[int, int] = {}
    velocity_scores: dict[int, int] = {}
    for index, event in bins.items():
        position = index % 16
        counts[position] = counts.get(position, 0) + 1
        velocity_scores[position] = velocity_scores.get(position, 0) + int(event.get("velocity") or 0)

    average_events_per_bar = len(bins) / bars
    if average_events_per_bar <= 6.0:
        return bins

    min_support = max(2, round(bars * 0.16))
    supported = [position for position, count in counts.items() if count >= min_support]
    if not supported:
        return bins
    preferred_offbeats = {2, 3, 6, 7, 10, 11, 14, 15}
    ranked = sorted(
        supported,
        key=lambda position: (
            position not in preferred_offbeats,
            -counts[position],
            -velocity_scores[position],
            position,
        ),
    )
    preferred_supported = [position for position in ranked if position in preferred_offbeats]
    if len(preferred_supported) >= 4:
        max_positions = min(8, len(preferred_supported))
    else:
        max_positions = 8 if bin_seconds <= 0.14 else 6
    keep_positions = set(ranked[:max_positions])
    return {index: event for index, event in bins.items() if index % 16 in keep_positions}


def _confidence_from_notes(events: list[dict]) -> float:
    if not events:
        return 0.0
    density = min(1.0, len(events) / 80.0)
    return round(0.45 + density * 0.35, 2)


def _last_error(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-1] if lines else "unknown error"


def _progress(message: str) -> None:
    print(f"progress: {message}", file=sys.stderr, flush=True)
