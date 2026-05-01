#!/usr/bin/env python3
"""Full-song arrangement artifacts for SUNO/ACE reference workflows."""
from __future__ import annotations

import json
import os
from pathlib import Path

from composition import _bass_events, _chord_events, _drum_events, _melody_events, _parse_key
from midi_extraction import write_multitrack_midi


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
    guide_midi = write_full_arrangement_guide_midi(
        str(exports_dir / "full-arrangement-guide.mid"),
        arrangement,
        analysis,
    )
    report_text = render_analysis_report(analysis, arrangement, user_prompt=user_prompt)
    prompt_text = render_suno_structure_prompt(analysis, arrangement, user_prompt=user_prompt)

    arrangement_path = exports_dir / "arrangement-map.json"
    report_path = exports_dir / "analysis-report.md"
    prompt_path = exports_dir / "suno-structure-prompt.md"

    arrangement_path.write_text(json.dumps(arrangement, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        "limitations": arrangement["limitations"],
    }


def build_arrangement_map(analysis: dict, similarity_level: str | None = None) -> dict:
    bpm = _number(analysis.get("bpm"), 120.0)
    duration = max(1.0, _number(analysis.get("duration_seconds"), 30.0))
    bar_seconds = 4.0 * 60.0 / max(40.0, min(220.0, bpm))
    total_bars = max(1, round(duration / bar_seconds))
    level = similarity_level or analysis.get("reference_similarity_level") or "medium"
    level = str(level).replace("-", "_")

    raw_sections = ((analysis.get("structure") or {}).get("sections") or [])
    if raw_sections:
        sections = _sections_from_analysis(raw_sections, duration, bar_seconds)
        sections = _merge_short_sections(sections, min_seconds=max(bar_seconds * 8.0, 12.0))
        method = f"{(analysis.get('structure') or {}).get('method', 'structure_analysis')}+bar_alignment"
        limitations = [
            "Section boundaries are aligned to the detected BPM grid.",
            "Very short detected fragments are merged into neighboring sections to keep the SUNO structure usable.",
            "Labels are producer-role labels inferred from energy and position unless an external structure model supplies names.",
        ]
    else:
        sections = _fallback_sections(duration, total_bars, bar_seconds)
        method = "fallback_bar_grid"
        limitations = [
            "No external full-song structure model was available, so sections were estimated from duration and bar grid.",
            "Install All-In-One Music Structure Analyzer for stronger beat, downbeat, and functional section labels.",
        ]

    _repair_section_edges(sections, total_bars, duration, bar_seconds)
    _annotate_sections(sections)
    return {
        "version": 1,
        "method": method,
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
        "limitations": limitations,
    }


def render_analysis_report(analysis: dict, arrangement: dict, user_prompt: str = "") -> str:
    genre = analysis.get("genre") or {}
    groove = analysis.get("groove") or {}
    drums = analysis.get("drums") or {}
    transform = analysis.get("reference_transform") or {}
    stem = analysis.get("stem_separation") or {}
    model = analysis.get("model_transcription") or {}
    vocals = _vocal_summary(analysis)
    lines = [
        "# Reference Track Analysis Report",
        "",
        "## Identity",
        f"- Style/genre estimate: {_genre_text(genre)}",
        f"- BPM: {arrangement['bpm']} ({_confidence(analysis.get('bpm_confidence'))})",
        f"- Key: {arrangement['key']} ({_confidence(analysis.get('key_confidence'))})",
        f"- Duration: {_fmt_time(arrangement['duration_seconds'])}",
        f"- Similarity target: {arrangement['similarity_level']} - {arrangement['similarity_policy']}",
        "",
        "## Arrangement Map",
        "| Time | Bars | Section | Energy | Active Roles | Notes |",
        "|---|---:|---|---|---|---|",
    ]
    for section in arrangement["sections"]:
        roles = ", ".join(section["active_roles"])
        lines.append(
            f"| {_fmt_time(section['start_seconds'])}-{_fmt_time(section['end_seconds'])} "
            f"| {section['start_bar']}-{section['end_bar']} "
            f"| {section['role']} | {section['energy_level']} | {roles} | {section['description']} |"
        )

    lines.extend(
        [
            "",
            "## Groove And Drums",
            f"- Groove estimate: {groove.get('description') or 'unknown'}",
            f"- Drum analysis method: {drums.get('method') or 'not available'}",
            f"- Kick behavior: {drums.get('tempo_feel') or 'assume 4/4 club pulse until stem analysis confirms variations'}",
            f"- Drum density: {drums.get('density') or 'unknown'}",
            f"- Swing: {drums.get('swing') or 'unknown'}",
            "",
            "## Bass",
            f"- Bass source evidence: {_bass_evidence(analysis)}",
            f"- Bass role: {((transform.get('bass') or {}).get('description') or 'low-end groove anchor; refine with stem-aware transcription')}",
            "- Timbre target: describe with producer terms after stem descriptors are available: sub weight, roundness, punch, saturation, pluck, sustain.",
            "",
            "## Vocals / Hook Character",
            f"- Vocal role: {vocals['report']}",
            f"- Generation instruction: {vocals['instruction']}",
            "",
            "## Harmony, Stabs, Pads, FX",
            f"- Chord evidence: {_chord_text(analysis.get('chords') or {})}",
            f"- Stab/effect replacement: {((transform.get('stab_replacement') or {}).get('description') or 'none requested')}",
            "- Pad/FX detail is currently inferred from mix energy and style; Essentia/stem descriptors should upgrade this.",
            "",
            "## Model / Tool Evidence",
            f"- Stems: {stem.get('method', 'unknown')} available={stem.get('available', False)}",
            f"- Basic Pitch transcription: {model.get('method', 'unknown')} available={model.get('available', False)}",
            f"- Arrangement method: {arrangement['method']}",
            "",
            "## User Direction",
            user_prompt.strip() or "No extra user direction supplied.",
            "",
            "## Confidence Limits",
        ]
    )
    lines.extend(f"- {item}" for item in arrangement["limitations"])
    lines.append("- Timbre labels are conservative until stem-level Essentia descriptors are added.")
    return "\n".join(lines) + "\n"


def render_suno_structure_prompt(analysis: dict, arrangement: dict, user_prompt: str = "") -> str:
    vocals = _vocal_summary(analysis)
    sections = []
    for section in arrangement["sections"]:
        roles = ", ".join(section["active_roles"])
        sections.append(
            f"{section['start_bar']}-{section['end_bar']} bars "
            f"({_fmt_time(section['start_seconds'])}-{_fmt_time(section['end_seconds'])}): "
            f"{section['role']}, {section['energy_level']} energy, {roles}; {section['description']}"
        )
    prompt = [
        "# SUNO Structure Prompt",
        "",
        "Use the attached ACE guide audio as the musical and arrangement reference. Follow the structure, section lengths, breaks, drops, energy curve, and instrument-role timeline closely.",
        "",
        f"Create an original {vocals['track_kind']} at {arrangement['bpm']} BPM in the {arrangement['key']} key area.",
        f"Similarity level: {arrangement['similarity_level']} - {arrangement['similarity_policy']}.",
        f"Style/genre: {_genre_text(analysis.get('genre') or {})}.",
        f"Groove: {(analysis.get('groove') or {}).get('description') or 'club-focused groove with stable timing'}.",
        "",
        "Arrangement:",
    ]
    prompt.extend(f"- {line}" for line in sections)
    prompt.extend(
        [
            "",
            "Production direction:",
            "- Preserve the reference tempo, bar grid, section proportions, energy movement, and role balance.",
            "- Keep drums, bass, percussion, stabs, pads, and FX professional and genre-accurate.",
            f"- {vocals['instruction']}",
            "- Do not copy protected hooks, lead vocal identity, lyrics, or exact melodic signature.",
            "- Avoid cheesy pop additions, random sci-fi glitches, weak drums, thin bass, and atonal artifacts.",
        ]
    )
    if user_prompt.strip():
        prompt.extend(["", "User direction:", user_prompt.strip()])
    prompt.append("")
    prompt.append(vocals["closing"])
    return "\n".join(prompt) + "\n"


def _vocal_summary(analysis: dict) -> dict:
    transform_vocal = ((analysis.get("reference_transform") or {}).get("vocals") or {})
    vocals = analysis.get("vocals") or {}
    present = bool(transform_vocal.get("preserve_role") or vocals.get("present"))
    role = str(transform_vocal.get("role") or vocals.get("role") or "vocal hook")
    confidence = vocals.get("confidence")
    if not present:
        return {
            "track_kind": "instrumental track",
            "report": "none detected",
            "instruction": "Keep the generation instrumental unless short vocal texture naturally fits the style.",
            "closing": "Instrumental, no vocals unless the user explicitly asks for vocals.",
        }
    confidence_text = f" confidence={confidence}" if confidence is not None else ""
    return {
        "track_kind": "track",
        "report": f"{role}{confidence_text}; preserve the function but not the original identity",
        "instruction": (
            f"Include a new {role} with original words, new voice, and changed melody contour while preserving the reference energy and placement."
        ),
        "closing": "Vocals are allowed because the reference has a vocal-hook role; use original lyrics and voice only.",
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


def _sections_from_analysis(raw_sections: list[dict], duration: float, bar_seconds: float) -> list[dict]:
    sections: list[dict] = []
    for index, raw in enumerate(raw_sections):
        start = max(0.0, _number(raw.get("start"), 0.0))
        end = max(start + 0.1, _number(raw.get("end"), duration))
        sections.append(
            {
                "id": f"section_{index + 1}",
                "source_label": str(raw.get("label") or chr(65 + min(index, 25))),
                "start_seconds": round(start, 3),
                "end_seconds": round(min(duration, end), 3),
                "start_bar": max(1, round(start / bar_seconds) + 1),
                "end_bar": max(1, round(end / bar_seconds)),
                "energy": _number(raw.get("energy"), 0.0),
            }
        )
    return sections


def _merge_short_sections(sections: list[dict], min_seconds: float) -> list[dict]:
    if len(sections) <= 1:
        return sections
    merged: list[dict] = []
    for section in sections:
        length = float(section["end_seconds"]) - float(section["start_seconds"])
        if merged and length < min_seconds:
            previous = merged[-1]
            previous_length = float(previous["end_seconds"]) - float(previous["start_seconds"])
            total = max(0.001, previous_length + length)
            previous["end_seconds"] = section["end_seconds"]
            previous["end_bar"] = section["end_bar"]
            previous["source_label"] = f"{previous['source_label']}+{section['source_label']}"
            previous["energy"] = round(
                ((float(previous.get("energy") or 0.0) * previous_length) + (float(section.get("energy") or 0.0) * length)) / total,
                4,
            )
        else:
            merged.append(dict(section))

    if len(merged) > 1:
        first = merged[0]
        first_length = float(first["end_seconds"]) - float(first["start_seconds"])
        if first_length < min_seconds:
            second = merged[1]
            second_length = float(second["end_seconds"]) - float(second["start_seconds"])
            total = max(0.001, first_length + second_length)
            second["start_seconds"] = first["start_seconds"]
            second["start_bar"] = first["start_bar"]
            second["source_label"] = f"{first['source_label']}+{second['source_label']}"
            second["energy"] = round(
                ((float(first.get("energy") or 0.0) * first_length) + (float(second.get("energy") or 0.0) * second_length)) / total,
                4,
            )
            merged = merged[1:]
    for index, section in enumerate(merged):
        section["id"] = f"section_{index + 1}"
    return merged


def _fallback_sections(duration: float, total_bars: int, bar_seconds: float) -> list[dict]:
    if total_bars <= 32:
        ranges = [(1, total_bars, "main")]
    elif total_bars <= 80:
        intro = min(16, total_bars // 4)
        outro = min(16, total_bars // 5)
        ranges = [(1, intro, "intro"), (intro + 1, total_bars - outro, "main"), (total_bars - outro + 1, total_bars, "outro")]
    else:
        intro = 16
        groove_a = min(64, max(32, total_bars // 3))
        breakdown_start = min(total_bars - 32, max(groove_a + 1, round(total_bars * 0.55)))
        breakdown_end = min(total_bars - 17, breakdown_start + 16)
        outro_start = max(breakdown_end + 17, total_bars - 15)
        ranges = [
            (1, intro, "intro"),
            (intro + 1, groove_a, "groove"),
            (groove_a + 1, breakdown_start - 1, "variation"),
            (breakdown_start, breakdown_end, "breakdown"),
            (breakdown_end + 1, outro_start - 1, "drop"),
            (outro_start, total_bars, "outro"),
        ]
    sections = []
    for index, (start_bar, end_bar, label) in enumerate(ranges):
        start = (start_bar - 1) * bar_seconds
        end = min(duration, end_bar * bar_seconds)
        sections.append(
            {
                "id": f"section_{index + 1}",
                "source_label": label,
                "start_seconds": round(start, 3),
                "end_seconds": round(end, 3),
                "start_bar": start_bar,
                "end_bar": max(start_bar, end_bar),
                "energy": _fallback_energy(label),
            }
        )
    return sections


def _repair_section_edges(sections: list[dict], total_bars: int, duration: float, bar_seconds: float) -> None:
    cursor = 1
    for section in sections:
        length = max(1, int(section["end_bar"]) - int(section["start_bar"]) + 1)
        section["start_bar"] = cursor
        section["end_bar"] = min(total_bars, cursor + length - 1)
        section["start_seconds"] = round((section["start_bar"] - 1) * bar_seconds, 3)
        section["end_seconds"] = round(min(duration, section["end_bar"] * bar_seconds), 3)
        cursor = section["end_bar"] + 1
    if sections and sections[-1]["end_bar"] < total_bars:
        sections[-1]["end_bar"] = total_bars
        sections[-1]["end_seconds"] = round(duration, 3)


def _annotate_sections(sections: list[dict]) -> None:
    energies = [float(section.get("energy") or 0.0) for section in sections]
    max_energy = max(energies) if energies else 1.0
    min_energy = min(energies) if energies else 0.0
    span = max(0.001, max_energy - min_energy)
    previous_level = "low"
    for index, section in enumerate(sections):
        normalized = (float(section.get("energy") or 0.0) - min_energy) / span
        level = "high" if normalized >= 0.66 else "medium" if normalized >= 0.33 else "low"
        role = _role_for_section(index, len(sections), level, previous_level, str(section.get("source_label") or ""))
        section["energy_level"] = level
        section["role"] = role
        section["active_roles"] = _active_roles(role, level)
        section["description"] = _section_description(role, level)
        previous_level = level


def _role_for_section(index: int, count: int, level: str, previous_level: str, label: str) -> str:
    lower = label.lower()
    for role in ("intro", "breakdown", "drop", "outro", "bridge", "chorus", "verse"):
        if role in lower:
            return "groove" if role in {"chorus", "verse"} else role
    if index == 0:
        return "intro"
    if index == count - 1:
        return "outro"
    if level == "low" and previous_level in {"medium", "high"}:
        return "breakdown"
    if level == "high" and previous_level == "low":
        return "drop"
    if level == "high":
        return "groove"
    return "variation"


def _active_roles(role: str, level: str) -> list[str]:
    roles = {
        "intro": ["kick", "bass hint", "filtered percussion"],
        "groove": ["kick", "bass", "clap/snare", "hats", "percussion", "main stab"],
        "variation": ["kick", "bass", "percussion fills", "FX movement"],
        "breakdown": ["pads", "FX tails", "filtered stab", "reduced drums"],
        "drop": ["full drums", "bass", "hats", "percussion", "main hook/stab"],
        "outro": ["kick", "reduced bass", "hats", "DJ-friendly tail"],
        "bridge": ["pads", "transition FX", "reduced groove"],
    }.get(role, ["kick", "bass", "percussion"])
    if level == "low" and "reduced drums" not in roles:
        roles = [item for item in roles if item not in {"full drums", "main hook/stab"}]
    return roles


def _section_description(role: str, level: str) -> str:
    descriptions = {
        "intro": "establish timing and mood without revealing every element",
        "groove": "main dancefloor groove with stable low-end and percussion drive",
        "variation": "same pocket with fills, sound movement, and controlled changes",
        "breakdown": "reduce drums and low-end, leave tension, space, pads, and FX",
        "drop": "return with the strongest drum/bass energy and clearest hook role",
        "outro": "strip elements for a DJ-friendly ending while keeping tempo locked",
        "bridge": "connect sections with lower density and transition FX",
    }
    return f"{descriptions.get(role, 'maintain the reference role balance')} ({level} energy)"


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


def _fallback_energy(label: str) -> float:
    return {
        "intro": 0.35,
        "main": 0.75,
        "groove": 0.8,
        "variation": 0.7,
        "breakdown": 0.2,
        "drop": 0.95,
        "outro": 0.4,
    }.get(label, 0.6)


def _genre_text(genre: dict) -> str:
    primary = genre.get("primary") or "unknown"
    tags = genre.get("tags") or []
    suffix = f" ({', '.join(tags[:5])})" if tags else ""
    return f"{primary}{suffix}"


def _confidence(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "unknown confidence"
    if number >= 0.75:
        return f"high confidence {number:.2f}"
    if number >= 0.45:
        return f"medium confidence {number:.2f}"
    return f"low confidence {number:.2f}"


def _bass_evidence(analysis: dict) -> str:
    source = analysis.get("bass_transcription") or {}
    events = source.get("event_count")
    confidence = source.get("confidence")
    if events:
        return f"{events} low-frequency events, confidence {confidence}"
    return "no reliable bass transcription yet"


def _chord_text(chords: dict) -> str:
    progression = chords.get("progression") or []
    if progression:
        return ", ".join(str(item) for item in progression[:8])
    return chords.get("method") or "not available"


def _fmt_time(seconds: float) -> str:
    seconds = max(0, int(round(float(seconds))))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _number(value, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
