#!/usr/bin/env python3
"""Drum stem onset analysis for prompt2midi — quantized to a 16th-note MIDI grid."""

from __future__ import annotations

import math
import os
import struct
import wave

_FALLBACK: dict = {
    "kick": [],
    "snare": [],
    "hat": [],
    "swing": 0.0,
    "density": "medium",
    "tempo_feel": "balanced",
    "percussion_character": "unknown",
    "hits_per_bar": 0.0,
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
        onset_rates = {
            "kick": len(kick_times) / bars,
            "snare_mid": len(snare_times) / bars,
            "hat_high": len(hat_times) / bars,
        }
        energy = {
            "kick": _rms(kick_band),
            "snare_mid": _rms(snare_band),
            "hat_high": _rms(hat_band),
        }

        swing = _estimate_swing(hat_times, sixteenth)
        density = _classify_density(onset_rates)
        tempo_feel = _classify_tempo_feel(hat_times, sixteenth)
        percussion_character = _classify_percussion_character(onset_rates, energy, density)

        return {
            "kick": kick_pos,
            "snare": snare_pos,
            "hat": hat_pos,
            "swing": round(swing, 3),
            "density": density,
            "tempo_feel": tempo_feel,
            "percussion_character": percussion_character,
            "hits_per_bar": round(sum(onset_rates.values()), 2),
            "onsets_per_bar": {key: round(value, 2) for key, value in onset_rates.items()},
            "method": "onset_detection",
        }

    except Exception:
        return _analyze_drums_fallback(drum_stem_path, bpm)


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


def _rms(y) -> float:
    import numpy as np

    return float(np.sqrt(np.mean(y * y))) if len(y) else 0.0


def _classify_density(onset_rates: dict[str, float]) -> str:
    hits_per_bar = sum(onset_rates.values())
    if hits_per_bar < 5:
        return "sparse"
    if hits_per_bar >= 18:
        return "dense"
    return "medium"


def _classify_percussion_character(onset_rates: dict[str, float], energy: dict[str, float], density: str) -> str:
    mid = onset_rates.get("snare_mid", 0.0)
    high = onset_rates.get("hat_high", 0.0)
    kick = onset_rates.get("kick", 0.0)
    mid_high_energy = energy.get("snare_mid", 0.0) + energy.get("hat_high", 0.0)
    kick_energy = max(0.001, energy.get("kick", 0.0))
    if density == "dense" and mid + high >= 10.0 and mid_high_energy / kick_energy >= 0.35:
        return "tribal_percussion"
    if high >= 8.0 and density in {"medium", "dense"}:
        return "hat_shaker_driven"
    if kick >= 6.0 and density != "dense":
        return "kick_led"
    return "balanced_drums"


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


def _analyze_drums_fallback(drum_stem_path: str, bpm: float) -> dict:
    """Dependency-free onset fallback for environments without librosa/scipy."""
    try:
        samples, sample_rate = _read_wav_mono(drum_stem_path)
    except (OSError, wave.Error, ValueError, struct.error):
        return dict(_FALLBACK)
    if not samples:
        return dict(_FALLBACK)

    window_size = max(1, int(sample_rate * 0.02))
    windows = []
    for start in range(0, len(samples), window_size):
        window = samples[start : start + window_size]
        if not window:
            continue
        rms = math.sqrt(sum(sample * sample for sample in window) / len(window))
        zcr = _zero_crossing_rate(window)
        windows.append({"time": start / sample_rate, "rms": rms, "zcr": zcr})
    if len(windows) < 3:
        return dict(_FALLBACK)

    mean_rms = sum(window["rms"] for window in windows) / len(windows)
    peak_rms = max(window["rms"] for window in windows)
    threshold = max(mean_rms * 1.7, peak_rms * 0.28, 0.01)
    min_gap = max(0.045, 60.0 / max(40.0, min(220.0, bpm or 120.0)) / 8.0)
    onsets = []
    last_time = -999.0
    for index in range(1, len(windows)):
        current = windows[index]
        previous = windows[index - 1]
        novelty = current["rms"] - previous["rms"]
        if current["rms"] < threshold or novelty < mean_rms * 0.25:
            continue
        if current["time"] - last_time < min_gap:
            continue
        onsets.append(current)
        last_time = current["time"]

    if not onsets:
        return dict(_FALLBACK)

    kick_times = []
    snare_times = []
    hat_times = []
    for onset in onsets:
        if onset["zcr"] < 0.055:
            kick_times.append(onset["time"])
        elif onset["zcr"] >= 0.16:
            hat_times.append(onset["time"])
        else:
            snare_times.append(onset["time"])

    sixteenth = 60.0 / max(40.0, min(220.0, bpm or 120.0)) / 4.0
    duration = len(samples) / sample_rate
    bars = max(1, duration / (sixteenth * 16))
    onset_rates = {
        "kick": len(kick_times) / bars,
        "snare_mid": len(snare_times) / bars,
        "hat_high": len(hat_times) / bars,
    }
    density = _classify_density(onset_rates)
    energy = {
        "kick": sum(w["rms"] for w in windows if w["zcr"] < 0.055) / max(1, sum(1 for w in windows if w["zcr"] < 0.055)),
        "snare_mid": sum(w["rms"] for w in windows if 0.055 <= w["zcr"] < 0.16) / max(1, sum(1 for w in windows if 0.055 <= w["zcr"] < 0.16)),
        "hat_high": sum(w["rms"] for w in windows if w["zcr"] >= 0.16) / max(1, sum(1 for w in windows if w["zcr"] >= 0.16)),
    }
    kick_pos = _dominant_grid_positions(kick_times, sixteenth, bars, min_support_ratio=0.18, max_positions=4)
    snare_pos = _dominant_grid_positions(snare_times, sixteenth, bars, min_support_ratio=0.16, max_positions=4)
    hat_pos = _dominant_grid_positions(hat_times, sixteenth, bars, min_support_ratio=0.2, max_positions=8)
    if len(kick_pos) + len(snare_pos) + len(hat_pos) > 12:
        kick_pos = _limit_positions(kick_pos, preferred=(0, 4, 8, 12), max_positions=4)
        snare_pos = _limit_positions(snare_pos, preferred=(4, 12, 8, 0), max_positions=3)
        hat_pos = _limit_positions(hat_pos, preferred=(2, 6, 10, 14, 0, 4, 8, 12), max_positions=5)
    method = "onset_detection_fallback"
    warnings = ["Dependency-free drum fallback used because librosa/scipy onset analysis was unavailable."]
    if _should_use_house_four_on_floor_prior(bpm, kick_pos, snare_pos, hat_pos, onset_rates):
        kick_pos = [0, 4, 8, 12]
        snare_pos = [4, 12]
        hat_pos = [2, 6, 10, 14]
        method = "house_four_on_floor_fallback"
        warnings.append(
            "Fallback onset evidence was ambiguous; exported a conservative 4/4 house kick-clap-offbeat-hat pattern for review."
        )

    return {
        "kick": kick_pos,
        "snare": snare_pos,
        "hat": hat_pos,
        "swing": round(_estimate_swing(hat_times, sixteenth), 3),
        "density": density,
        "tempo_feel": _classify_tempo_feel([onset["time"] for onset in onsets], sixteenth),
        "percussion_character": _classify_percussion_character(onset_rates, energy, density),
        "hits_per_bar": round(sum(onset_rates.values()), 2),
        "onsets_per_bar": {key: round(value, 2) for key, value in onset_rates.items()},
        "method": method,
        "warnings": warnings,
    }


def _read_wav_mono(path: str) -> tuple[list[float], int]:
    with wave.open(path, "rb") as handle:
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        sample_rate = handle.getframerate()
        frame_count = handle.getnframes()
        frames = handle.readframes(frame_count)
    if sample_width not in (1, 2, 3, 4):
        raise ValueError(f"unsupported sample width {sample_width}")
    samples = []
    stride = sample_width * channels
    for offset in range(0, len(frames), stride):
        values = []
        for channel in range(channels):
            start = offset + channel * sample_width
            raw = frames[start : start + sample_width]
            if len(raw) == sample_width:
                values.append(_decode_pcm(raw, sample_width))
        if values:
            samples.append(sum(values) / len(values))
    return samples, sample_rate


def _dominant_grid_positions(
    onset_times: list[float],
    sixteenth: float,
    bars: float,
    *,
    min_support_ratio: float,
    max_positions: int,
) -> list[int]:
    if not onset_times:
        return []
    counts: dict[int, int] = {}
    for time in onset_times:
        position = int(round(time / sixteenth)) % 16
        counts[position] = counts.get(position, 0) + 1
    min_support = max(2, int(round(max(1.0, bars) * min_support_ratio)))
    supported = [position for position, count in counts.items() if count >= min_support]
    ranked = sorted(supported, key=lambda position: (-counts[position], position))
    return sorted(ranked[:max_positions])


def _limit_positions(positions: list[int], *, preferred: tuple[int, ...], max_positions: int) -> list[int]:
    selected = [position for position in preferred if position in positions]
    for position in positions:
        if position not in selected:
            selected.append(position)
        if len(selected) >= max_positions:
            break
    return sorted(selected[:max_positions])


def _should_use_house_four_on_floor_prior(
    bpm: float,
    kick_pos: list[int],
    snare_pos: list[int],
    hat_pos: list[int],
    onset_rates: dict[str, float],
) -> bool:
    tempo = max(40.0, min(220.0, bpm or 120.0))
    if not 118.0 <= tempo <= 138.0:
        return False
    all_positions = kick_pos + snare_pos + hat_pos
    if len(all_positions) < 8:
        return False
    overlap_count = len(set(kick_pos) & set(snare_pos)) + len(set(kick_pos) & set(hat_pos)) + len(set(snare_pos) & set(hat_pos))
    total_rate = sum(onset_rates.values())
    missing_quarter_kicks = any(position not in kick_pos for position in (0, 4, 8, 12))
    return overlap_count >= 2 or (missing_quarter_kicks and total_rate <= 8.0)


def _decode_pcm(raw: bytes, sample_width: int) -> float:
    if sample_width == 1:
        return (raw[0] - 128) / 128.0
    if sample_width == 2:
        return struct.unpack("<h", raw)[0] / 32768.0
    if sample_width == 3:
        padded = raw + (b"\xff" if raw[-1] & 0x80 else b"\x00")
        return struct.unpack("<i", padded)[0] / 8388608.0
    return struct.unpack("<i", raw)[0] / 2147483648.0


def _zero_crossing_rate(samples: list[float]) -> float:
    if len(samples) < 2:
        return 0.0
    crossings = 0
    previous = samples[0]
    for sample in samples[1:]:
        if (previous < 0 <= sample) or (previous > 0 >= sample):
            crossings += 1
        previous = sample
    return crossings / (len(samples) - 1)
