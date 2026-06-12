#!/usr/bin/env python3
"""Deterministic house/techno drum control split.

This is not source separation. It creates practical arrangement-control lanes
from a 4/4 drum stem by combining beat-grid windows and broad filters:
- kick: low drum body on every quarter note
- snare_clap: mid/high transients on beats 2 and 4
- tops: high-passed residual with kick/clap transient regions ducked

Use this when AI drum sub-separation produces musically bad stems.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal


def main() -> int:
    parser = argparse.ArgumentParser(description="Create grid-based drum control stems for 4/4 house/techno.")
    parser.add_argument("--input", required=True, help="Input drum stem.")
    parser.add_argument("--output-dir", required=True, help="Output directory.")
    parser.add_argument("--bpm", type=float, required=True, help="Track BPM.")
    parser.add_argument("--phase-ms", type=float, default=0.0, help="Beat-grid phase offset in milliseconds.")
    args = parser.parse_args()

    payload = split_grid_drums(args.input, args.output_dir, args.bpm, phase_ms=args.phase_ms)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def split_grid_drums(input_path: str, output_dir: str, bpm: float, phase_ms: float = 0.0) -> dict:
    source = Path(input_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    audio, sample_rate = sf.read(str(source), always_2d=True, dtype="float32")
    audio = audio[:, :2]
    if audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)

    beat_samples = int(round(sample_rate * 60.0 / bpm))
    phase_samples = int(round(sample_rate * phase_ms / 1000.0))
    kick_mask = transient_mask(len(audio), beat_samples, phase_samples, width_samples=int(0.20 * sample_rate), every=1)
    clap_mask = transient_mask(
        len(audio),
        beat_samples,
        phase_samples + beat_samples,
        width_samples=int(0.18 * sample_rate),
        every=2,
    )
    short_all_beat_mask = transient_mask(len(audio), beat_samples, phase_samples, width_samples=int(0.065 * sample_rate), every=1)
    short_clap_mask = transient_mask(
        len(audio),
        beat_samples,
        phase_samples + beat_samples,
        width_samples=int(0.09 * sample_rate),
        every=2,
    )

    low = lowpass(audio, sample_rate, 210.0)
    mid_high = highpass(audio, sample_rate, 450.0)
    top_band = highpass(audio, sample_rate, 900.0)

    kick = low * kick_mask[:, None]
    snare_clap = mid_high * clap_mask[:, None]
    tops_duck = np.maximum(short_all_beat_mask * 0.82, short_clap_mask * 0.7)
    tops = top_band * (1.0 - tops_duck[:, None])
    residual = audio - np.clip(kick + snare_clap + tops, -1.0, 1.0)

    outputs = {
        "kick_grid": kick,
        "snare_clap_grid": snare_clap,
        "tops_grid": tops,
        "drums_residual_grid": residual,
    }
    paths = {}
    for name, samples in outputs.items():
        path = out / f"{name}.wav"
        sf.write(str(path), np.clip(samples, -1.0, 1.0), sample_rate, subtype="PCM_16")
        paths[name] = str(path.resolve())

    return {
        "available": True,
        "method": "grid_drum_control_split",
        "source_audio": str(source.resolve()),
        "sample_rate": sample_rate,
        "bpm": bpm,
        "phase_ms": phase_ms,
        "stems": paths,
        "warning": "Grid split is for arrangement control, not clean source separation.",
    }


def transient_mask(length: int, beat_samples: int, phase_samples: int, width_samples: int, every: int) -> np.ndarray:
    mask = np.zeros(length, dtype=np.float32)
    cursor = phase_samples
    step = beat_samples * every
    fade = max(1, min(width_samples // 3, int(0.025 * beat_samples)))
    while cursor < length:
        start = max(0, cursor)
        end = min(length, cursor + width_samples)
        if end > start:
            segment = np.ones(end - start, dtype=np.float32)
            if len(segment) > fade * 2:
                segment[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
            mask[start:end] = np.maximum(mask[start:end], segment)
        cursor += step
    return mask


def lowpass(samples: np.ndarray, sample_rate: int, cutoff_hz: float) -> np.ndarray:
    sos = signal.butter(4, cutoff_hz / (sample_rate / 2.0), btype="lowpass", output="sos")
    return signal.sosfiltfilt(sos, samples, axis=0).astype(np.float32)


def highpass(samples: np.ndarray, sample_rate: int, cutoff_hz: float) -> np.ndarray:
    sos = signal.butter(4, cutoff_hz / (sample_rate / 2.0), btype="highpass", output="sos")
    return signal.sosfiltfilt(sos, samples, axis=0).astype(np.float32)


if __name__ == "__main__":
    raise SystemExit(main())
