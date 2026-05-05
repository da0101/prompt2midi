#!/usr/bin/env python3
"""Stem-aware vocal role detection for reference-track prompting."""
from __future__ import annotations

import math
import os

from analysis.core.feature_extraction import AnalysisError, read_wav_mono


def analyze_vocal_role(stems: dict | None) -> dict:
    """Return a conservative vocal-role summary from separated stems."""
    stem_paths = (stems or {}).get("stems") or {}
    vocal_path = stem_paths.get("vocals")
    if not vocal_path:
        return {
            "available": False,
            "present": False,
            "role": "none",
            "confidence": 0.0,
            "warnings": ["No vocals stem was available for vocal role analysis."],
        }

    try:
        vocal_stats = _stem_stats(vocal_path)
    except (AnalysisError, OSError, ValueError) as exc:
        return {
            "available": False,
            "present": False,
            "role": "unknown",
            "confidence": 0.0,
            "source": os.path.abspath(vocal_path),
            "warnings": [f"Could not analyze vocals stem: {exc}"],
        }

    relative_level = _relative_vocal_level(vocal_stats["rms"], stem_paths)
    active_ratio = vocal_stats["active_ratio"]
    present = (
        vocal_stats["rms"] >= 0.018
        and active_ratio >= 0.08
        and (relative_level >= 0.08 or vocal_stats["peak"] >= 0.12)
    )
    if present and active_ratio >= 0.26 and relative_level >= 0.12:
        role = "lead vocal hook"
    elif present:
        role = "rhythmic vocal hook"
    else:
        role = "none"

    confidence = 0.0
    if present:
        confidence = min(0.92, 0.35 + active_ratio * 0.7 + min(0.25, relative_level))

    warnings = [
        "Vocal role is estimated from the separated vocals stem and may include bleed from synths or drums."
    ]
    return {
        "available": True,
        "present": present,
        "role": role,
        "confidence": round(confidence, 3),
        "active_ratio": round(active_ratio, 3),
        "rms": round(vocal_stats["rms"], 5),
        "peak": round(vocal_stats["peak"], 5),
        "relative_level": round(relative_level, 3),
        "source": os.path.abspath(vocal_path),
        "description": _description(role, active_ratio, relative_level),
        "generation_guidance": _generation_guidance(role),
        "warnings": warnings,
    }


def _stem_stats(path: str) -> dict:
    audio = read_wav_mono(path)
    samples = audio.samples
    if not samples:
        raise ValueError("empty stem")
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    peak = max(abs(sample) for sample in samples)
    window_size = max(1, int(audio.sample_rate * 0.1))
    windows = []
    for start in range(0, len(samples), window_size):
        window = samples[start : start + window_size]
        if window:
            windows.append(math.sqrt(sum(sample * sample for sample in window) / len(window)))
    threshold = max(0.006, rms * 0.55)
    active_ratio = 0.0 if not windows else sum(1 for value in windows if value >= threshold) / len(windows)
    return {"rms": rms, "peak": peak, "active_ratio": active_ratio}


def _relative_vocal_level(vocal_rms: float, stem_paths: dict) -> float:
    rms_values = [max(0.0, vocal_rms)]
    for name in ("bass", "drums", "other"):
        path = stem_paths.get(name)
        if not path:
            continue
        try:
            rms_values.append(_stem_stats(path)["rms"])
        except (AnalysisError, OSError, ValueError):
            continue
    total = sum(rms_values)
    if total <= 0.000001:
        return 0.0
    return max(0.0, min(1.0, vocal_rms / total))


def _description(role: str, active_ratio: float, relative_level: float) -> str:
    if role == "lead vocal hook":
        return (
            "prominent vocal character or hook is part of the reference identity; preserve a new vocal-hook role "
            "without copying the original singer, words, or exact melody"
        )
    if role == "rhythmic vocal hook":
        return (
            "short vocal phrases or chops contribute to the groove; preserve that role with new vocal material"
        )
    return (
        f"no clear vocal hook detected from stem activity {active_ratio:.2f} and relative level {relative_level:.2f}"
    )


def _generation_guidance(role: str) -> str:
    if role == "lead vocal hook":
        return "include a clear new vocal hook with original words, new voice, and new melody contour"
    if role == "rhythmic vocal hook":
        return "include short new vocal chops or phrases as rhythmic character"
    return "instrumental focus; vocal chops only if the style naturally needs them"
