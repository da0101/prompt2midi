#!/usr/bin/env python3
"""Full-song arrangement artifacts for SUNO/ACE reference workflows."""
from __future__ import annotations

import json
import os
from pathlib import Path

from analysis.arrangement.arrangement_lock import build_arrangement_lock_artifacts
from analysis.arrangement.arrangement_reports import render_analysis_report, render_suno_structure_prompt
from analysis.arrangement.arrangement_sections import build_arrangement_sections
from analysis.composition.composition import _bass_events, _chord_events, _drum_events, _melody_events, _parse_key
from analysis.midi.midi_extraction import write_multitrack_midi


SIMILARITY_COPY = {
    "low": "new track in the same genre, tempo, key area, and energy lane",
    "medium_low": "new track path with recognizable reference attitude and section logic",
    "medium": "balanced inspired version with similar groove logic and clearly new musical content",
    "medium_high": "close reference-inspired version with changed bass notes, fills, and sound palette",
    "high": "very close arrangement and groove behavior with generated sounds and variation",
    "near_identical_twist": "closest structural transformation with a twist; do not copy the hook or vocal identity",
}


def build_full_arrangement_package(
    analysis: dict,
    output_dir: str,
    user_prompt: str = "",
    similarity_level: str | None = None,
) -> dict:
    """Write arrangement-map/report/SUNO prompt/guide MIDI and return their paths."""
    exports_dir = Path(output_dir)
    exports_dir.mkdir(parents=True, exist_ok=True)

    arrangement = build_arrangement_map(analysis, similarity_level=similarity_level)
    artifacts = build_arrangement_lock_artifacts(analysis, arrangement)
    guide_midi = write_full_arrangement_guide_midi(str(exports_dir / "full-arrangement-guide.mid"), arrangement, analysis)
    report_text = render_analysis_report(analysis, arrangement, user_prompt=user_prompt)
    prompt_text = render_suno_structure_prompt(analysis, arrangement, user_prompt=user_prompt)

    arrangement_path = exports_dir / "arrangement-map.json"
    structure_debug_path = exports_dir / "structure-debug.json"
    lock_report_path = exports_dir / "arrangement-lock-report.json"
    report_path = exports_dir / "analysis-report.md"
    prompt_path = exports_dir / "suno-structure-prompt.md"

    arrangement_path.write_text(json.dumps(arrangement, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    structure_debug_path.write_text(json.dumps(artifacts["structure_debug"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lock_report_path.write_text(json.dumps(artifacts["lock_report"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(report_text, encoding="utf-8")
    prompt_path.write_text(prompt_text, encoding="utf-8")

    return {
        "status": "ready",
        "method": arrangement["method"],
        "similarity_level": arrangement["similarity_level"],
        "duration_seconds": arrangement["duration_seconds"],
        "total_bars": arrangement["total_bars"],
        "section_count": len(arrangement["sections"]),
        "paths": {
            "arrangement_map": str(arrangement_path.resolve()),
            "structure_debug": str(structure_debug_path.resolve()),
            "arrangement_lock_report": str(lock_report_path.resolve()),
            "analysis_report": str(report_path.resolve()),
            "suno_structure_prompt": str(prompt_path.resolve()),
            "full_arrangement_guide_midi": guide_midi,
            "full_arrangement_guide_audio": None,
        },
        "guide_audio": {
            "status": "not_generated",
            "provider": "ace_step",
            "reason": (
                "Full-song ACE guide audio is the next stage. This slice writes the bar-accurate "
                "arrangement scaffold, report, SUNO prompt, and full-arrangement MIDI guide first."
            ),
        },
        "sections": arrangement["sections"],
        "arrangement_lock": arrangement["arrangement_lock"],
        "blueprint_fidelity": arrangement["blueprint_fidelity"],
        "limitations": arrangement["limitations"],
    }


def build_arrangement_map(analysis: dict, similarity_level: str | None = None) -> dict:
    bpm = _number(analysis.get("bpm"), 120.0)
    duration = max(1.0, _number(analysis.get("duration_seconds"), 30.0))
    bar_seconds = 4.0 * 60.0 / max(40.0, min(220.0, bpm))
    total_bars = max(1, round(duration / bar_seconds))
    level = similarity_level or analysis.get("reference_similarity_level") or "medium"
    level = str(level).replace("-", "_")

    section_package = build_arrangement_sections(analysis, duration, total_bars, bar_seconds)
    sections = section_package["sections"]
    return {
        "version": 1,
        "method": section_package["method"],
        "bpm": round(bpm, 2),
        "key": analysis.get("key") or "unknown",
        "duration_seconds": round(duration, 3),
        "bar_seconds": round(bar_seconds, 4),
        "total_bars": total_bars,
        "time_signature": "4/4",
        "similarity_level": level,
        "similarity_policy": SIMILARITY_COPY.get(level, SIMILARITY_COPY["medium"]),
        "sections": sections,
        "source_models": {
            "current": ["Python DSP", "librosa when installed", "Demucs optional", "Basic Pitch optional"],
            "recommended_next": ["All-In-One Music Structure Analyzer", "Essentia MusicExtractor", "Essentia Discogs EffNet"],
        },
        "limitations": section_package["limitations"],
    }


def write_full_arrangement_guide_midi(path: str, arrangement: dict, analysis: dict) -> str:
    bpm = _number(arrangement.get("bpm"), 120.0)
    root, mode = _parse_key(str(arrangement.get("key") or analysis.get("key") or "C major"))
    bass_root = root - 24
    chord_root = root - 12
    total_bars = max(1, int(arrangement.get("total_bars") or 32))
    bar_seconds = 4.0 * 60.0 / bpm

    bass = _bass_events(bass_root, bpm, total_bars, style="full arrangement")
    drums = _drum_events(bpm, total_bars, style="full arrangement")
    chords = _chord_events(chord_root, mode, bpm, total_bars, style="full arrangement")
    melody = _melody_events(root, mode, bpm, total_bars, style="full arrangement")

    tracks = [
        _filter_events_for_sections(bass, arrangement["sections"], "bass"),
        _filter_events_for_sections(drums, arrangement["sections"], "drums"),
        _filter_events_for_sections(chords, arrangement["sections"], "chords"),
        _filter_events_for_sections(melody, arrangement["sections"], "melody"),
        _section_marker_events(arrangement["sections"], bar_seconds),
    ]
    return write_multitrack_midi(path, tracks, bpm=bpm)


def _filter_events_for_sections(events: list[dict], sections: list[dict], role: str) -> list[dict]:
    output = []
    for event in events:
        section = _section_for_time(float(event.get("start", 0.0)), sections)
        active = section.get("active_roles") or []
        if role == "bass" and not any("bass" in item for item in active):
            continue
        if role == "chords" and section.get("role") not in {"breakdown", "drop", "groove", "variation"}:
            continue
        if role == "melody" and section.get("role") not in {"drop", "variation", "breakdown"}:
            continue
        output.append(dict(event))
    return output


def _section_for_time(start: float, sections: list[dict]) -> dict:
    for section in sections:
        if section["start_seconds"] <= start < section["end_seconds"]:
            return section
    return sections[-1]


def _section_marker_events(sections: list[dict], bar_seconds: float) -> list[dict]:
    events = []
    for index, section in enumerate(sections):
        events.append(
            {
                "start": (section["start_bar"] - 1) * bar_seconds,
                "duration": min(0.5, bar_seconds * 0.25),
                "midi_note": 84 + (index % 12),
                "velocity": 70,
                "channel": 15,
            }
        )
    return events


def _number(value, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
