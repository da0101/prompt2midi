#!/usr/bin/env python3
"""ACE-output stem role detection and MIDI mapping plan artifacts."""

from __future__ import annotations

import argparse
import json
import math
import os
import struct
import wave
from pathlib import Path

from analysis.midi.stem_separation import separate_for_transcription

ROLE_CONFIG = {
    "drums": {
        "family": "percussion",
        "midi_target": "source-drum-groove.mid",
        "transcription": "drum_onset_detection",
        "limitations": [
            "Drum mapping should use onset bands from the separated drum stem.",
            "Kick, snare, hats, and percussion labels are estimates and need DAW review.",
        ],
    },
    "bass": {
        "family": "pitched_low",
        "midi_target": "source-bass-transcription.mid",
        "transcription": "stem_basic_pitch_low_range",
        "limitations": [
            "Bass MIDI should be transcribed from the generated-audio bass stem, not the reference.",
            "Kick bleed, guitar lows, or synth subs can still create wrong notes.",
        ],
    },
    "vocals": {
        "family": "vocal_audio",
        "midi_target": None,
        "transcription": "no_core_midi_mapping",
        "limitations": [
            "Vocal stems are detected for arrangement context; lyric and melody transcription is not reliable enough for core MIDI export yet.",
        ],
    },
    "guitar": {
        "family": "pitched_harmonic",
        "midi_target": "source-guitar-transcription.mid",
        "transcription": "stem_basic_pitch_mid_range",
        "limitations": [
            "Guitar MIDI needs stem-specific transcription and cleanup; bends, slides, and chords may be simplified.",
        ],
    },
    "piano": {
        "family": "pitched_harmonic",
        "midi_target": "source-piano-transcription.mid",
        "transcription": "stem_basic_pitch_polyphonic",
        "limitations": [
            "Piano/key MIDI should be reviewed for voicing, sustain, and octave errors.",
        ],
    },
    "other": {
        "family": "pitched_harmonic",
        "midi_target": "source-other-harmonic-transcription.mid",
        "transcription": "role_classify_then_stem_basic_pitch",
        "limitations": [
            "The Demucs other stem can contain pads, keys, guitars, effects, and residual bleed.",
            "Do not split this into fake instrument MIDI files until the role classifier has enough confidence.",
        ],
    },
}


def build_ace_stem_mapping(audio_path: str, output_dir: str, bpm: float | None = None, stem_result: dict | None = None) -> dict:
    """Analyze generated ACE audio as the legal source for stem/MIDI planning."""
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"ACE generated audio not found: {audio_path}")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stems = stem_result or separate_for_transcription(
        audio_path,
        str(output),
        source_stage="ace_generated_output",
    )
    mapping = detect_stem_roles(stems, source_audio=audio_path, source_stage="ace_generated_output")
    mapping["bpm"] = bpm
    mapping["midi_plan"] = _build_midi_plan(mapping, output)
    mapping_path = output / "ace-stem-midi-map.json"
    with open(mapping_path, "w", encoding="utf-8") as handle:
        json.dump(mapping, handle, indent=2, sort_keys=True)
    mapping["path"] = os.path.abspath(mapping_path)
    return mapping


def detect_stem_roles(stem_result: dict | None, source_audio: str | None = None, source_stage: str | None = None) -> dict:
    stem_result = stem_result or {}
    stem_paths = stem_result.get("stems") or {}
    source = source_audio or stem_result.get("source_audio")
    stage = source_stage or stem_result.get("source_stage") or "unknown"
    roles: dict[str, dict] = {}
    omitted: list[dict] = []
    warnings = list(stem_result.get("warnings") or [])

    for stem_name, path in sorted(stem_paths.items()):
        config = ROLE_CONFIG.get(stem_name, _generic_config(stem_name))
        try:
            stats = _wav_stats(path)
        except (OSError, wave.Error, ValueError, struct.error) as exc:
            omitted.append({"stem": stem_name, "reason": f"unreadable stem: {exc}", "path": os.path.abspath(path)})
            continue

        active = _is_active(stem_name, stats)
        role_key = _role_key(stem_name, stats)
        if not active:
            omitted.append(
                {
                    "stem": stem_name,
                    "role": role_key,
                    "reason": "inactive_or_too_quiet",
                    "path": os.path.abspath(path),
                    "stats": _round_stats(stats),
                }
            )
            continue

        confidence = _confidence(stem_name, stats)
        roles[role_key] = {
            "present": True,
            "confidence": confidence,
            "source_stem": stem_name,
            "source_audio": os.path.abspath(path),
            "source_mix": os.path.abspath(source) if source else None,
            "source_stage": stage,
            "family": config["family"],
            "role_hint": _role_hint(stem_name, stats),
            "method": "demucs_role_activity_v1",
            "stats": _round_stats(stats),
            "limitations": config["limitations"],
            "midi_target": config["midi_target"],
            "transcription_strategy": config["transcription"],
        }

    detected = sorted(roles)
    if not detected:
        warnings.append("No active stem roles were detected; MIDI mapping should be skipped for this generated audio.")

    return {
        "available": bool(detected),
        "method": f"{stem_result.get('method', 'stem_separation')}+role_activity_v1",
        "source_audio": os.path.abspath(source) if source else None,
        "source_stage": stage,
        "detected_roles": detected,
        "roles": roles,
        "omitted_roles": omitted,
        "warnings": warnings,
    }


def _build_midi_plan(mapping: dict, output_dir: Path) -> list[dict]:
    plan = []
    midi_root = output_dir / "midi"
    for role, details in sorted((mapping.get("roles") or {}).items()):
        target = details.get("midi_target")
        plan.append(
            {
                "role": role,
                "status": "planned" if target else "context_only",
                "target_path": os.path.abspath(midi_root / target) if target else None,
                "source_stem": details.get("source_stem"),
                "source_audio": details.get("source_audio"),
                "source_stage": details.get("source_stage"),
                "confidence": details.get("confidence", 0.0),
                "transcription_strategy": details.get("transcription_strategy"),
                "limitations": details.get("limitations") or [],
            }
        )
    return plan


def _wav_stats(path: str) -> dict:
    with wave.open(path, "rb") as handle:
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        sample_rate = handle.getframerate()
        frame_count = handle.getnframes()
        frames = handle.readframes(frame_count)

    if sample_width not in (1, 2, 3, 4):
        raise ValueError(f"unsupported sample width {sample_width}")
    if frame_count <= 0:
        raise ValueError("empty stem")

    samples = []
    stride = sample_width * channels
    for offset in range(0, len(frames), stride):
        channel_values = []
        for channel in range(channels):
            start = offset + channel * sample_width
            raw = frames[start : start + sample_width]
            if len(raw) != sample_width:
                continue
            channel_values.append(_decode_pcm(raw, sample_width))
        if channel_values:
            samples.append(sum(channel_values) / len(channel_values))

    if not samples:
        raise ValueError("no readable PCM samples")

    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    peak = max(abs(sample) for sample in samples)
    window_size = max(1, int(sample_rate * 0.1))
    windows = []
    zero_crossings = 0
    previous = samples[0]
    for sample in samples[1:]:
        if (previous < 0 <= sample) or (previous > 0 >= sample):
            zero_crossings += 1
        previous = sample
    for start in range(0, len(samples), window_size):
        window = samples[start : start + window_size]
        if window:
            windows.append(math.sqrt(sum(sample * sample for sample in window) / len(window)))

    threshold = max(0.0035, rms * 0.5)
    active_ratio = 0.0 if not windows else sum(1 for value in windows if value >= threshold) / len(windows)
    transient_ratio = _transient_ratio(windows)
    return {
        "sample_rate": sample_rate,
        "duration_seconds": len(samples) / sample_rate,
        "rms": rms,
        "peak": peak,
        "active_ratio": active_ratio,
        "zero_crossing_rate": zero_crossings / max(1, len(samples) - 1),
        "transient_ratio": transient_ratio,
    }


def _decode_pcm(raw: bytes, sample_width: int) -> float:
    if sample_width == 1:
        return (raw[0] - 128) / 128.0
    if sample_width == 2:
        return struct.unpack("<h", raw)[0] / 32768.0
    if sample_width == 3:
        padded = raw + (b"\xff" if raw[-1] & 0x80 else b"\x00")
        return struct.unpack("<i", padded)[0] / 8388608.0
    return struct.unpack("<i", raw)[0] / 2147483648.0


def _transient_ratio(windows: list[float]) -> float:
    if len(windows) < 3:
        return 0.0
    deltas = [max(0.0, windows[index] - windows[index - 1]) for index in range(1, len(windows))]
    threshold = max(0.004, (sum(windows) / len(windows)) * 0.45)
    return sum(1 for value in deltas if value >= threshold) / len(deltas)


def _is_active(stem_name: str, stats: dict) -> bool:
    if stem_name == "drums":
        return stats["peak"] >= 0.035 and stats["active_ratio"] >= 0.02
    if stem_name == "vocals":
        return stats["rms"] >= 0.008 and stats["active_ratio"] >= 0.05
    return stats["rms"] >= 0.005 and stats["active_ratio"] >= 0.04


def _role_key(stem_name: str, stats: dict) -> str:
    if stem_name != "other":
        return stem_name
    if stats["transient_ratio"] >= 0.35:
        return "other_plucked_harmonic"
    return "other_sustained_harmonic"


def _role_hint(stem_name: str, stats: dict) -> str:
    if stem_name == "drums":
        return "drums_or_percussion"
    if stem_name == "bass":
        return "bass_or_low_synth"
    if stem_name == "vocals":
        return "vocal_or_vocal_like_lead"
    if stem_name == "guitar":
        return "guitar_or_plucked_string"
    if stem_name == "piano":
        return "piano_or_keys"
    if stats["transient_ratio"] >= 0.35:
        return "plucked_harmonic_other"
    return "pad_keys_or_sustained_harmonic_other"


def _confidence(stem_name: str, stats: dict) -> float:
    base = 0.42 if stem_name == "other" else 0.52
    level = min(0.25, stats["rms"] * 3.5)
    activity = min(0.22, stats["active_ratio"] * 0.24)
    peak = min(0.12, stats["peak"] * 0.35)
    return round(min(0.92, base + level + activity + peak), 3)


def _round_stats(stats: dict) -> dict:
    rounded = {}
    for key, value in stats.items():
        rounded[key] = round(value, 5) if isinstance(value, float) else value
    return rounded


def _generic_config(stem_name: str) -> dict:
    return {
        "family": "unknown_audio",
        "midi_target": f"source-{stem_name}-transcription.mid",
        "transcription": "manual_review_required",
        "limitations": ["Unknown stem role; do not export MIDI until the instrument role is confirmed."],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an ACE-generated audio stem/MIDI mapping plan.")
    parser.add_argument("--audio", required=True, help="Generated ACE audio file, not the original reference.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--bpm", type=float)
    args = parser.parse_args()
    payload = build_ace_stem_mapping(args.audio, args.output_dir, bpm=args.bpm)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
