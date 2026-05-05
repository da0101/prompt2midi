#!/usr/bin/env python3
"""Arrangement Lock report/debug payload helpers."""
from __future__ import annotations


def lock_summary(confidence: float, review_required: bool, warnings: list[dict]) -> str:
    if review_required:
        return f"Structure needs review before full ACE rendering; confidence {confidence:.2f}, warnings {len(warnings)}."
    return f"Arrangement Lock map is ready for section generation; confidence {confidence:.2f}."


def reference_version(arrangement: dict) -> dict:
    duration = _number(arrangement.get("duration_seconds"), 0.0)
    if duration <= 0:
        return {"kind": "unknown", "duration_seconds": duration, "note": "Reference duration unavailable."}
    if duration < 240:
        return {
            "kind": "radio_edit_or_short_mix",
            "duration_seconds": round(duration, 3),
            "note": "Short references are valid Arrangement Lock inputs; preserve this shorter structure unless the user supplies an extended mix.",
        }
    if duration >= 360:
        return {
            "kind": "extended_or_club_mix",
            "duration_seconds": round(duration, 3),
            "note": "Long club references may include DJ intro/outro material; keep those sections if the user wants full arrangement lock.",
        }
    return {"kind": "standard_full_length", "duration_seconds": round(duration, 3), "note": "Reference duration is in a typical full-song range."}


def build_lock_report(arrangement: dict, warnings: list[dict]) -> dict:
    lock = arrangement.get("arrangement_lock") or {}
    fidelity = arrangement.get("blueprint_fidelity") or {}
    return {
        "version": 1,
        "status": lock.get("status"),
        "confidence": lock.get("confidence"),
        "review_required": lock.get("review_required"),
        "summary": lock.get("summary"),
        "bar_grid": arrangement.get("bar_grid") or {},
        "reference_version": arrangement.get("reference_version") or {},
        "blueprint_fidelity": fidelity,
        "warnings": warnings,
        "sections": [_lock_section(section) for section in arrangement.get("sections") or []],
    }


def build_structure_debug(analysis: dict, arrangement: dict, bar_grid: dict, repairs: list[dict], candidates: list[dict]) -> dict:
    structure = analysis.get("structure") or {}
    allin1 = analysis.get("allin1") or {}
    return {
        "version": 1,
        "method": arrangement.get("method"),
        "input_duration_seconds": analysis.get("duration_seconds"),
        "arrangement_duration_seconds": arrangement.get("duration_seconds"),
        "raw_structure": {
            "method": structure.get("method"),
            "section_count": structure.get("section_count"),
            "estimated_bars": structure.get("estimated_bars"),
            "sections": structure.get("sections") or [],
        },
        "allin1": {
            "available": bool(allin1.get("available")),
            "method": allin1.get("method"),
            "path": allin1.get("path"),
            "warnings": allin1.get("warnings") or [],
        },
        "bar_grid": bar_grid,
        "bar_grid_candidates": candidates,
        "reference_version": arrangement.get("reference_version") or {},
        "repairs": repairs,
    }


def _lock_section(section: dict) -> dict:
    return {
        "id": section.get("id"),
        "role": section.get("role"),
        "bars": section.get("locked_bar_range"),
        "transition_in": section.get("transition_in"),
        "transition_out": section.get("transition_out"),
        "boundary_confidence": section.get("boundary_confidence"),
        "target_duration_seconds": section.get("target_duration_seconds"),
        "source_kind": section.get("source_kind"),
        "source_confidence": section.get("source_confidence"),
    }


def _number(value, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
