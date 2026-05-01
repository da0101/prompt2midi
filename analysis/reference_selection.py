#!/usr/bin/env python3
"""Select a musically useful reference section for generation conditioning."""
from __future__ import annotations

import math
import os
import shutil
import subprocess
from pathlib import Path

from feature_extraction import AnalysisError, read_wav_mono


def prepare_reference_section(
    audio_path: str,
    output_dir: str,
    duration_seconds: float = 30.0,
    strategy: str | None = None,
) -> dict:
    """Export a representative groove section and return metadata about the choice."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    audio = _read_audio_for_selection(audio_path, output_dir)
    requested = max(10.0, float(duration_seconds))
    section_duration = min(requested, max(1.0, audio.duration_seconds))
    start = _configured_start(audio.duration_seconds, section_duration)
    method = "configured_start"
    if start is None:
        strategy = strategy or os.environ.get("PROMPT2MIDI_REFERENCE_SECTION_STRATEGY") or "stable_energy"
        start = _choose_start(audio.samples, audio.sample_rate, audio.duration_seconds, section_duration, strategy)
        method = "early_character_window" if strategy == "early_character" else "stable_energy_groove_window"

    output_path = os.path.abspath(os.path.join(output_dir, "reference-section.wav"))
    _extract_wav(audio_path, output_path, start, section_duration)
    return {
        "path": output_path,
        "start_seconds": round(start, 3),
        "duration_seconds": round(section_duration, 3),
        "source_duration_seconds": round(audio.duration_seconds, 3),
        "method": method,
    }


def _configured_start(total_seconds: float, duration_seconds: float) -> float | None:
    configured = os.environ.get("PROMPT2MIDI_REFERENCE_SECTION_START")
    if configured in (None, ""):
        return None
    try:
        start = float(str(configured).rstrip("s"))
    except ValueError:
        return None
    return min(max(0.0, start), max(0.0, total_seconds - duration_seconds))


def _choose_start(
    samples: list[float],
    sample_rate: int,
    total_seconds: float,
    duration_seconds: float,
    strategy: str = "stable_energy",
) -> float:
    if total_seconds <= duration_seconds + 0.5:
        return 0.0

    hop_seconds = 2.0
    window = max(1, int(duration_seconds * sample_rate))
    hop = max(1, int(hop_seconds * sample_rate))
    margin = min(20.0, max(4.0, total_seconds * 0.08))
    first = int(margin * sample_rate)
    last = max(first, int((total_seconds - duration_seconds - margin) * sample_rate))
    if strategy == "early_character":
        first_seconds = min(max(8.0, total_seconds * 0.04), max(0.0, total_seconds - duration_seconds))
        last_seconds = min(max(first_seconds, total_seconds * 0.42), max(first_seconds, 90.0), max(0.0, total_seconds - duration_seconds))
        first = int(first_seconds * sample_rate)
        last = max(first, int(last_seconds * sample_rate))

    best_start = first
    best_score = -1.0
    for start in range(first, last + 1, hop):
        segment = samples[start : start + window]
        if len(segment) < window // 2:
            continue
        score = _segment_score(segment, sample_rate)
        if score > best_score:
            best_score = score
            best_start = start
    return min(max(0.0, best_start / sample_rate), max(0.0, total_seconds - duration_seconds))


def _segment_score(segment: list[float], sample_rate: int) -> float:
    second = max(1, sample_rate)
    rms_values: list[float] = []
    zcr_values: list[float] = []
    for start in range(0, len(segment), second):
        chunk = segment[start : start + second]
        if not chunk:
            continue
        rms = math.sqrt(sum(sample * sample for sample in chunk) / len(chunk))
        zcr = _zero_crossing_rate(chunk)
        rms_values.append(rms)
        zcr_values.append(zcr)

    if not rms_values:
        return 0.0
    mean_rms = sum(rms_values) / len(rms_values)
    variance = sum((value - mean_rms) ** 2 for value in rms_values) / len(rms_values)
    steadiness = 1.0 / (1.0 + 8.0 * math.sqrt(variance))
    silence_penalty = sum(1 for value in rms_values if value < mean_rms * 0.35) / len(rms_values)
    high_noise = max(0.0, (sum(zcr_values) / len(zcr_values)) - 0.18)
    return mean_rms * steadiness * (1.0 - 0.7 * silence_penalty) * (1.0 - min(0.7, high_noise * 3.0))


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


def _extract_wav(source: str, output: str, start_seconds: float, duration_seconds: float) -> None:
    ffmpeg = os.environ.get("PROMPT2MIDI_FFMPEG") or shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to export the selected reference section.")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{start_seconds:.3f}",
            "-t",
            f"{duration_seconds:.3f}",
            "-i",
            source,
            "-ac",
            "2",
            "-ar",
            "48000",
            output,
        ],
        check=True,
    )


def _read_audio_for_selection(audio_path: str, output_dir: str):
    try:
        return read_wav_mono(audio_path)
    except AnalysisError:
        decoded = os.path.abspath(os.path.join(output_dir, "reference-input.wav"))
        _extract_wav(audio_path, decoded, 0.0, 10 * 60 * 60.0)
        return read_wav_mono(decoded)
