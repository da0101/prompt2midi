#!/usr/bin/env python3
"""Phase 3 analysis improvements: librosa-optional BPM/key, genre heuristics, groove estimation.

All functions degrade gracefully when librosa is not installed.
"""
from __future__ import annotations

import math
import os


def better_bpm(audio_path: str, fallback_bpm: float | None, fallback_confidence: float | None) -> dict:
    """Estimate BPM using librosa beat tracker if available, else return fallback."""
    if os.environ.get("PROMPT2MIDI_DISABLE_LIBROSA") == "1":
        return {"bpm": fallback_bpm, "confidence": fallback_confidence, "method": "autocorrelation"}
    try:
        import librosa
        import numpy as np
        y, sr = librosa.load(audio_path, sr=None, mono=True)
        tempo = librosa.beat.beat_track(y=y, sr=sr)[0]
        bpm = float(np.atleast_1d(tempo)[0])
        if bpm < 60:
            bpm *= 2
        elif bpm > 180:
            bpm /= 2
        return {"bpm": round(bpm, 2), "confidence": 0.82, "method": "librosa"}
    except ImportError:
        return {"bpm": fallback_bpm, "confidence": fallback_confidence, "method": "autocorrelation"}
    except Exception:
        return {"bpm": fallback_bpm, "confidence": fallback_confidence, "method": "autocorrelation"}


def better_key(audio_path: str, fallback_key: str | None, fallback_confidence: float | None) -> dict:
    """Estimate key using librosa chroma + Krumhansl-Schmuckler profiles if available."""
    if os.environ.get("PROMPT2MIDI_DISABLE_LIBROSA") == "1":
        return {"key": fallback_key, "confidence": fallback_confidence, "method": "fundamental_freq"}
    try:
        import librosa
        import numpy as np

        y, sr = librosa.load(audio_path, sr=None, mono=True, duration=60.0)
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_mean = np.mean(chroma, axis=1)

        major = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
        notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

        best_key = fallback_key or "C major"
        best_score = -2.0
        for i in range(12):
            rotated = np.roll(chroma_mean, -i)
            for profile, label in ((major, "major"), (minor, "minor")):
                score = float(np.corrcoef(rotated, profile)[0, 1])
                if score > best_score:
                    best_score = score
                    best_key = f"{notes[i]} {label}"

        confidence = round(min(0.88, max(0.55, best_score)), 2)
        return {"key": best_key, "confidence": confidence, "method": "librosa_chroma"}
    except ImportError:
        return {"key": fallback_key, "confidence": fallback_confidence, "method": "fundamental_freq"}
    except Exception:
        return {"key": fallback_key, "confidence": fallback_confidence, "method": "fundamental_freq"}


def infer_genre(analysis: dict) -> dict:
    """Heuristic genre tags from BPM, energy, and spectral features. No ML deps required."""
    bpm = float(analysis.get("bpm") or 120.0)
    curve = analysis.get("energy_curve") or []
    avg_energy = sum(pt.get("energy", 0.5) for pt in curve) / max(len(curve), 1)
    zcr = (analysis.get("spectral_features") or {}).get("zero_crossing_rate", 0.1)

    if 115 <= bpm <= 135:
        if avg_energy < 0.35 or zcr < 0.07:
            primary, tags = "Minimal House", ["minimal", "house", "deep", "club", "4/4"]
        elif avg_energy < 0.55:
            primary, tags = "Deep House", ["deep house", "house", "soulful", "club"]
        else:
            primary, tags = "House", ["house", "electronic", "4/4", "club", "driving"]
        confidence = 0.68
    elif 135 < bpm <= 150:
        primary, tags = "Techno", ["techno", "electronic", "dark", "driving", "industrial"]
        confidence = 0.65
    elif bpm > 150:
        primary, tags = "Hard Techno", ["hard techno", "industrial", "rave", "driving"]
        confidence = 0.60
    elif 90 <= bpm < 115:
        if zcr > 0.14 or avg_energy > 0.55:
            primary, tags = "Trap", ["trap", "hip-hop", "urban", "808", "hard"]
        else:
            primary, tags = "Hip-Hop", ["hip-hop", "lo-fi", "boom bap", "chill"]
        confidence = 0.58
    elif 70 <= bpm < 90:
        primary, tags = "Lo-Fi / Chill", ["lo-fi", "chill", "ambient", "relaxed"]
        confidence = 0.52
    else:
        primary, tags = "Electronic", ["electronic", "instrumental"]
        confidence = 0.40

    return {"primary": primary, "tags": tags, "confidence": round(confidence, 2)}


def estimate_groove(analysis: dict) -> dict:
    """Estimate groove feel from energy variance and spectral features."""
    curve = analysis.get("energy_curve") or []
    if not curve:
        return {"feel": "steady", "density": "medium", "description": "balanced groove"}

    energies = [pt.get("energy", 0.5) for pt in curve]
    avg = sum(energies) / len(energies)
    variance = sum((e - avg) ** 2 for e in energies) / len(energies)
    zcr = (analysis.get("spectral_features") or {}).get("zero_crossing_rate", 0.1)

    density = "high" if variance > 0.04 else "low" if variance < 0.01 else "medium"
    feel = "tight" if zcr < 0.07 else "loose" if zcr > 0.14 else "balanced"

    descriptions = {
        ("tight", "high"): "driving tight groove with punchy dynamics",
        ("tight", "medium"): "tight controlled groove",
        ("tight", "low"): "sparse tight groove",
        ("balanced", "high"): "dynamic balanced groove",
        ("balanced", "medium"): "steady balanced groove",
        ("balanced", "low"): "minimal steady groove",
        ("loose", "high"): "loose energetic groove",
        ("loose", "medium"): "loose relaxed groove",
        ("loose", "low"): "open airy groove",
    }
    description = descriptions.get((feel, density), "steady groove")
    return {"feel": feel, "density": density, "description": description}
