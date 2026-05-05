#!/usr/bin/env python3
"""Arrangement report and prompt rendering."""
from __future__ import annotations


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
        f"- Arrangement Lock: {(arrangement.get('arrangement_lock') or {}).get('status', 'unknown')} "
        f"confidence={(arrangement.get('arrangement_lock') or {}).get('confidence', 'unknown')}",
        "",
        "## Arrangement Lock Review",
        f"- Status: {(arrangement.get('arrangement_lock') or {}).get('summary', 'unknown')}",
        f"- Bar grid: {(arrangement.get('bar_grid') or {}).get('source', 'unknown')} "
        f"confidence={(arrangement.get('bar_grid') or {}).get('confidence', 'unknown')}",
        "",
        "## Arrangement Map",
        "| Time | Bars | Section | Energy | Transition Out | Boundary | Active Roles | Notes |",
        "|---|---:|---|---|---|---:|---|---|",
    ]
    for section in arrangement["sections"]:
        roles = ", ".join(section["active_roles"])
        lines.append(
            f"| {_fmt_time(section['start_seconds'])}-{_fmt_time(section['end_seconds'])} "
            f"| {section['start_bar']}-{section['end_bar']} "
            f"| {section['role']} | {section['energy_level']} | {section.get('transition_out', 'unknown')} "
            f"| {section.get('boundary_confidence', 'unknown')} | {roles} | {section['description']} |"
        )

    lines.extend(
        [
            "",
            "## Groove And Drums",
            f"- Groove estimate: {groove.get('description') or 'unknown'}",
            f"- Drum analysis method: {drums.get('method') or 'not available'}",
            f"- Kick behavior: {drums.get('tempo_feel') or 'assume 4/4 club pulse until stem analysis confirms variations'}",
            f"- Drum density: {drums.get('density') or 'unknown'}",
            f"- Percussion character: {drums.get('percussion_character') or 'unknown'}",
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
    lock_warnings = ((arrangement.get("blueprint_fidelity") or {}).get("warnings") or [])
    lines.extend(f"- {item.get('severity', 'medium')}: {item.get('message')}" for item in lock_warnings)
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
            f"{section['role']}, {section['energy_level']} energy, transition {section.get('transition_out', 'steady_section_change')}, "
            f"{roles}; {section['description']}"
        )
    prompt = [
        "# SUNO Structure Prompt",
        "",
        "Use the attached ACE guide audio as the musical and arrangement reference. Follow the structure, section lengths, breaks, drops, energy curve, and instrument-role timeline closely.",
        "",
        f"Create an original {vocals['track_kind']} at {arrangement['bpm']} BPM in the {arrangement['key']} key area.",
        f"Similarity level: {arrangement['similarity_level']} - {arrangement['similarity_policy']}.",
        f"Arrangement Lock confidence: {(arrangement.get('arrangement_lock') or {}).get('confidence', 'unknown')} "
        f"({(arrangement.get('arrangement_lock') or {}).get('status', 'unknown')}).",
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
        "instruction": f"Include a new {role} with original words, new voice, and changed melody contour while preserving the reference energy and placement.",
        "closing": "Vocals are allowed because the reference has a vocal-hook role; use original lyrics and voice only.",
    }


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
