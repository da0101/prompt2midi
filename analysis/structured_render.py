#!/usr/bin/env python3
"""Pipeline-owned structured sample renderer.

This is a fast local guide-audio lane for reference-inspired samples. It does
not require Ableton, MIDI instruments, ACE-Step, or SoundFonts. The renderer
uses reference analysis as control data, composes new parts, and renders a
mixed stereo WAV with layered synthesized drums, bass, stabs, hook proxies, FX,
sidechain, saturation, and limiting.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, find_peaks, sawtooth, sosfilt

from audio_quality import score_audio_candidate
SR = 44100
NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
KEY_NOTE = {name: index for index, name in enumerate(NOTE_NAMES)}
KEY_NOTE.update({"Db": 1, "Eb": 3, "Gb": 6, "Ab": 8, "Bb": 10})

SIMILARITY = {
    "low": {"reuse": 0.12, "density": 0.86, "palette": "fresh"},
    "medium-low": {"reuse": 0.28, "density": 0.94, "palette": "fresh"},
    "medium": {"reuse": 0.45, "density": 1.0, "palette": "balanced"},
    "medium-high": {"reuse": 0.62, "density": 1.05, "palette": "balanced"},
    "high": {"reuse": 0.78, "density": 1.08, "palette": "reference"},
    "near-identical": {"reuse": 0.9, "density": 1.1, "palette": "reference"},
}


@dataclass(frozen=True)
class ReferenceAudio:
    path: str
    samples: np.ndarray
    sample_rate: int
    duration_seconds: float


def render_reference_sample(
    reference_path: str,
    output_dir: str,
    similarity_level: str = "medium",
    duration_seconds: float = 30.0,
    candidates: int = 4,
    prompt: str = "",
    seed: int | None = None,
) -> dict:
    similarity_key = _normalize_similarity(similarity_level)
    out = Path(output_dir)
    exports = out / "exports"
    exports.mkdir(parents=True, exist_ok=True)

    _progress("loading reference")
    reference = _load_reference(reference_path, out)
    _progress("analyzing reference")
    analysis = _analyze_reference(reference, prompt)
    profile = SIMILARITY[similarity_key]
    base_seed = seed if seed is not None else random.SystemRandom().randint(1, 2**31 - 1)

    candidate_payloads = []
    for index in range(max(1, int(candidates))):
        _progress(f"rendering candidate {index + 1}/{max(1, int(candidates))}")
        rng = random.Random(base_seed + index * 9173)
        composition = _compose(analysis, profile, duration_seconds, rng, index)
        audio = _render_mix(composition, analysis, profile, duration_seconds, rng)
        path = exports / f"candidate-{index + 1}.wav"
        _write_wav(path, audio)
        _progress(f"scoring candidate {index + 1}/{max(1, int(candidates))}")
        quality = score_audio_candidate(str(path), target_duration=duration_seconds)
        candidate_payloads.append(
            {
                "index": index + 1,
                "path": str(path),
                "quality": quality,
                "composition": _composition_summary(composition),
            }
        )

    metadata = {
        "ok": True,
        "engine": "structured_render_v1",
        "reference": os.path.abspath(reference_path),
        "output_dir": str(out),
        "similarity_level": similarity_key,
        "duration_seconds": duration_seconds,
        "seed": base_seed,
        "analysis": analysis,
        "suno_prompt": _build_suno_prompt(analysis, similarity_key, prompt),
        "candidates": candidate_payloads,
        "warnings": [
            "This is local rendered guide audio, not a neural master recording.",
            "Vocals are represented as safe original chop/proxy textures; the renderer does not clone lyrics, singer identity, or lead vocal audio.",
        ],
    }
    (out / "structured-render.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (out / "suno-prompt.txt").write_text(metadata["suno_prompt"], encoding="utf-8")
    return metadata


def render_control_scaffold(
    reference_path: str,
    output_dir: str,
    prompt: str = "",
    analysis: dict | None = None,
    reference_groove: dict | None = None,
    duration_seconds: float = 30.0,
    seed: int | None = None,
) -> dict:
    """Render a deterministic in-key bass/drum scaffold for ACE conditioning."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed if seed is not None else 1701)
    scaffold_analysis = _scaffold_analysis(reference_path, prompt, analysis or {}, reference_groove or {})
    composition = _compose_control_scaffold(scaffold_analysis, duration_seconds, rng)
    audio = _render_mix(composition, scaffold_analysis, SIMILARITY["near-identical"], duration_seconds, rng)
    path = out / "ace-control-scaffold.wav"
    _write_wav(path, audio)
    payload = {
        "path": str(path.resolve()),
        "duration_seconds": duration_seconds,
        "analysis": scaffold_analysis,
        "composition": _composition_summary(composition),
        "purpose": "ACE cover/reference conditioning with controlled in-key bass rhythm and tone.",
        "warnings": [
            "This scaffold is generated by the pipeline and is not the original reference recording.",
            "Bass notes are generated inside the detected/corrected key; ACE may still reinterpret the scaffold.",
        ],
    }
    (out / "ace-control-scaffold.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _progress(message: str) -> None:
    print(f"progress: structured-render: {message}", file=sys.stderr, flush=True)


def _load_reference(reference_path: str, output_dir: Path) -> ReferenceAudio:
    wav_path = _ensure_wav(reference_path, output_dir)
    sample_rate, data = wavfile.read(str(wav_path))
    samples = _pcm_to_float(data)
    if samples.ndim == 2:
        samples = np.mean(samples, axis=1)
    if sample_rate != SR:
        samples = _resample_linear(samples.astype(np.float32), sample_rate, SR)
        sample_rate = SR
    return ReferenceAudio(
        path=str(wav_path),
        samples=samples.astype(np.float32),
        sample_rate=sample_rate,
        duration_seconds=len(samples) / float(sample_rate),
    )


def _pcm_to_float(data: np.ndarray) -> np.ndarray:
    if np.issubdtype(data.dtype, np.floating):
        return np.asarray(np.clip(data, -1.0, 1.0), dtype=np.float32)
    if data.dtype == np.uint8:
        return ((data.astype(np.float32) - 128.0) / 128.0).astype(np.float32)
    info = np.iinfo(data.dtype)
    scale = max(abs(info.min), abs(info.max))
    return (data.astype(np.float32) / float(scale)).astype(np.float32)


def _ensure_wav(reference_path: str, output_dir: Path) -> Path:
    path = Path(reference_path)
    if not path.exists():
        raise FileNotFoundError(f"Reference audio not found: {reference_path}")
    if path.suffix.lower() in {".wav", ".wave"} and _is_pcm_wav(path):
        return path

    ffmpeg = os.environ.get("PROMPT2MIDI_FFMPEG") or shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to decode non-PCM or non-WAV references for structured rendering.")
    decoded = output_dir / "reference-input.wav"
    output_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), str(decoded)],
        check=True,
    )
    return decoded


def _is_pcm_wav(path: Path) -> bool:
    try:
        with wave.open(str(path), "rb") as wav:
            return wav.getnframes() > 0 and wav.getframerate() > 0
    except wave.Error:
        return False


def _analyze_reference(reference: ReferenceAudio, prompt: str) -> dict:
    bpm = _estimate_bpm_quick(reference.samples, reference.sample_rate)
    key = _estimate_key_chroma(reference.samples, reference.sample_rate, "C minor")
    bpm = _normalize_bpm(bpm)
    groove = _analyze_groove(reference.samples, reference.sample_rate, bpm)
    genre = _infer_style(bpm, groove, prompt, reference.path)
    vocals = _detect_vocal_role(reference.samples, reference.sample_rate, prompt, genre)
    energy = _energy_profile(reference.samples)
    return {
        "bpm": round(bpm, 2),
        "key": key,
        "genre": genre,
        "mood": _infer_mood(energy, genre, prompt),
        "energy": energy,
        "groove": groove,
        "vocals": vocals,
        "duration_seconds": round(reference.duration_seconds, 3),
        "source_path": os.path.abspath(reference.path),
    }


def _scaffold_analysis(reference_path: str, prompt: str, analysis: dict, reference_groove: dict) -> dict:
    bpm = _coerce_float(analysis.get("bpm"), 124.0)
    key = (
        _nested(analysis, "reference_transform", "harmonic", "key")
        or analysis.get("key")
        or "C minor"
    )
    genre = analysis.get("genre") if isinstance(analysis.get("genre"), dict) else {}
    if not genre:
        genre = _infer_style(bpm, _fallback_groove(), prompt, reference_path)
    energy = analysis.get("energy") if isinstance(analysis.get("energy"), dict) else {}
    if not energy:
        energy = {"lane": "medium"}

    groove = _scaffold_groove(prompt, reference_groove, analysis)
    mood = analysis.get("mood") or _nested(analysis, "reference_transform", "reference_character", "mood")
    if not mood:
        mood = _infer_mood(energy, genre, prompt)

    return {
        "bpm": round(_normalize_bpm(bpm), 2),
        "key": str(key),
        "genre": genre,
        "mood": str(mood),
        "energy": energy,
        "groove": groove,
        "vocals": {
            "present": False,
            "role": "none",
            "render_mode": "none",
            "guidance": "control scaffold uses drums and bass only so ACE receives a clean groove target",
        },
        "duration_seconds": _coerce_float(analysis.get("duration_seconds"), 0.0),
        "source_path": os.path.abspath(reference_path),
        "control_scaffold": True,
    }


def _scaffold_groove(prompt: str, reference_groove: dict, analysis: dict) -> dict:
    source_groove = analysis.get("groove") if isinstance(analysis.get("groove"), dict) else {}
    wants_running = _wants_running_bass(prompt)
    kick = _pattern32_to_16(reference_groove.get("kick_pattern_16th")) or source_groove.get("kick_pattern_16th")
    bass = _pattern32_to_16(reference_groove.get("bass_accent_pattern_16th")) or source_groove.get("bass_accent_pattern_16th")
    hats = _pattern32_to_16(reference_groove.get("hat_pattern_16th")) or source_groove.get("hat_pattern_16th")
    if wants_running:
        bass = [0, 2, 4, 6, 8, 10, 12, 14]
    kick = _sanitize_pattern(kick, [0, 4, 8, 12], max_count=8)
    bass = _sanitize_pattern(bass, [0, 2, 4, 6, 8, 10, 12, 14], max_count=10)
    hats = _sanitize_pattern(hats, list(range(0, 16, 2)), max_count=14)
    return {
        "kick_pattern_16th": kick,
        "bass_accent_pattern_16th": bass,
        "hat_pattern_16th": hats,
        "swing": _coerce_float(reference_groove.get("swing"), _coerce_float(source_groove.get("swing"), 0.0)),
        "low_end_weight": reference_groove.get("low_end_weight") or source_groove.get("low_end_weight") or "heavy",
        "drum_feel": reference_groove.get("drum_feel") or source_groove.get("drum_feel") or "four-on-floor",
        "bass_feel": "steady running" if wants_running else reference_groove.get("bass_feel") or source_groove.get("bass_feel") or "rolling",
        "hat_feel": reference_groove.get("hat_feel") or source_groove.get("hat_feel") or "eighth-note drive",
        "method": "pipeline_control_scaffold",
    }


def _pattern32_to_16(pattern: object) -> list[int]:
    if not isinstance(pattern, list):
        return []
    return sorted({int(step) % 16 for step in pattern if isinstance(step, (int, float))})


def _sanitize_pattern(pattern: object, fallback: list[int], max_count: int) -> list[int]:
    source = sorted({int(step) % 16 for step in pattern}) if isinstance(pattern, list) else []
    if not source:
        source = list(fallback)
    if len(source) > max_count:
        source = list(fallback)
    return source


def _wants_running_bass(prompt: str) -> bool:
    text = (prompt or "").lower()
    return bool(
        re.search(
            r"\b(running bass|straight bass|steady bass|same bass line rhythm|same bassline rhythm|"
            r"every beat and off beat|on beat and off beat|da da da)\b",
            text,
        )
    )


def _coerce_float(value: object, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if math.isfinite(number) else fallback


def _nested(source: dict, *keys: str) -> object:
    current: object = source
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _estimate_bpm_quick(samples: np.ndarray, sr: int) -> float:
    y = samples[: min(samples.size, sr * 75)]
    if y.size < sr * 4:
        return 124.0
    hop = max(1, int(sr * 0.05))
    usable = (y.size // hop) * hop
    frames = y[:usable].reshape(-1, hop)
    energy = np.sqrt(np.mean(np.square(frames), axis=1))
    flux = np.maximum(0.0, np.diff(energy))
    if flux.size < 20 or float(np.max(flux)) <= 1e-7:
        return 124.0
    flux = flux - float(np.mean(flux))
    best_bpm = 124.0
    best_score = -1e9
    step_seconds = hop / float(sr)
    for bpm in range(80, 161):
        lag = max(1, int(round((60.0 / bpm) / step_seconds)))
        if lag >= flux.size:
            continue
        score = float(np.dot(flux[lag:], flux[:-lag]))
        if score > best_score:
            best_score = score
            best_bpm = float(bpm)
    return best_bpm


def _normalize_bpm(bpm: float) -> float:
    while bpm < 92.0:
        bpm *= 2.0
    while bpm > 160.0:
        bpm /= 2.0
    return max(92.0, min(150.0, bpm))


def _estimate_key_chroma(samples: np.ndarray, sr: int, fallback: str) -> str:
    if samples.size < sr:
        return fallback
    y = samples[: min(samples.size, sr * 24)]
    y = y - float(np.mean(y))
    window = 4096
    hop = 2048
    chroma = np.zeros(12, dtype=np.float64)
    freqs = np.fft.rfftfreq(window, 1.0 / sr)
    valid = (freqs >= 55.0) & (freqs <= 3000.0)
    pcs = np.asarray([int(round(69 + 12 * math.log2(max(1e-6, freq) / 440.0))) % 12 for freq in freqs[valid]])
    for start in range(0, max(1, y.size - window), hop):
        frame = y[start : start + window]
        if frame.size < window:
            break
        mag = np.abs(np.fft.rfft(frame * np.hanning(window)))
        chroma += np.bincount(pcs, weights=mag[valid], minlength=12)
    if np.max(chroma) <= 0:
        return fallback
    chroma = chroma / np.max(chroma)
    major = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    best = (-999.0, fallback)
    for root in range(12):
        rotated = np.roll(chroma, -root)
        for profile, mode in ((major, "major"), (minor, "minor")):
            score = float(np.corrcoef(rotated, profile)[0, 1])
            if score > best[0]:
                best = (score, f"{NOTE_NAMES[root]} {mode}")
    return best[1]


def _analyze_groove(samples: np.ndarray, sr: int, bpm: float) -> dict:
    if samples.size < sr:
        return _fallback_groove()
    y = samples[: min(samples.size, sr * 96)]
    beat = 60.0 / bpm
    sixteenth = beat / 4.0
    kick = _pattern_from_band(y, sr, 35.0, 135.0, sixteenth, delta=0.7)
    bass = _pattern_from_band(y, sr, 45.0, 260.0, sixteenth, delta=0.55)
    hats = _pattern_from_band(y, sr, 2500.0, 10000.0, sixteenth, delta=0.5)
    if len(kick) > 8:
        kick = [0, 4, 8, 12]
    if len(bass) > 10:
        bass = [1, 3, 6, 9, 11, 14]
    if len(hats) > 14:
        hats = list(range(0, 16, 2))
    swing = _estimate_swing_from_pattern(hats)
    low_weight = _band_energy(y, sr, 35.0, 180.0) / max(1e-6, _band_energy(y, sr, 180.0, 6000.0))
    return {
        "kick_pattern_16th": kick or [0, 4, 8, 12],
        "bass_accent_pattern_16th": bass or [2, 6, 10, 14],
        "hat_pattern_16th": hats or list(range(0, 16, 2)),
        "swing": round(swing, 3),
        "low_end_weight": "heavy" if low_weight > 0.9 else "light" if low_weight < 0.38 else "medium",
        "drum_feel": "four-on-floor" if set(kick or []).issuperset({0, 4, 8, 12}) else "syncopated",
        "bass_feel": "rolling" if len(bass or []) >= 5 else "sparse" if len(bass or []) <= 2 else "syncopated",
        "hat_feel": "running 16ths" if len(hats or []) >= 10 else "offbeat/open" if len(hats or []) <= 5 else "eighth-note drive",
    }


def _fallback_groove() -> dict:
    return {
        "kick_pattern_16th": [0, 4, 8, 12],
        "bass_accent_pattern_16th": [2, 6, 10, 14],
        "hat_pattern_16th": list(range(0, 16, 2)),
        "swing": 0.0,
        "low_end_weight": "medium",
        "drum_feel": "four-on-floor",
        "bass_feel": "syncopated",
        "hat_feel": "eighth-note drive",
    }


def _pattern_from_band(samples: np.ndarray, sr: int, low: float, high: float, sixteenth: float, delta: float) -> list[int]:
    band = _bandpass(samples, sr, low, high)
    env = _smooth(np.abs(band), max(32, int(sr * 0.025)))
    if np.max(env) <= 0:
        return []
    env = env / np.max(env)
    peaks, _ = find_peaks(env, height=max(0.18, np.quantile(env, delta)), distance=max(1, int(sixteenth * sr * 0.6)))
    if peaks.size == 0:
        return []
    counts = [0.0] * 16
    for peak in peaks:
        step = int(round((peak / sr) / sixteenth)) % 16
        counts[step] += float(env[peak])
    if max(counts) <= 0:
        return []
    threshold = max(counts) * 0.28
    return [index for index, value in enumerate(counts) if value >= threshold]


def _estimate_swing_from_pattern(pattern: list[int]) -> float:
    odd = sum(1 for step in pattern if step % 2 == 1)
    even = sum(1 for step in pattern if step % 2 == 0)
    if even + odd == 0:
        return 0.0
    return max(0.0, min(0.18, odd / (even + odd) * 0.18))


def _infer_style(bpm: float, groove: dict, prompt: str, path: str) -> dict:
    text = f"{prompt} {path}".lower()
    if any(term in text for term in ("tech house", "minimal", "manda moor", "deep tech")):
        primary = "minimal deep tech / tech house"
        tags = ["minimal deep tech", "tech house", "club", "groove-led"]
    elif any(term in text for term in ("electro", "tiga", "new wave", "synth pop")):
        primary = "electro house / indie dance"
        tags = ["electro house", "indie dance", "synth hook", "club"]
    elif any(term in text for term in ("funk", "michael jackson", "smooth criminal", "disco")):
        primary = "electro funk / dance pop"
        tags = ["electro funk", "dance pop", "syncopated bass", "vocal-hook proxy"]
    elif 118 <= bpm <= 132 and groove.get("drum_feel") == "four-on-floor":
        primary = "house / tech house"
        tags = ["house", "tech house", "club", groove.get("bass_feel", "syncopated")]
    else:
        primary = "electronic club"
        tags = ["electronic", "club", groove.get("drum_feel", "dance"), groove.get("hat_feel", "hats")]
    return {"primary": primary, "tags": tags, "confidence": 0.55, "method": "local_feature_heuristic"}


def _detect_vocal_role(samples: np.ndarray, sr: int, prompt: str, genre: dict) -> dict:
    text = f"{prompt} {' '.join(genre.get('tags') or [])}".lower()
    if any(term in text for term in ("no vocal", "instrumental only", "without vocal")):
        present = False
    elif any(term in text for term in ("vocal", "lyrics", "singer", "michael jackson", "tiga")):
        present = True
    else:
        mid = _band_energy(samples[: min(samples.size, sr * 45)], sr, 300.0, 3200.0)
        full = _band_energy(samples[: min(samples.size, sr * 45)], sr, 80.0, 9000.0)
        present = (mid / max(1e-6, full)) > 0.45
    role = "rhythmic vocal hook" if present else "none"
    return {
        "present": present,
        "role": role,
        "render_mode": "instrumental_hook_proxy" if present else "none",
        "guidance": "use short original vocal-like chop/proxy texture, not copied lyrics or singer identity" if present else "instrumental focus",
    }


def _energy_profile(samples: np.ndarray) -> dict:
    rms = float(np.sqrt(np.mean(np.square(samples)))) if samples.size else 0.0
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    return {
        "rms": round(rms, 5),
        "peak": round(peak, 5),
        "lane": "high" if rms > 0.14 else "low" if rms < 0.06 else "medium",
    }


def _infer_mood(energy: dict, genre: dict, prompt: str) -> str:
    text = prompt.lower()
    if any(term in text for term in ("dark", "mean", "underground", "banger")):
        return "dark, confident, underground"
    if "funk" in " ".join(genre.get("tags") or []):
        return "tight, funky, animated"
    if energy.get("lane") == "high":
        return "driving and energetic"
    return "controlled and club-focused"


def _compose(analysis: dict, profile: dict, duration: float, rng: random.Random, candidate_index: int) -> dict:
    bpm = float(analysis["bpm"])
    beat = 60.0 / bpm
    bars = max(4, int(math.ceil(duration / (beat * 4.0))))
    root_pc, mode = _parse_key(analysis["key"])
    scale = _scale(root_pc, mode)
    groove = analysis["groove"]
    reuse = float(profile["reuse"])

    kick_steps = _vary_steps(groove["kick_pattern_16th"], [0, 4, 8, 12], reuse, rng, role="kick")
    bass_steps = _vary_steps(groove["bass_accent_pattern_16th"], [1, 3, 6, 9, 11, 14], reuse, rng, role="bass")
    hat_steps = _vary_steps(groove["hat_pattern_16th"], list(range(0, 16, 2)), reuse, rng, role="hat")

    chord_roots = _chord_roots(root_pc, mode, profile["palette"], rng)
    bass_offsets = _bass_offsets(mode, reuse, rng)
    events = {"kick": [], "snare": [], "hat": [], "perc": [], "bass": [], "chords": [], "hook": [], "vocal_chop": [], "fx": []}
    bar_seconds = beat * 4.0
    swing = float(groove.get("swing") or 0.0)

    for bar in range(bars):
        section = _section_weight(bar, bars)
        chord_pc = chord_roots[bar % len(chord_roots)]
        for step in kick_steps:
            events["kick"].append((bar, step, 0.9 + 0.08 * section))
        for step in (4, 12):
            if section > 0.3:
                events["snare"].append((bar, step, 0.66 + rng.random() * 0.08))
        for step in hat_steps:
            if rng.random() < (0.82 + 0.12 * section):
                vel = 0.25 + 0.18 * (step % 4 == 2) + rng.random() * 0.08
                events["hat"].append((bar, step, vel))
        if bar % 2 == 1 and section > 0.45:
            events["perc"].append((bar, rng.choice([3, 7, 10, 15]), 0.35 + rng.random() * 0.2))
        if bar % 4 == 3:
            for step in rng.sample([12, 13, 14, 15], rng.choice([1, 2, 3])):
                events["perc"].append((bar, step, 0.25 + rng.random() * 0.18))

        for index, step in enumerate(bass_steps):
            pc = (chord_pc + bass_offsets[(index + bar + candidate_index) % len(bass_offsets)]) % 12
            note = _pc_to_midi(pc, octave=2)
            dur_steps = rng.choice([1.6, 2.0, 2.6, 3.0])
            events["bass"].append((bar, step, note, dur_steps, 0.72 + rng.random() * 0.18))

        chord_steps = [0, 8] if reuse >= 0.45 else rng.choice([[2, 10], [0, 7], [3, 11]])
        for step in chord_steps:
            if section > 0.35 and rng.random() > 0.15:
                events["chords"].append((bar, step, _chord_notes(chord_pc, mode), 2.2, 0.45 + rng.random() * 0.16))

        hook_density = 0.55 if analysis["vocals"].get("present") else 0.35
        if bar % 2 == candidate_index % 2 and rng.random() < hook_density * section:
            for step, degree in zip(rng.sample([1, 3, 6, 9, 11, 14], rng.choice([2, 3])), rng.sample(range(len(scale)), 3)):
                note = _pc_to_midi(scale[degree % len(scale)], octave=4)
                events["hook"].append((bar, step, note, rng.choice([0.7, 1.0, 1.4]), 0.36 + rng.random() * 0.18))
        if analysis["vocals"].get("present") and section > 0.45 and bar % 2 == 0:
            for step in rng.sample([2, 5, 7, 10, 13], rng.choice([1, 2])):
                events["vocal_chop"].append((bar, step, _pc_to_midi(rng.choice(scale), octave=4), 0.45, 0.28 + rng.random() * 0.16))
        if bar % 8 == 7:
            events["fx"].append((bar, 14, 0.28 + rng.random() * 0.2))

    return {
        "bpm": bpm,
        "bars": bars,
        "beat": beat,
        "swing": swing,
        "events": events,
        "key": analysis["key"],
        "mode": mode,
        "style": analysis["genre"]["primary"],
    }


def _compose_control_scaffold(analysis: dict, duration: float, rng: random.Random) -> dict:
    bpm = float(analysis["bpm"])
    beat = 60.0 / bpm
    bars = max(2, int(math.ceil(duration / (beat * 4.0))))
    root_pc, mode = _parse_key(analysis["key"])
    scale = _scale(root_pc, mode)
    groove = analysis["groove"]
    kick_steps = _sanitize_pattern(groove.get("kick_pattern_16th"), [0, 4, 8, 12], max_count=8)
    bass_steps = _sanitize_pattern(groove.get("bass_accent_pattern_16th"), [0, 2, 4, 6, 8, 10, 12, 14], max_count=10)
    hat_steps = _sanitize_pattern(groove.get("hat_pattern_16th"), list(range(0, 16, 2)), max_count=14)
    events = {"kick": [], "snare": [], "hat": [], "perc": [], "bass": [], "chords": [], "hook": [], "vocal_chop": [], "fx": []}
    swing = min(0.12, max(0.0, float(groove.get("swing") or 0.0)))
    degree_cycle = _control_bass_degrees(mode)

    for bar in range(bars):
        section = _section_weight(bar, bars)
        for step in kick_steps:
            events["kick"].append((bar, step, 0.92 + 0.05 * section))
        if section > 0.45:
            for step in (4, 12):
                events["snare"].append((bar, step, 0.48 + 0.06 * section))
        for step in hat_steps:
            vel = 0.22 + (0.14 if step % 4 == 2 else 0.04)
            events["hat"].append((bar, step, vel))
        if bar % 4 == 3:
            events["perc"].append((bar, 15, 0.22))

        for index, step in enumerate(bass_steps):
            degree = degree_cycle[(index + bar) % len(degree_cycle)]
            pc = scale[degree % len(scale)]
            note = _pc_to_midi(pc, octave=2)
            if note > 47:
                note -= 12
            dur_steps = _control_bass_duration(step, bass_steps)
            events["bass"].append((bar, step, note, dur_steps, 0.84))

    return {
        "bpm": bpm,
        "bars": bars,
        "beat": beat,
        "swing": swing,
        "events": events,
        "key": analysis["key"],
        "mode": mode,
        "style": analysis["genre"]["primary"],
    }


def _control_bass_degrees(mode: str) -> list[int]:
    if mode == "minor":
        return [0, 4, 6, 4, 0, 2, 4, 5]
    return [0, 4, 5, 4, 0, 2, 4, 1]


def _control_bass_duration(step: int, bass_steps: list[int]) -> float:
    ordered = sorted(set(bass_steps))
    if len(ordered) >= 7:
        return 1.45
    if any(((step + 2) % 16) == other for other in ordered):
        return 1.75
    return 2.35


def _render_mix(composition: dict, analysis: dict, profile: dict, duration: float, rng: random.Random) -> np.ndarray:
    n = int(duration * SR)
    drums = np.zeros((n, 2), dtype=np.float32)
    music = np.zeros((n, 2), dtype=np.float32)
    fx_bus = np.zeros((n, 2), dtype=np.float32)
    kick_times: list[float] = []
    beat = composition["beat"]
    s16 = beat / 4.0
    events = composition["events"]

    for bar, step, vel in events["kick"]:
        t = _event_time(bar, step, s16, composition["swing"])
        kick_times.append(t)
        _add(drums, _kick(vel), t)
    for bar, step, vel in events["snare"]:
        _add(drums, _clap(vel), _event_time(bar, step, s16, composition["swing"]))
    for bar, step, vel in events["hat"]:
        _add(drums, _hat(vel, open_hat=step % 8 == 6), _event_time(bar, step, s16, composition["swing"]))
    for bar, step, vel in events["perc"]:
        _add(drums, _perc(vel, rng), _event_time(bar, step, s16, composition["swing"]))
    for bar, step, note, dur_steps, vel in events["bass"]:
        t = _event_time(bar, step, s16, composition["swing"])
        _add(music, _bass(note, dur_steps * s16, vel), t)
    for bar, step, notes, dur_steps, vel in events["chords"]:
        t = _event_time(bar, step, s16, composition["swing"])
        _add(music, _chord_stab(notes, dur_steps * s16, vel, profile["palette"], rng), t)
    for bar, step, note, dur_steps, vel in events["hook"]:
        t = _event_time(bar, step, s16, composition["swing"])
        _add(music, _lead(note, dur_steps * s16, vel, rng), t)
    for bar, step, note, dur_steps, vel in events["vocal_chop"]:
        t = _event_time(bar, step, s16, composition["swing"])
        _add(music, _vocal_proxy(note, dur_steps * s16, vel, rng), t)
    for bar, step, vel in events["fx"]:
        _add(fx_bus, _riser(beat * 1.5, vel, rng), _event_time(bar, step, s16, 0.0))

    music = _sidechain(music, kick_times)
    music = _stereo_delay(music, delay_l=0.17, delay_r=0.23, feedback=0.22, wet=0.18)
    music = music + _reverb(music, wet=0.08)
    drums = _soft_clip(drums * 1.18)
    mix = drums * 0.9 + music * 0.72 + fx_bus * 0.5
    mix = _high_shelf_control(mix)
    mix = _soft_clip(mix * 1.45)
    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if peak > 0:
        mix = mix / peak * 0.92
    return mix.astype(np.float32)


def _kick(velocity: float) -> np.ndarray:
    length = int(SR * 0.48)
    t = np.arange(length) / SR
    freq = 46 + 74 * np.exp(-t * 34)
    phase = np.cumsum(freq) / SR * 2 * np.pi
    body = np.sin(phase) * np.exp(-t * 9)
    click = np.random.default_rng(7).normal(0, 1, length) * np.exp(-t * 95)
    click = _bandpass(click, SR, 1800, 7000)
    tail = np.sin(2 * np.pi * 42 * t) * np.exp(-t * 5.5)
    mono = (body * 0.78 + click * 0.18 + tail * 0.34) * velocity
    return _stereo(mono)


def _clap(velocity: float) -> np.ndarray:
    length = int(SR * 0.34)
    t = np.arange(length) / SR
    rng = np.random.default_rng(11)
    noise = rng.normal(0, 1, length)
    bursts = sum(np.exp(-np.maximum(0, t - off) * 55) * (t >= off) for off in (0.0, 0.012, 0.027))
    body = _bandpass(noise * bursts, SR, 700, 6500)
    tone = np.sin(2 * np.pi * 188 * t) * np.exp(-t * 16) * 0.18
    mono = (body * 0.45 + tone) * velocity
    return _stereo(mono, width=0.34)


def _hat(velocity: float, open_hat: bool = False) -> np.ndarray:
    length = int(SR * (0.28 if open_hat else 0.09))
    t = np.arange(length) / SR
    rng = np.random.default_rng(23 if open_hat else 19)
    noise = _bandpass(rng.normal(0, 1, length), SR, 5200, 13000)
    metallic = sum(np.sin(2 * np.pi * f * t) for f in (7400, 9100, 11300)) / 3.0
    env = np.exp(-t * (11 if open_hat else 48))
    mono = (noise * 0.7 + metallic * 0.18) * env * velocity
    return _stereo(mono, width=0.55)


def _perc(velocity: float, rng: random.Random) -> np.ndarray:
    length = int(SR * rng.choice([0.14, 0.18, 0.24]))
    t = np.arange(length) / SR
    freq = rng.choice([170, 230, 310, 420])
    body = np.sin(2 * np.pi * freq * t) * np.exp(-t * rng.choice([15, 20, 25]))
    noise = _bandpass(np.random.default_rng(freq).normal(0, 1, length), SR, 600, 5500) * np.exp(-t * 30)
    return _stereo((body * 0.36 + noise * 0.16) * velocity, width=0.42)


def _bass(note: int, duration: float, velocity: float) -> np.ndarray:
    length = max(32, int(SR * duration))
    t = np.arange(length) / SR
    f = _midi_to_hz(note)
    env = _adsr(length, 0.006, 0.08, 0.62, 0.07)
    sub = np.sin(2 * np.pi * f * t)
    saw = sawtooth(2 * np.pi * f * t) * 0.45 + sawtooth(2 * np.pi * f * 1.005 * t) * 0.25
    growl = np.sin(2 * np.pi * (f * 2.01) * t + 0.8 * np.sin(2 * np.pi * f * 0.5 * t)) * 0.18
    mono = _lowpass((sub * 0.65 + saw + growl) * env, SR, 1100)
    mono = np.tanh(mono * 2.2) * 0.58 * velocity
    return _stereo(mono, width=0.08)


def _chord_stab(notes: list[int], duration: float, velocity: float, palette: str, rng: random.Random) -> np.ndarray:
    length = max(32, int(SR * duration))
    t = np.arange(length) / SR
    env = _adsr(length, 0.012, 0.14, 0.24 if palette == "fresh" else 0.34, 0.2)
    mono = np.zeros(length, dtype=np.float32)
    detunes = [-0.008, 0.0, 0.006, 0.011]
    for note in notes:
        f = _midi_to_hz(note)
        for detune in detunes:
            mono += sawtooth(2 * np.pi * f * (1.0 + detune) * t) * 0.09
    cutoff = 1100 + rng.random() * 1400
    mono = _lowpass(mono * env, SR, cutoff)
    mono = np.tanh(mono * 1.7) * velocity
    return _stereo(mono, width=0.62)


def _lead(note: int, duration: float, velocity: float, rng: random.Random) -> np.ndarray:
    length = max(32, int(SR * duration))
    t = np.arange(length) / SR
    f = _midi_to_hz(note)
    env = _adsr(length, 0.004, 0.08, 0.38, 0.08)
    fm = np.sin(2 * np.pi * f * t + 1.8 * np.sin(2 * np.pi * f * 2.0 * t))
    pluck = sawtooth(2 * np.pi * f * 0.5 * t) * 0.28
    mono = _bandpass((fm * 0.55 + pluck) * env, SR, 250, 5200)
    return _stereo(np.tanh(mono * 1.4) * velocity, width=0.48)


def _vocal_proxy(note: int, duration: float, velocity: float, rng: random.Random) -> np.ndarray:
    length = max(32, int(SR * duration))
    t = np.arange(length) / SR
    f = _midi_to_hz(note)
    env = _adsr(length, 0.01, 0.05, 0.25, 0.04)
    carrier = np.sin(2 * np.pi * f * t + 2.2 * np.sin(2 * np.pi * f * 1.51 * t))
    formant = _bandpass(carrier, SR, rng.choice([650, 800, 1000]), rng.choice([2200, 2800, 3400]))
    chopped = formant * env * (0.65 + 0.35 * np.sign(np.sin(2 * np.pi * 18 * t)))
    return _stereo(np.tanh(chopped * 1.8) * velocity, width=0.5)


def _riser(duration: float, velocity: float, rng: random.Random) -> np.ndarray:
    length = max(32, int(SR * duration))
    t = np.arange(length) / SR
    noise = np.random.default_rng(101).normal(0, 1, length)
    cutoff = np.linspace(700, 9000, length)
    mono = noise * np.linspace(0.0, 1.0, length) * np.exp(-np.maximum(0, t - duration * 0.8) * 4)
    mono = _bandpass(mono, SR, 500, 9500)
    mono *= (cutoff / np.max(cutoff)) * velocity * 0.18
    return _stereo(mono, width=0.8)


def _event_time(bar: int, step: int, s16: float, swing: float) -> float:
    delay = swing * s16 if step % 2 == 1 else 0.0
    return (bar * 16 + step) * s16 + delay


def _add(buffer: np.ndarray, sample: np.ndarray, start_seconds: float) -> None:
    start = int(start_seconds * SR)
    if start >= buffer.shape[0]:
        return
    end = min(buffer.shape[0], start + sample.shape[0])
    if end <= start:
        return
    buffer[start:end] += sample[: end - start]


def _sidechain(audio: np.ndarray, kick_times: list[float]) -> np.ndarray:
    if not kick_times:
        return audio
    gain = np.ones(audio.shape[0], dtype=np.float32)
    for t in kick_times:
        start = int(t * SR)
        length = int(SR * 0.22)
        if start >= gain.size:
            continue
        end = min(gain.size, start + length)
        curve = 1.0 - 0.45 * np.exp(-np.linspace(0, 4.5, end - start))
        gain[start:end] = np.minimum(gain[start:end], curve)
    return audio * gain[:, None]


def _stereo_delay(audio: np.ndarray, delay_l: float, delay_r: float, feedback: float, wet: float) -> np.ndarray:
    out = np.array(audio, copy=True)
    for channel, delay in enumerate((delay_l, delay_r)):
        offset = int(delay * SR)
        if offset <= 0 or offset >= out.shape[0]:
            continue
        delayed = np.zeros(out.shape[0], dtype=np.float32)
        delayed[offset:] = out[:-offset, channel] * feedback
        out[:, channel] += delayed * wet
    return out


def _reverb(audio: np.ndarray, wet: float) -> np.ndarray:
    out = np.zeros_like(audio)
    for delay, gain in ((0.031, 0.25), (0.047, 0.18), (0.071, 0.13), (0.113, 0.08)):
        offset = int(delay * SR)
        if offset < audio.shape[0]:
            out[offset:] += audio[:-offset] * gain
    return out * wet


def _write_wav(path: Path, audio: np.ndarray) -> None:
    audio16 = np.asarray(np.clip(audio, -1.0, 1.0) * 32767.0, dtype=np.int16)
    wavfile.write(str(path), SR, audio16)


def _bandpass(samples: np.ndarray, sr: int, low: float, high: float) -> np.ndarray:
    nyq = sr / 2.0
    sos = butter(3, [max(0.001, low / nyq), min(0.999, high / nyq)], btype="band", output="sos")
    return sosfilt(sos, samples)


def _lowpass(samples: np.ndarray, sr: int, cutoff: float) -> np.ndarray:
    sos = butter(3, min(0.999, cutoff / (sr / 2.0)), btype="low", output="sos")
    return sosfilt(sos, samples)


def _smooth(samples: np.ndarray, size: int) -> np.ndarray:
    if size <= 1:
        return samples
    # Cumulative moving average is much faster than direct convolution for
    # multi-minute references.
    pad_left = size // 2
    pad_right = size - pad_left - 1
    padded = np.pad(samples, (pad_left, pad_right), mode="edge")
    cumsum = np.cumsum(np.insert(padded, 0, 0.0))
    return ((cumsum[size:] - cumsum[:-size]) / float(size)).astype(np.float32)


def _band_energy(samples: np.ndarray, sr: int, low: float, high: float) -> float:
    if samples.size == 0:
        return 0.0
    band = _bandpass(samples, sr, low, high)
    return float(np.sqrt(np.mean(np.square(band))))


def _adsr(length: int, attack: float, decay: float, sustain: float, release: float) -> np.ndarray:
    a = max(1, int(SR * attack))
    d = max(1, int(SR * decay))
    r = max(1, int(SR * release))
    s = max(0, length - a - d - r)
    env = np.concatenate(
        [
            np.linspace(0, 1, a),
            np.linspace(1, sustain, d),
            np.full(s, sustain),
            np.linspace(sustain, 0, r),
        ]
    )
    if env.size < length:
        env = np.pad(env, (0, length - env.size))
    return env[:length].astype(np.float32)


def _soft_clip(audio: np.ndarray) -> np.ndarray:
    return np.tanh(audio).astype(np.float32)


def _high_shelf_control(audio: np.ndarray) -> np.ndarray:
    return np.clip(audio, -1.0, 1.0)


def _stereo(mono: np.ndarray, width: float = 0.2) -> np.ndarray:
    left = mono * (1.0 + width * 0.3)
    right = mono * (1.0 - width * 0.3)
    if width > 0.0:
        delay = min(80, max(1, int(width * 80)))
        right = np.pad(right, (delay, 0))[: mono.size]
    return np.column_stack([left, right]).astype(np.float32)


def _resample_linear(samples: np.ndarray, original_sr: int, target_sr: int) -> np.ndarray:
    if original_sr == target_sr:
        return samples
    duration = samples.size / float(original_sr)
    src_x = np.linspace(0.0, duration, samples.size, endpoint=False)
    dst_size = max(1, int(duration * target_sr))
    dst_x = np.linspace(0.0, duration, dst_size, endpoint=False)
    return np.interp(dst_x, src_x, samples).astype(np.float32)


def _parse_key(key: str) -> tuple[int, str]:
    parts = key.split()
    root = parts[0] if parts else "C"
    mode = "minor" if any("min" in part.lower() for part in parts[1:]) else "major"
    return KEY_NOTE.get(root, 0), mode


def _scale(root: int, mode: str) -> list[int]:
    intervals = [0, 2, 3, 5, 7, 8, 10] if mode == "minor" else [0, 2, 4, 5, 7, 9, 11]
    return [(root + interval) % 12 for interval in intervals]


def _chord_roots(root: int, mode: str, palette: str, rng: random.Random) -> list[int]:
    if mode == "minor":
        options = [[0, 10, 8, 7], [0, 3, 10, 5], [0, 5, 8, 10]]
    else:
        options = [[0, 5, 7, 5], [0, 9, 5, 7], [0, 7, 9, 5]]
    progression = list(rng.choice(options))
    if palette == "fresh":
        rng.shuffle(progression)
    return [(root + step) % 12 for step in progression]


def _bass_offsets(mode: str, reuse: float, rng: random.Random) -> list[int]:
    safe = [0, 0, 7, 10, 5] if mode == "minor" else [0, 0, 7, 9, 5]
    if reuse < 0.35:
        safe = [0, 5, 7, 10 if mode == "minor" else 9, 12]
        rng.shuffle(safe)
    return safe


def _chord_notes(root_pc: int, mode: str) -> list[int]:
    intervals = [0, 3, 7, 10] if mode == "minor" else [0, 4, 7, 11]
    return [_pc_to_midi((root_pc + interval) % 12, octave=4) for interval in intervals]


def _pc_to_midi(pc: int, octave: int) -> int:
    return 12 * (octave + 1) + pc


def _midi_to_hz(note: int) -> float:
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


def _vary_steps(reference: list[int], fallback: list[int], reuse: float, rng: random.Random, role: str) -> list[int]:
    source = sorted(set(int(step) % 16 for step in (reference or fallback)))
    kept = [step for step in source if rng.random() < reuse]
    target_count = max(2 if role != "hat" else 4, int(round(len(source) * (0.65 + reuse * 0.35))))
    if role == "kick" and reuse >= 0.55:
        kept.extend([0, 4, 8, 12])
    pool = list(range(16)) if role != "kick" else [0, 3, 4, 7, 8, 10, 12, 14]
    target_count = min(target_count, len(set(pool)))
    while len(set(kept)) < target_count:
        kept.append(rng.choice(pool))
    if role == "hat" and reuse < 0.35:
        kept.extend(rng.sample(list(range(16)), 4))
    return sorted(set(step % 16 for step in kept))


def _section_weight(bar: int, bars: int) -> float:
    if bars <= 4:
        return 1.0
    if bar < 2:
        return 0.62
    if bar >= bars - 2:
        return 0.78
    if bar % 8 in (6, 7):
        return 0.9
    return 1.0


def _composition_summary(composition: dict) -> dict:
    events = composition["events"]
    return {
        "bpm": round(composition["bpm"], 2),
        "key": composition["key"],
        "style": composition["style"],
        "bars": composition["bars"],
        "event_counts": {name: len(values) for name, values in events.items()},
    }


def _build_suno_prompt(analysis: dict, similarity_level: str, user_prompt: str) -> str:
    vocals = analysis["vocals"]
    vocal_line = (
        "Use short original vocal chops or a new vocal-hook role only; do not copy lyrics, singer identity, or exact hook rhythm."
        if vocals.get("present")
        else "Keep it instrumental unless short non-lyrical chops naturally fit."
    )
    user_line = f" User direction: {user_prompt.strip()}" if user_prompt.strip() else ""
    return (
        f"Create an original {analysis['genre']['primary']} track at {analysis['bpm']} BPM in {analysis['key']}. "
        f"Similarity target: {similarity_level}; preserve genre, BPM, key area, mood, energy lane, and groove attitude, "
        f"while changing melodic/bass note identity according to that level. Mood: {analysis['mood']}. "
        f"Drums: {analysis['groove']['drum_feel']} kick behavior, {analysis['groove']['hat_feel']} hats, "
        f"{analysis['groove']['bass_feel']} low-end movement, swing {analysis['groove']['swing']}. "
        f"Sound palette: punchy club drums, controlled sub bass, musical chord stabs, tasteful FX, clean mix, no alien glitches. "
        f"{vocal_line}{user_line}"
    )


def _normalize_similarity(value: str) -> str:
    key = value.strip().lower().replace("_", "-")
    aliases = {
        "mediumhigh": "medium-high",
        "mid-high": "medium-high",
        "mediumlow": "medium-low",
        "mid-low": "medium-low",
        "near-identical-twist": "near-identical",
        "identical": "near-identical",
    }
    key = aliases.get(key, key)
    if key not in SIMILARITY:
        raise ValueError(f"Unknown similarity level '{value}'. Expected one of: {', '.join(SIMILARITY)}")
    return key


def main() -> int:
    parser = argparse.ArgumentParser(description="Render local structured reference-inspired sample audio.")
    parser.add_argument("--reference", required=True, help="Reference WAV/MP3 path")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--similarity-level", default="medium", choices=sorted(SIMILARITY.keys()))
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--candidates", type=int, default=4)
    parser.add_argument("--prompt", default="")
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()

    try:
        payload = render_reference_sample(
            reference_path=args.reference,
            output_dir=args.output_dir,
            similarity_level=args.similarity_level,
            duration_seconds=args.duration,
            candidates=args.candidates,
            prompt=args.prompt,
            seed=args.seed,
        )
    except Exception as exc:
        payload = {"ok": False, "error": {"code": "structured_render_failed", "message": str(exc)}}
    sys.stdout.write(json.dumps(payload, indent=2))
    sys.stdout.write("\n")
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
