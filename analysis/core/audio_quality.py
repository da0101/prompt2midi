#!/usr/bin/env python3
"""Fast sanity scoring for generated music candidates."""
from __future__ import annotations

import math
import os

from analysis.core.feature_extraction import read_wav_mono


def score_audio_candidate(path: str, target_duration: float = 30.0) -> dict:
    if not path or not os.path.exists(path):
        return {"score": 0.0, "warnings": ["Candidate file is missing."]}

    audio = read_wav_mono(path)
    samples = audio.samples
    if not samples:
        return {"score": 0.0, "warnings": ["Candidate contains no samples."]}

    duration_score = max(0.0, 1.0 - abs(audio.duration_seconds - target_duration) / max(1.0, target_duration))
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    peak = max(abs(sample) for sample in samples)
    loudness_score = _triangular(rms, ideal=0.16, width=0.14)
    clipping_penalty = min(0.4, sum(1 for sample in samples if abs(sample) > 0.98) / len(samples) * 30.0)

    windows = _window_rms(samples, audio.sample_rate)
    pulse_score = _pulse_consistency(windows)
    silence_penalty = min(0.4, sum(1 for value in windows if value < 0.01) / max(1, len(windows)))
    zcr = _zero_crossing_rate(samples[:: max(1, audio.sample_rate // 12000)])
    window_zcr = _window_zcr(samples, audio.sample_rate)
    timbre_score = _timbre_sanity(zcr, window_zcr)
    harsh_penalty = max(0.0, min(0.45, (zcr - 0.18) * 2.5))
    artifact_penalty = 0.10 if timbre_score < 0.45 else 0.0

    score = (
        0.22 * duration_score
        + 0.16 * loudness_score
        + 0.42 * pulse_score
        + 0.10 * min(1.0, peak / 0.35)
        + 0.10 * timbre_score
        - clipping_penalty
        - silence_penalty
        - harsh_penalty
        - artifact_penalty
    )
    warnings: list[str] = []
    if zcr > 0.18:
        warnings.append("High zero-crossing rate suggests noisy or harsh high-frequency content.")
    if timbre_score < 0.45:
        warnings.append("Unstable timbre profile; candidate may contain synthetic artifacts.")
    if pulse_score < 0.25:
        warnings.append("Weak rhythmic pulse; candidate may not read as dance music.")
    if rms < 0.025:
        warnings.append("Low loudness; candidate may be too quiet or sparse.")
    return {
        "score": round(max(0.0, min(1.0, score)), 3),
        "duration_seconds": round(audio.duration_seconds, 3),
        "rms": round(rms, 5),
        "peak": round(peak, 5),
        "zero_crossing_rate": round(zcr, 5),
        "pulse_score": round(pulse_score, 3),
        "timbre_score": round(timbre_score, 3),
        "warnings": warnings,
    }


def _triangular(value: float, ideal: float, width: float) -> float:
    return max(0.0, 1.0 - abs(value - ideal) / max(0.0001, width))


def _window_rms(samples: list[float], sample_rate: int) -> list[float]:
    size = max(1, int(sample_rate * 0.25))
    values = []
    for start in range(0, len(samples), size):
        chunk = samples[start : start + size]
        if chunk:
            values.append(math.sqrt(sum(sample * sample for sample in chunk) / len(chunk)))
    return values


def _window_zcr(samples: list[float], sample_rate: int) -> list[float]:
    size = max(2, int(sample_rate * 0.5))
    values = []
    for start in range(0, len(samples), size):
        chunk = samples[start : start + size]
        if len(chunk) >= 2:
            values.append(_zero_crossing_rate(chunk[:: max(1, sample_rate // 12000)]))
    return values


def _timbre_sanity(global_zcr: float, window_zcr: list[float]) -> float:
    if not window_zcr:
        return _triangular(global_zcr, ideal=0.11, width=0.12)
    mean = sum(window_zcr) / len(window_zcr)
    variance = sum((value - mean) ** 2 for value in window_zcr) / len(window_zcr)
    stability = max(0.0, 1.0 - math.sqrt(variance) / 0.08)
    brightness = _triangular(global_zcr, ideal=0.11, width=0.12)
    return max(0.0, min(1.0, 0.65 * brightness + 0.35 * stability))


def _pulse_consistency(values: list[float]) -> float:
    if len(values) < 8:
        return 0.0
    mean = sum(values) / len(values)
    if mean <= 0.00001:
        return 0.0
    flux = [max(0.0, values[index] - values[index - 1]) for index in range(1, len(values))]
    if max(flux, default=0.0) <= 0.00001:
        return 0.0
    best = 0.0
    total = 0.0
    for lag in range(2, min(16, len(flux) // 2)):
        score = sum(flux[index] * flux[index - lag] for index in range(lag, len(flux)))
        best = max(best, score)
        total += score
    return 0.0 if total <= 0 else max(0.0, min(1.0, best / total * 3.5))


def _zero_crossing_rate(samples: list[float]) -> float:
    if len(samples) < 2:
        return 0.0
    crossings = 0
    previous = samples[0]
    for sample in samples[1:]:
        if (previous < 0 <= sample) or (previous >= 0 > sample):
            crossings += 1
        previous = sample
    return crossings / float(len(samples) - 1)
