#!/usr/bin/env python3
"""Arrangement Lock scoring and review metadata."""
from __future__ import annotations

import statistics

from analysis.arrangement.arrangement_lock_reports import build_lock_report, build_structure_debug, lock_summary, reference_version

REVIEW_THRESHOLD = 0.68

def build_arrangement_lock_artifacts(analysis: dict, arrangement: dict) -> dict:
    """Annotate arrangement sections and return report/debug artifacts."""
    bar_grid = _bar_grid(analysis, arrangement)
    sections = arrangement.get("sections") or []
    repairs = _annotate_sections(sections, arrangement, bar_grid)
    fidelity = _blueprint_fidelity(analysis, arrangement, bar_grid, repairs)
    warnings = _warnings(analysis, arrangement, bar_grid, fidelity, repairs)
    confidence = _lock_confidence(analysis, arrangement, bar_grid, fidelity, warnings)
    review_required = confidence < REVIEW_THRESHOLD or any(item.get("severity") == "high" for item in warnings)

    fidelity["confidence"] = confidence
    fidelity["review_required"] = review_required
    fidelity["warnings"] = warnings
    arrangement["bar_grid"] = bar_grid
    arrangement["reference_version"] = reference_version(arrangement)
    arrangement["blueprint_fidelity"] = fidelity
    arrangement["arrangement_lock"] = {
        "status": "review_required" if review_required else "ready_for_generation",
        "confidence": confidence,
        "review_threshold": REVIEW_THRESHOLD,
        "review_required": review_required,
        "summary": lock_summary(confidence, review_required, warnings),
    }

    candidates = _bar_grid_candidates(analysis, arrangement)
    return {
        "lock_report": build_lock_report(arrangement, warnings),
        "structure_debug": build_structure_debug(analysis, arrangement, bar_grid, repairs, candidates),
    }

def _bar_grid(analysis: dict, arrangement: dict) -> dict:
    for candidate in _bar_grid_candidates(analysis, arrangement):
        if candidate.get("downbeat_count", 0) >= 2:
            return candidate
    candidates = _bar_grid_candidates(analysis, arrangement)
    return candidates[0] if candidates else _estimated_grid(analysis, arrangement)


def _bar_grid_candidates(analysis: dict, arrangement: dict) -> list[dict]:
    allin1 = analysis.get("allin1") or {}
    structure = analysis.get("structure") or {}
    beat_grid = analysis.get("beat_grid") or {}
    candidates = []
    for source, payload, base_confidence in (
        ("allin1_downbeats", allin1, 0.95),
        ("librosa_estimated_downbeats", beat_grid, _number(beat_grid.get("confidence"), 0.62)),
        ("structure_downbeats", structure, 0.58),
    ):
        beats = _numbers(payload.get("beats") or [])
        downbeats = _numbers(payload.get("downbeats") or [])
        if beats or downbeats:
            candidates.append(_grid_from_times(source, beats, downbeats, arrangement, analysis, base_confidence))
    candidates.append(_estimated_grid(analysis, arrangement))
    return sorted(candidates, key=lambda item: item.get("confidence", 0.0), reverse=True)


def _grid_from_times(source: str, beats: list[float], downbeats: list[float], arrangement: dict, analysis: dict, base_confidence: float) -> dict:
    bpm = _number(arrangement.get("bpm"), _number(analysis.get("bpm"), 120.0))
    bar_seconds = _number(arrangement.get("bar_seconds"), 4.0 * 60.0 / max(40.0, min(220.0, bpm)))
    if len(downbeats) >= 2:
        intervals = [b - a for a, b in zip(downbeats, downbeats[1:]) if b > a]
        median = statistics.median(intervals) if intervals else bar_seconds
        drift = _tempo_drift(intervals, median)
        return {
            "source": source,
            "confidence": round(max(0.45, min(0.95, base_confidence - drift * 3.0)), 3),
            "bar_seconds": round(median, 4),
            "estimated_bar_seconds": round(bar_seconds, 4),
            "downbeat_count": len(downbeats),
            "beat_count": len(beats),
            "tempo_drift": round(drift, 4),
            "first_downbeats": [round(value, 3) for value in downbeats[:16]],
        }
    beat_based_bars = len(beats) // 4 if beats else 0
    confidence = min(base_confidence, 0.52) if beat_based_bars else 0.34
    return {
        "source": source if beat_based_bars else "estimated_bpm_grid",
        "confidence": confidence,
        "bar_seconds": round(bar_seconds, 4),
        "estimated_bar_seconds": round(bar_seconds, 4),
        "downbeat_count": 0,
        "beat_count": len(beats),
        "tempo_drift": 0.0,
        "first_downbeats": [],
    }


def _estimated_grid(analysis: dict, arrangement: dict) -> dict:
    bpm = _number(arrangement.get("bpm"), _number(analysis.get("bpm"), 120.0))
    bar_seconds = _number(arrangement.get("bar_seconds"), 4.0 * 60.0 / max(40.0, min(220.0, bpm)))
    return {
        "source": "estimated_bpm_grid",
        "confidence": 0.34,
        "bar_seconds": round(bar_seconds, 4),
        "estimated_bar_seconds": round(bar_seconds, 4),
        "downbeat_count": 0,
        "beat_count": 0,
        "tempo_drift": 0.0,
        "first_downbeats": [],
    }


def _annotate_sections(sections: list[dict], arrangement: dict, bar_grid: dict) -> list[dict]:
    repairs = []
    bar_seconds = _number(arrangement.get("bar_seconds"), _number(bar_grid.get("bar_seconds"), 2.0))
    for index, section in enumerate(sections):
        start = _number(section.get("start_seconds"), 0.0)
        end = _number(section.get("end_seconds"), start)
        detected_start = _number(section.get("detected_start_seconds"), start)
        detected_end = _number(section.get("detected_end_seconds"), end)
        start_delta = start - detected_start
        end_delta = end - detected_end
        bar_count = max(1, int(section.get("end_bar") or 1) - int(section.get("start_bar") or 1) + 1)

        transition_in = "track_start" if index == 0 else (sections[index - 1].get("transition_out") or "section_change")
        transition_out = _transition_out(section, sections[index + 1] if index + 1 < len(sections) else None)
        section["transition_in"] = transition_in
        section["transition_out"] = transition_out
        section["locked_bar_range"] = {"start_bar": int(section.get("start_bar") or 1), "end_bar": int(section.get("end_bar") or 1), "bar_count": bar_count}
        section["target_duration_seconds"] = round(max(0.0, end - start), 3)
        section["pre_roll_seconds"] = round(min(2.0, bar_seconds * 0.5), 3) if index > 0 else 0.0
        section["tail_seconds"] = round(min(2.0, bar_seconds * 0.5), 3) if index + 1 < len(sections) else 0.0
        section["boundary_confidence"] = _boundary_confidence(start_delta, end_delta, bar_seconds, bar_grid)
        section["boundary"] = {
            "detected_start_seconds": round(detected_start, 3),
            "detected_end_seconds": round(detected_end, 3),
            "aligned_start_delta_seconds": round(start_delta, 3),
            "aligned_end_delta_seconds": round(end_delta, 3),
            "aligned_start_delta_bars": round(start_delta / max(0.001, bar_seconds), 3),
            "aligned_end_delta_bars": round(end_delta / max(0.001, bar_seconds), 3),
        }
        if abs(start_delta) > bar_seconds or abs(end_delta) > bar_seconds:
            repairs.append(
                {"section_id": section.get("id"), "kind": "large_boundary_repair", "start_delta_seconds": round(start_delta, 3), "end_delta_seconds": round(end_delta, 3)}
            )
    return repairs


def _blueprint_fidelity(analysis: dict, arrangement: dict, bar_grid: dict, repairs: list[dict]) -> dict:
    bpm = _number(arrangement.get("bpm"), 120.0)
    beat_seconds = 60.0 / max(1.0, bpm)
    duration = _number(arrangement.get("duration_seconds"), 0.0)
    source_duration = _number(analysis.get("duration_seconds"), duration)
    total_delta = duration - source_duration
    start_deltas = []
    length_deltas = []
    for section in arrangement.get("sections") or []:
        boundary = section.get("boundary") or {}
        start_deltas.append({"section_id": section.get("id"), "role": section.get("role"), "delta_seconds": boundary.get("aligned_start_delta_seconds", 0.0), "delta_bars": boundary.get("aligned_start_delta_bars", 0.0)})
        detected_len = _number(boundary.get("detected_end_seconds"), 0.0) - _number(boundary.get("detected_start_seconds"), 0.0)
        target_len = _number(section.get("target_duration_seconds"), detected_len)
        length_deltas.append({"section_id": section.get("id"), "role": section.get("role"), "delta_seconds": round(target_len - detected_len, 3), "delta_bars": round((target_len - detected_len) / max(0.001, _number(bar_grid.get("bar_seconds"), 1.0)), 3)})
    return {
        "total_duration_delta_seconds": round(total_delta, 3),
        "total_duration_delta_beats": round(total_delta / max(0.001, beat_seconds), 3),
        "section_start_deltas": start_deltas,
        "section_length_deltas": length_deltas,
        "repair_count": len(repairs),
    }


def _warnings(analysis: dict, arrangement: dict, bar_grid: dict, fidelity: dict, repairs: list[dict]) -> list[dict]:
    warnings: list[dict] = []
    sections = arrangement.get("sections") or []
    duration = _number(arrangement.get("duration_seconds"), _number(analysis.get("duration_seconds"), 0.0))
    if _number(analysis.get("bpm_confidence"), 0.0) < 0.45:
        warnings.append(_warning("weak_tempo_estimate", "medium", "BPM confidence is low; review the bar grid before rendering."))
    if bar_grid.get("confidence", 0.0) < 0.6:
        warnings.append(_warning("weak_downbeat_grid", "medium", "No reliable downbeat grid is available; boundaries use estimated BPM bars."))
    if bar_grid.get("tempo_drift", 0.0) > 0.08:
        warnings.append(_warning("tempo_drift", "high", "Detected downbeats are uneven enough to risk section drift."))
    if len(sections) <= 1:
        warnings.append(_warning("unclear_section_structure", "high", "Only one usable section was found."))
    if duration >= 180 and len(sections) < 4:
        warnings.append(_warning("too_few_sections_for_song", "medium", "Reference is long enough to need a richer section map; review before full rendering."))
    if sections and duration >= 180:
        first = sections[0]
        first_role = str(first.get("role") or "")
        first_duration = _number(first.get("target_duration_seconds"), _number(first.get("end_seconds"), 0.0) - _number(first.get("start_seconds"), 0.0))
        if first_role == "intro" and first_duration > duration * 0.45:
            warnings.append(_warning("long_intro_suspicious", "medium", "Intro covers nearly half the reference; section segmentation likely needs review."))
    if len(repairs) > 0:
        warnings.append(_warning("boundary_repairs", "medium", "One or more detected boundaries moved by more than one bar."))
    if any(section.get("boundary_confidence", 1.0) < 0.55 for section in sections):
        warnings.append(_warning("low_boundary_confidence", "medium", "At least one section boundary needs review."))
    if not _has_clear_roles(sections):
        warnings.append(_warning("unclear_section_labels", "medium", "Section labels are generic; review roles before ACE rendering."))
    if any(section.get("source_kind") == "phrase_subdivision" for section in sections):
        warnings.append(_warning("phrase_subdivision_used", "low", "Overlong detected spans were split into phrase-sized producer sections."))
    if any(section.get("source_kind") == "phrase_grid_normalized" for section in sections):
        warnings.append(_warning("phrase_grid_normalized", "low", "Long club structure was normalized to 8/16/32-bar producer phrases for stronger SUNO arrangement control."))

    vocals = analysis.get("vocals") or {}
    transform_vocals = ((analysis.get("reference_transform") or {}).get("vocals") or {})
    if vocals.get("present") and transform_vocals.get("preserve_role"):
        warnings.append(_warning("dense_vocal_hook_risk", "medium", "Reference appears vocal-led; keep Arrangement Lock timing but avoid copied lyrics, hook melody, and singer identity."))
    preflight = analysis.get("ace_preflight") or {}
    for risk in preflight.get("risks") or []:
        warnings.append(_warning(f"ace_{risk.get('code') or 'risk'}", str(risk.get("severity") or "medium"), str(risk.get("message") or "ACE preflight flagged this reference.")))
    return warnings


def _lock_confidence(analysis: dict, arrangement: dict, bar_grid: dict, fidelity: dict, warnings: list[dict]) -> float:
    method = str(arrangement.get("method") or "")
    sections = arrangement.get("sections") or []
    phrase_score = _phrase_grid_score(sections)
    phrase_normalized = any(section.get("source_kind") == "phrase_grid_normalized" for section in sections)
    method_score = 0.86 if "allin1" in method else 0.78 if phrase_normalized else 0.68 if "segmentation" in method else 0.46
    bpm_score = max(0.0, min(1.0, _number(analysis.get("bpm_confidence"), 0.55)))
    boundary_scores = [max(0.0, min(1.0, _number(s.get("boundary_confidence"), 0.5))) for s in sections]
    boundary_score = sum(boundary_scores) / len(boundary_scores) if boundary_scores else 0.25
    warning_penalty = sum(_warning_penalty(w) for w in warnings)
    repair_penalty = min(0.18, 0.04 * int(fidelity.get("repair_count") or 0))
    score = (method_score * 0.23) + (_number(bar_grid.get("confidence"), 0.4) * 0.24) + (bpm_score * 0.16) + (boundary_score * 0.23) + (phrase_score * 0.14)
    return round(max(0.05, min(0.98, score - warning_penalty - repair_penalty)), 3)


def _transition_out(section: dict, next_section: dict | None) -> str:
    if next_section is None:
        return "track_end"
    role = str(section.get("role") or "")
    next_role = str(next_section.get("role") or "")
    energy = _energy_rank(str(section.get("energy_level") or "medium"))
    next_energy = _energy_rank(str(next_section.get("energy_level") or "medium"))
    if next_role == "outro":
        return "outro_strip"
    if next_role == "breakdown" or next_energy <= energy - 2:
        return "breakdown_entry"
    if role == "breakdown" and next_energy >= energy + 2:
        return "drop_return"
    if next_energy > energy:
        return "buildup"
    if next_energy < energy:
        return "filter_down"
    return "steady_section_change"


def _boundary_confidence(start_delta: float, end_delta: float, bar_seconds: float, bar_grid: dict) -> float:
    worst = max(abs(start_delta), abs(end_delta)) / max(0.001, bar_seconds)
    alignment = max(0.0, 1.0 - min(1.0, worst))
    score = (alignment * 0.65) + (_number(bar_grid.get("confidence"), 0.4) * 0.35)
    return round(score, 3)


def _has_clear_roles(sections: list[dict]) -> bool:
    roles = {str(section.get("role") or "") for section in sections}
    return bool(roles & {"intro", "drop", "breakdown", "outro", "groove"}) and len(roles) >= 2


def _phrase_grid_score(sections: list[dict]) -> float:
    if not sections:
        return 0.2
    scores = []
    for index, section in enumerate(sections):
        bars = max(1, int(((section.get("locked_bar_range") or {}).get("bar_count")) or 1))
        if index == 0 or index == len(sections) - 1:
            scores.append(1.0 if 8 <= bars <= 32 else 0.55)
        elif bars in {8, 16, 32, 64}:
            scores.append(1.0)
        elif bars % 8 == 0:
            scores.append(0.86)
        else:
            scores.append(max(0.35, 1.0 - min(0.65, _distance_to_phrase(bars) * 0.09)))
    return sum(scores) / len(scores)


def _distance_to_phrase(bars: int) -> int:
    return min(abs(bars - target) for target in (8, 16, 32, 64))


def _tempo_drift(intervals: list[float], median: float) -> float:
    if not intervals or median <= 0:
        return 0.0
    return sum(abs(item - median) / median for item in intervals) / len(intervals)


def _warning(code: str, severity: str, message: str) -> dict:
    severity = severity if severity in {"low", "medium", "high"} else "medium"
    return {"code": code, "severity": severity, "message": message}


def _warning_penalty(warning: dict) -> float:
    code = str(warning.get("code") or "")
    if code == "dense_vocal_hook_risk" or code.startswith("ace_"):
        return 0.0
    severity = warning.get("severity")
    if severity == "high":
        return 0.14
    if severity == "medium":
        return 0.06
    return 0.0


def _energy_rank(level: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(level, 1)


def _numbers(values: list) -> list[float]:
    output = []
    for value in values:
        try:
            output.append(float(value))
        except (TypeError, ValueError):
            continue
    return output


def _number(value, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
