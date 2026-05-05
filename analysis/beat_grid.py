#!/usr/bin/env python3
"""Dependency-optional beat/downbeat grid fallback."""
from __future__ import annotations

import os


def analyze_beat_grid(audio_path: str, bpm: float | None = None) -> dict:
    if os.environ.get("PROMPT2MIDI_DISABLE_BEAT_GRID") == "1":
        return _unavailable("disabled by PROMPT2MIDI_DISABLE_BEAT_GRID")
    if not audio_path or not os.path.exists(audio_path):
        return _unavailable("audio path is missing")
    try:
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache", "numba")
        os.makedirs(cache_dir, exist_ok=True)
        os.environ.setdefault("NUMBA_CACHE_DIR", cache_dir)
        import librosa

        y, sr = librosa.load(audio_path, sr=22050, mono=True)
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, trim=False, units="frames")
        beats = [float(item) for item in librosa.frames_to_time(beat_frames, sr=sr)]
        if len(beats) < 4:
            return _unavailable("librosa found fewer than four beats")
        tempo_value = _number(tempo[0] if hasattr(tempo, "__len__") else tempo, _number(bpm, 120.0))
        downbeats = _estimate_downbeats(beats, tempo_value)
        return {
            "available": True,
            "method": "librosa_beat_track_downbeat_estimate",
            "bpm": round(tempo_value, 3),
            "beats": [round(item, 3) for item in beats],
            "downbeats": [round(item, 3) for item in downbeats],
            "beat_positions": [((index % 4) + 1) for index in range(len(beats))],
            "confidence": _confidence(beats, downbeats, tempo_value, bpm),
            "warnings": ["Downbeats are estimated every four beats from the beat tracker, not model-classified."],
        }
    except Exception as exc:
        return _unavailable(f"librosa beat grid failed: {exc}")


def _estimate_downbeats(beats: list[float], tempo: float) -> list[float]:
    if len(beats) < 4:
        return []
    beat_seconds = 60.0 / max(1.0, tempo)
    best_offset = 0
    best_score = None
    for offset in range(4):
        selected = beats[offset::4]
        if len(selected) < 2:
            continue
        intervals = [b - a for a, b in zip(selected, selected[1:])]
        score = sum(abs(item - beat_seconds * 4.0) for item in intervals) / len(intervals)
        if best_score is None or score < best_score:
            best_score = score
            best_offset = offset
    return beats[best_offset::4]


def _confidence(beats: list[float], downbeats: list[float], tempo: float, expected_bpm: float | None) -> float:
    if len(beats) < 8 or len(downbeats) < 2:
        return 0.35
    intervals = [b - a for a, b in zip(beats, beats[1:]) if b > a]
    target = 60.0 / max(1.0, tempo)
    jitter = sum(abs(item - target) / target for item in intervals) / max(1, len(intervals))
    bpm_delta = abs(tempo - _number(expected_bpm, tempo)) / max(1.0, tempo)
    coverage_bonus = min(0.08, max(0.0, (len(downbeats) - 32) / 400.0))
    stable_long_grid_bonus = 0.05 if len(downbeats) >= 64 and jitter < 0.02 else 0.0
    return round(max(0.35, min(0.9, 0.78 + coverage_bonus + stable_long_grid_bonus - jitter * 0.8 - bpm_delta * 0.5)), 3)


def _unavailable(reason: str) -> dict:
    return {"available": False, "method": "librosa_beat_track_downbeat_estimate", "warnings": [reason]}


def _number(value, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
