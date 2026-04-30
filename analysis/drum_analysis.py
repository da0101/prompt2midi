#!/usr/bin/env python3
"""Drum stem onset analysis for prompt2midi — quantized to a 16th-note MIDI grid."""

from __future__ import annotations

import os

_FALLBACK: dict = {
    "kick": [],
    "snare": [],
    "hat": [],
    "swing": 0.0,
    "density": "medium",
    "tempo_feel": "balanced",
    "method": "unavailable",
}


def analyze_drums(drum_stem_path: str, bpm: float) -> dict:
    if os.environ.get("PROMPT2MIDI_DISABLE_DRUMS") == "1":
        return dict(_FALLBACK)

    if drum_stem_path is None or not os.path.exists(drum_stem_path):
        return dict(_FALLBACK)

    try:
        import numpy as np
        import librosa
        from scipy.signal import butter, sosfilt

        sr = 22050
        y, _ = librosa.load(drum_stem_path, sr=sr, mono=True)

        kick_band = _bandpass(y, sr, low=20, high=200)
        snare_band = _bandpass(y, sr, low=200, high=2000)
        hat_band = _bandpass(y, sr, low=2000, high=20000)

        kick_times = librosa.onset.onset_detect(y=kick_band, sr=sr, units="time", delta=0.07)
        snare_times = librosa.onset.onset_detect(y=snare_band, sr=sr, units="time", delta=0.07)
        hat_times = librosa.onset.onset_detect(y=hat_band, sr=sr, units="time", delta=0.07)

        sixteenth = 60.0 / bpm / 4.0
        duration = len(y) / sr
        bars = max(1, duration / (sixteenth * 16))

        kick_pos = _quantize_to_grid(kick_times, sixteenth)
        snare_pos = _quantize_to_grid(snare_times, sixteenth)
        hat_pos = _quantize_to_grid(hat_times, sixteenth)

        swing = _estimate_swing(hat_times, sixteenth)
        density = _classify_density(kick_pos, snare_pos, hat_pos, bars)
        tempo_feel = _classify_tempo_feel(hat_times, sixteenth)

        return {
            "kick": kick_pos,
            "snare": snare_pos,
            "hat": hat_pos,
            "swing": round(swing, 3),
            "density": density,
            "tempo_feel": tempo_feel,
            "method": "onset_detection",
        }

    except Exception:
        return dict(_FALLBACK)


def drum_pattern_to_midi_events(drums: dict, bpm: float, bars: int = 2) -> list[dict]:
    """Convert a quantized drum fingerprint into editable General MIDI events."""
    if not drums or drums.get("method") == "unavailable":
        return []
    sixteenth = 60.0 / max(40.0, min(220.0, bpm or 120.0)) / 4.0
    mapping = [("kick", 36, 112), ("snare", 38, 88), ("hat", 42, 72)]
    events: list[dict] = []
    for bar in range(max(1, bars)):
        bar_offset = bar * 16
        for key, note, velocity in mapping:
            for position in drums.get(key, []) or []:
                step = bar_offset + int(position)
                events.append(
                    {
                        "start": round(step * sixteenth, 3),
                        "duration": round(sixteenth * 0.75, 3),
                        "midi_note": note,
                        "velocity": velocity,
                        "channel": 9,
                        "confidence": 0.7,
                    }
                )
    return sorted(events, key=lambda event: (event["start"], event["midi_note"]))


def _bandpass(y, sr: int, low: float, high: float):
    import numpy as np
    from scipy.signal import butter, sosfilt

    nyq = sr / 2.0
    low_norm = max(0.001, low / nyq)
    high_norm = min(0.999, high / nyq)
    sos = butter(4, [low_norm, high_norm], btype="band", output="sos")
    return sosfilt(sos, y)


def _quantize_to_grid(onset_times, sixteenth: float) -> list[int]:
    positions: list[int] = []
    for t in onset_times:
        grid_index = int(round(t / sixteenth))
        pos = grid_index % 16
        if pos not in positions:
            positions.append(pos)
    return sorted(positions)


def _estimate_swing(hat_times, sixteenth: float) -> float:
    if len(hat_times) < 4:
        return 0.0

    deviations: list[float] = []
    for t in hat_times:
        grid_index = round(t / sixteenth)
        expected = grid_index * sixteenth
        deviation = (t - expected) / sixteenth
        if grid_index % 2 == 1:
            deviations.append(deviation)

    if not deviations:
        return 0.0

    mean_dev = sum(deviations) / len(deviations)
    swing = max(0.0, min(0.33, mean_dev))
    return swing


def _classify_density(kick_pos: list[int], snare_pos: list[int], hat_pos: list[int], bars: float) -> str:
    total_hits = len(kick_pos) + len(snare_pos) + len(hat_pos)
    hits_per_bar = total_hits / max(1.0, bars)
    if hits_per_bar < 6:
        return "sparse"
    if hits_per_bar > 14:
        return "dense"
    return "medium"


def _classify_tempo_feel(hat_times, sixteenth: float) -> str:
    if len(hat_times) < 4:
        return "tight"

    deviations: list[float] = []
    for t in hat_times:
        grid_index = round(t / sixteenth)
        expected = grid_index * sixteenth
        deviations.append(abs(t - expected))

    mean_abs_dev = sum(deviations) / len(deviations)
    threshold = sixteenth * 0.06
    if mean_abs_dev <= threshold:
        return "tight"
    return "loose"
