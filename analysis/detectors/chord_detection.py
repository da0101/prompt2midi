#!/usr/bin/env python3
"""Chord progression detection for prompt2midi via chroma template matching."""

from __future__ import annotations

import os

_FALLBACK = {"progression": [], "progression_per_bar": [], "confidence": 0.0, "method": "disabled"}

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

_MAJOR_PROFILE = [1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1]
_MINOR_PROFILE = [1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0]


def detect_chords(audio_path: str, bpm: float) -> dict:
    if os.environ.get("PROMPT2MIDI_DISABLE_CHORDS") == "1":
        return _FALLBACK.copy()

    try:
        import librosa
        import numpy as np

        y, sr = librosa.load(audio_path, sr=22050, mono=True)

        start_bpm = float(bpm) if bpm and bpm > 0 else None
        beat_track_kwargs: dict = {"y": y, "sr": sr}
        if start_bpm is not None:
            beat_track_kwargs["start_bpm"] = start_bpm
        tempo_result, beat_frames = librosa.beat.beat_track(**beat_track_kwargs)

        beat_frames = np.atleast_1d(beat_frames)
        if len(beat_frames) < 4:
            return _FALLBACK.copy()

        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_synced = librosa.util.sync(chroma, beat_frames, aggregate=np.median)

        templates = _build_templates()
        chord_names = _build_chord_names()

        n_beats = chroma_synced.shape[1]
        beat_chords: list[str] = []
        beat_scores: list[float] = []

        for b in range(n_beats):
            chroma_vec = chroma_synced[:, b]
            norm = np.linalg.norm(chroma_vec)
            if norm < 1e-6:
                beat_chords.append(chord_names[0])
                beat_scores.append(0.0)
                continue
            chroma_norm = chroma_vec / norm
            similarities = templates @ chroma_norm
            best_idx = int(np.argmax(similarities))
            beat_chords.append(chord_names[best_idx])
            beat_scores.append(float(similarities[best_idx]))

        confidence = float(np.mean(beat_scores)) if beat_scores else 0.0
        confidence = round(min(1.0, max(0.0, confidence)), 2)

        n_bars = max(1, n_beats // 4)
        progression_per_bar: list[str] = []
        for bar in range(n_bars):
            start = bar * 4
            end = min(start + 4, n_beats)
            bar_chords = beat_chords[start:end]
            if not bar_chords:
                continue
            majority = max(set(bar_chords), key=bar_chords.count)
            progression_per_bar.append(majority)

        progression = _deduplicate_consecutive(progression_per_bar)

        return {
            "progression": progression,
            "progression_per_bar": progression_per_bar,
            "confidence": confidence,
            "method": "chroma_template_matching",
        }

    except Exception:
        return _FALLBACK.copy()


def _build_templates() -> "np.ndarray":
    import numpy as np

    raw_major = np.array(_MAJOR_PROFILE, dtype=float)
    raw_minor = np.array(_MINOR_PROFILE, dtype=float)
    templates: list[np.ndarray] = []
    for i in range(12):
        t_maj = np.roll(raw_major, i)
        t_maj = t_maj / (np.linalg.norm(t_maj) or 1.0)
        templates.append(t_maj)
    for i in range(12):
        t_min = np.roll(raw_minor, i)
        t_min = t_min / (np.linalg.norm(t_min) or 1.0)
        templates.append(t_min)
    return np.stack(templates)


def _build_chord_names() -> list[str]:
    major_names = list(_NOTE_NAMES)
    minor_names = [f"{n}m" for n in _NOTE_NAMES]
    return major_names + minor_names


def _deduplicate_consecutive(seq: list[str]) -> list[str]:
    if not seq:
        return []
    result = [seq[0]]
    for item in seq[1:]:
        if item != result[-1]:
            result.append(item)
    return result
