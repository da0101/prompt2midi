#!/usr/bin/env python3
"""Phase 1 WAV analysis for prompt2midi.

The first implementation is deliberately dependency-free so the local backend
can run on a fresh macOS machine. It supports uncompressed PCM WAV files and
returns stable JSON for the JUCE/Node contract.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import struct
import wave
from dataclasses import dataclass
from typing import Iterable


NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


@dataclass(frozen=True)
class AudioData:
    samples: list[float]
    sample_rate: int
    channels: int
    duration_seconds: float


class AnalysisError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def read_wav_mono(path: str) -> AudioData:
    if not os.path.exists(path):
        raise AnalysisError("audio_not_found", "Audio file does not exist.")

    if os.path.splitext(path)[1].lower() not in {".wav", ".wave"}:
        raise AnalysisError(
            "unsupported_format",
            "Phase 1 supports uncompressed PCM WAV files. MP3 decoding will be added after the decoder dependency is selected.",
        )

    try:
        with wave.open(path, "rb") as wav:
            channels = wav.getnchannels()
            sample_rate = wav.getframerate()
            sample_width = wav.getsampwidth()
            frame_count = wav.getnframes()
            frames = wav.readframes(frame_count)
    except wave.Error as exc:
        raise AnalysisError("invalid_wav", f"Could not read WAV file: {exc}") from exc

    if channels <= 0 or sample_rate <= 0:
        raise AnalysisError("invalid_wav", "WAV file has invalid channel or sample-rate metadata.")

    if sample_width not in (1, 2, 3, 4):
        raise AnalysisError("unsupported_bit_depth", f"Unsupported PCM sample width: {sample_width} bytes.")

    raw_samples = list(_decode_pcm(frames, sample_width))
    if not raw_samples:
        raise AnalysisError("empty_audio", "Audio file contains no samples.")

    mono: list[float] = []
    for index in range(0, len(raw_samples), channels):
        frame = raw_samples[index : index + channels]
        mono.append(sum(frame) / len(frame))

    return AudioData(
        samples=mono,
        sample_rate=sample_rate,
        channels=channels,
        duration_seconds=len(mono) / float(sample_rate),
    )


def _decode_pcm(frames: bytes, sample_width: int) -> Iterable[float]:
    if sample_width == 1:
        for value in frames:
            yield (value - 128) / 128.0
        return

    if sample_width == 2:
        for (value,) in struct.iter_unpack("<h", frames):
            yield max(-1.0, min(1.0, value / 32768.0))
        return

    if sample_width == 3:
        for index in range(0, len(frames), 3):
            chunk = frames[index : index + 3]
            if len(chunk) < 3:
                break
            value = int.from_bytes(chunk + (b"\xff" if chunk[2] & 0x80 else b"\x00"), "little", signed=True)
            yield max(-1.0, min(1.0, value / 8388608.0))
        return

    for (value,) in struct.iter_unpack("<i", frames):
        yield max(-1.0, min(1.0, value / 2147483648.0))


def analyze_wav(path: str) -> dict:
    audio = read_wav_mono(path)
    energy_curve = compute_energy_curve(audio.samples, audio.sample_rate)
    loudness = compute_loudness_dbfs(audio.samples)
    bpm = estimate_bpm(energy_curve)
    key = estimate_key(audio.samples, audio.sample_rate)

    return {
        "source_path": os.path.abspath(path),
        "duration_seconds": round(audio.duration_seconds, 3),
        "sample_rate": audio.sample_rate,
        "channels": audio.channels,
        "bpm": bpm,
        "key": key["key"],
        "key_confidence": key["confidence"],
        "energy_curve": energy_curve,
        "loudness": loudness,
        "spectral_features": {
            "zero_crossing_rate": round(zero_crossing_rate(audio.samples), 5),
            "peak_amplitude": round(max(abs(sample) for sample in audio.samples), 5),
        },
        "warnings": key["warnings"],
    }


def compute_energy_curve(samples: list[float], sample_rate: int, window_seconds: float = 0.1) -> list[dict]:
    window_size = max(1, int(sample_rate * window_seconds))
    curve: list[dict] = []
    for start in range(0, len(samples), window_size):
        window = samples[start : start + window_size]
        if not window:
            continue
        rms = math.sqrt(sum(sample * sample for sample in window) / len(window))
        curve.append({"time": round(start / sample_rate, 3), "energy": round(rms, 5)})
    return curve


def compute_loudness_dbfs(samples: list[float]) -> float:
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    if rms <= 0.000001:
        return -120.0
    return round(20.0 * math.log10(rms), 2)


def estimate_bpm(energy_curve: list[dict]) -> float | None:
    if len(energy_curve) < 8:
        return None

    energies = [point["energy"] for point in energy_curve]
    mean_energy = sum(energies) / len(energies)
    flux = [max(0.0, energies[index] - energies[index - 1]) for index in range(1, len(energies))]
    if max(flux, default=0.0) <= 0.00001:
        return None

    step_seconds = max(0.001, energy_curve[1]["time"] - energy_curve[0]["time"])
    best_lag = None
    best_score = 0.0
    for bpm in range(60, 181):
        lag = max(1, round((60.0 / bpm) / step_seconds))
        if lag >= len(flux):
            continue
        score = sum(flux[index] * flux[index - lag] for index in range(lag, len(flux)))
        score *= 1.0 + min(0.25, max(0.0, mean_energy))
        if score > best_score:
            best_lag = lag
            best_score = score

    if best_lag is None:
        return None
    return round(60.0 / (best_lag * step_seconds), 2)


def estimate_key(samples: list[float], sample_rate: int) -> dict:
    frequency = estimate_fundamental_frequency(samples, sample_rate)
    if frequency is None:
        return {"key": "Unknown", "confidence": 0.0, "warnings": ["Key estimate unavailable for low-signal audio."]}

    midi_note = round(69 + 12 * math.log2(frequency / 440.0))
    note_name = NOTE_NAMES[midi_note % 12]
    return {
        "key": f"{note_name} major",
        "confidence": 0.32,
        "warnings": ["Phase 1 key detection is a rough tonal-center estimate, not full chord/key analysis."],
    }


def estimate_fundamental_frequency(samples: list[float], sample_rate: int) -> float | None:
    max_samples = min(len(samples), sample_rate * 4)
    clipped = samples[:max_samples]
    threshold = max(0.02, max((abs(sample) for sample in clipped), default=0.0) * 0.15)
    crossings: list[int] = []
    previous = clipped[0] if clipped else 0.0
    for index, sample in enumerate(clipped[1:], start=1):
        if previous <= 0 < sample and abs(sample) >= threshold:
            crossings.append(index)
        previous = sample

    if len(crossings) < 4:
        return None

    periods = [crossings[index] - crossings[index - 1] for index in range(1, len(crossings))]
    average_period = sum(periods) / len(periods)
    if average_period <= 0:
        return None
    frequency = sample_rate / average_period
    if 40.0 <= frequency <= 2000.0:
        return frequency
    return None


def zero_crossing_rate(samples: list[float]) -> float:
    if len(samples) < 2:
        return 0.0
    crossings = 0
    previous = samples[0]
    for sample in samples[1:]:
        if (previous < 0 <= sample) or (previous >= 0 > sample):
            crossings += 1
        previous = sample
    return crossings / float(len(samples) - 1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze a WAV file and emit prompt2midi Phase 1 JSON.")
    parser.add_argument("audio_path")
    args = parser.parse_args()

    try:
        payload = {"ok": True, "analysis": analyze_wav(args.audio_path)}
    except AnalysisError as exc:
        payload = {"ok": False, "error": {"code": exc.code, "message": exc.message}}

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
