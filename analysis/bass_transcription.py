#!/usr/bin/env python3
"""Experimental monophonic bass transcription for prompt2midi."""

from __future__ import annotations

import math
from dataclasses import dataclass

from feature_extraction import AudioData, read_wav_mono


@dataclass(frozen=True)
class NoteEvent:
    start: float
    duration: float
    midi_note: int
    velocity: int
    confidence: float


def transcribe_bassline(path: str, bpm: float | None) -> dict:
    audio = read_wav_mono(path)
    beat_seconds = 60.0 / max(40.0, min(180.0, bpm or 120.0))
    window_seconds = max(0.22, min(0.5, beat_seconds * 0.5))
    raw_events = _detect_window_notes(audio, window_seconds)
    events = _merge_events(raw_events, max_gap=window_seconds * 0.6)
    confidence = _overall_confidence(events)

    warnings = [
        "Bass transcription is experimental monophonic low-frequency pitch tracking, not full source separation."
    ]
    if confidence < 0.35:
        warnings.append("Bass transcription confidence is low; use the MIDI as an editable starting point.")

    return {
        "events": [event.__dict__ for event in events],
        "confidence": confidence,
        "warnings": warnings,
    }


def _detect_window_notes(audio: AudioData, window_seconds: float) -> list[NoteEvent]:
    window_size = max(512, int(audio.sample_rate * window_seconds))
    hop_size = window_size
    max_rms = _max_window_rms(audio.samples, window_size, hop_size)
    if max_rms <= 0.000001:
        return []

    events: list[NoteEvent] = []
    for start in range(0, max(0, len(audio.samples) - window_size + 1), hop_size):
        window = audio.samples[start : start + window_size]
        rms = math.sqrt(sum(sample * sample for sample in window) / len(window))
        if rms < max(0.01, max_rms * 0.18):
            continue

        pitch = _estimate_window_pitch(window, audio.sample_rate)
        if pitch is None:
            continue

        midi_note, pitch_confidence = pitch
        velocity = max(35, min(112, round(35 + 77 * min(1.0, rms / max_rms))))
        events.append(
            NoteEvent(
                start=round(start / audio.sample_rate, 3),
                duration=round(window_seconds, 3),
                midi_note=midi_note,
                velocity=velocity,
                confidence=pitch_confidence,
            )
        )

    return events


def _max_window_rms(samples: list[float], window_size: int, hop_size: int) -> float:
    best = 0.0
    for start in range(0, max(0, len(samples) - window_size + 1), hop_size):
        window = samples[start : start + window_size]
        if window:
            best = max(best, math.sqrt(sum(sample * sample for sample in window) / len(window)))
    return best


def _estimate_window_pitch(window: list[float], sample_rate: int) -> tuple[int, float] | None:
    if len(window) < 128:
        return None

    if sample_rate > 5000:
        stride = max(1, round(sample_rate / 4000))
        window = window[::stride]
        sample_rate = round(sample_rate / stride)

    centered = _remove_dc(window)
    min_lag = max(1, int(sample_rate / 260.0))
    max_lag = min(len(centered) // 2, int(sample_rate / 45.0))
    if min_lag >= max_lag:
        return None

    energy = sum(sample * sample for sample in centered)
    if energy <= 0.000001:
        return None

    best_lag = 0
    best_score = 0.0
    sample_step = max(1, len(centered) // 384)
    for lag in range(min_lag, max_lag + 1):
        score = 0.0
        count = 0
        for index in range(0, len(centered) - lag, sample_step):
            score += centered[index] * centered[index + lag]
            count += 1
        score /= max(1, count)
        score /= max(0.000001, energy / len(centered))
        if score > best_score:
            best_lag = lag
            best_score = score

    if best_lag <= 0 or best_score < 0.12:
        return None

    frequency = sample_rate / best_lag
    midi_note = round(69 + 12 * math.log2(frequency / 440.0))
    if not 36 <= midi_note <= 60:
        return None
    return midi_note, round(min(0.95, max(0.05, best_score)), 3)


def _remove_dc(window: list[float]) -> list[float]:
    mean = sum(window) / len(window)
    return [(sample - mean) * _hann(index, len(window)) for index, sample in enumerate(window)]


def _hann(index: int, length: int) -> float:
    if length <= 1:
        return 1.0
    return 0.5 - 0.5 * math.cos((2.0 * math.pi * index) / (length - 1))


def _merge_events(events: list[NoteEvent], max_gap: float) -> list[NoteEvent]:
    if not events:
        return []

    merged: list[NoteEvent] = []
    current = events[0]
    for event in events[1:]:
        current_end = current.start + current.duration
        if event.midi_note == current.midi_note and event.start <= current_end + max_gap:
            end = max(current_end, event.start + event.duration)
            confidence = max(current.confidence, event.confidence)
            velocity = max(current.velocity, event.velocity)
            current = NoteEvent(current.start, round(end - current.start, 3), current.midi_note, velocity, confidence)
        else:
            merged.append(current)
            current = event
    merged.append(current)
    return merged


def _overall_confidence(events: list[NoteEvent]) -> float:
    if not events:
        return 0.0
    weighted = sum(event.confidence * event.duration for event in events)
    duration = sum(event.duration for event in events)
    return round(weighted / max(0.001, duration), 3)
