#!/usr/bin/env python3
"""Pure numpy/scipy drum and bass synthesiser for minimal/tech house.

No FluidSynth or external audio tools required.
All sounds are deterministic given the same seed / parameters.

Exports:
    render_groove_audio(bass_events, drum_events, bpm, sr, duration_seconds) -> np.ndarray
    write_wav(path, audio, sr) -> str
"""
from __future__ import annotations

import os

import numpy as np
from scipy.signal import butter, sosfilt


SR_DEFAULT = 44100

# GM drum note → synth type
_KICK_NOTES   = {36, 35}
_SNARE_NOTES  = {38, 40}
_CLAP_NOTES   = {39}
_HAT_C_NOTES  = {42, 44}
_HAT_O_NOTES  = {46}
_PERC_NOTES   = {70, 75, 76}


# ── Public API ────────────────────────────────────────────────────────────────

def render_groove_audio(
    bass_events: list[dict],
    drum_events: list[dict],
    bpm: float = 124.0,
    sr: int = SR_DEFAULT,
    duration_seconds: float = 30.0,
) -> np.ndarray:
    """Synthesise bass + drums into a single stereo float32 array [-1, 1]."""
    n_samples = int(sr * duration_seconds)
    mix = np.zeros(n_samples, dtype=np.float64)

    # Pre-render one-shot samples
    kick_sample  = _render_kick(sr)
    clap_sample  = _render_clap(sr)
    hat_c_sample = _render_hat(sr, closed=True)
    hat_o_sample = _render_hat(sr, closed=False)

    # Place drums
    for event in drum_events:
        note = int(event.get("midi_note", 0))
        start_samp = int(event["start"] * sr)
        if start_samp >= n_samples:
            continue
        vel = float(event.get("velocity", 100)) / 127.0

        if note in _KICK_NOTES:
            _add_sample(mix, kick_sample, start_samp, gain=vel * 0.9)
        elif note in _SNARE_NOTES:
            _add_sample(mix, clap_sample, start_samp, gain=vel * 0.6)
        elif note in _CLAP_NOTES:
            _add_sample(mix, clap_sample, start_samp, gain=vel * 0.65)
        elif note in _HAT_C_NOTES:
            _add_sample(mix, hat_c_sample, start_samp, gain=vel * 0.35)
        elif note in _HAT_O_NOTES:
            _add_sample(mix, hat_o_sample, start_samp, gain=vel * 0.30)

    # Place bass notes
    for event in bass_events:
        note      = int(event.get("midi_note", 36))
        start_s   = float(event["start"])
        dur_s     = float(event["duration"])
        vel       = float(event.get("velocity", 90)) / 127.0
        start_samp = int(start_s * sr)
        if start_samp >= n_samples:
            continue
        remaining = (n_samples - start_samp) / float(sr)
        actual_dur = min(dur_s, remaining)
        if actual_dur < 0.01:
            continue
        bass_note_audio = _render_bass_note(note, actual_dur, sr)
        _add_sample(mix, bass_note_audio, start_samp, gain=vel * 0.55)

    # Soft-clip and normalise to -2 dBFS
    mix = np.tanh(mix * 1.5)
    peak = np.max(np.abs(mix)) or 1.0
    mix = mix / peak * 0.8

    # Convert to stereo
    stereo = np.stack([mix, mix], axis=-1).astype(np.float32)
    return stereo


def write_wav(path: str, audio: np.ndarray, sr: int = SR_DEFAULT) -> str:
    """Write a float32 stereo array to a 16-bit WAV file."""
    from scipy.io import wavfile

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    # Convert float32 → int16
    int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    wavfile.write(path, sr, int16)
    return os.path.abspath(path)


# ── Drum synthesis ────────────────────────────────────────────────────────────

def _render_kick(sr: int) -> np.ndarray:
    """Sub-sweep kick: exponential frequency drop + amplitude envelope."""
    dur    = 0.55
    n      = int(sr * dur)
    t      = np.linspace(0, dur, n, endpoint=False)

    # Frequency sweep: 130 Hz → 45 Hz in 60 ms, then constant
    freq   = (130.0 - 45.0) * np.exp(-40.0 * t) + 45.0
    phase  = np.cumsum(2.0 * np.pi * freq / sr)
    tone   = np.sin(phase)

    # Click transient at attack (noise burst in click band)
    click  = np.random.RandomState(1).randn(n)
    click_sos = butter(2, [800.0, 6000.0], btype="band", fs=sr, output="sos")
    click  = sosfilt(click_sos, click)
    click *= np.exp(-80.0 * t)

    # Combined amplitude envelope
    amp_tone  = np.exp(-6.0 * t)
    amp_click = np.exp(-120.0 * t)
    out = tone * amp_tone * 0.85 + click * amp_click * 0.15

    return out.astype(np.float32)


def _render_hat(sr: int, closed: bool = True) -> np.ndarray:
    """Metallic hat: high-pass filtered noise with short exponential decay."""
    dur  = 0.045 if closed else 0.20
    n    = int(sr * dur)
    t    = np.linspace(0, dur, n, endpoint=False)

    noise = np.random.RandomState(2 if closed else 3).randn(n)
    sos   = butter(4, [6500.0, 18000.0], btype="band", fs=sr, output="sos")
    filt  = sosfilt(sos, noise)

    decay = 60.0 if closed else 18.0
    env   = np.exp(-decay * t)
    return (filt * env).astype(np.float32)


def _render_clap(sr: int) -> np.ndarray:
    """Tight clap: three very short noise bursts layered."""
    dur   = 0.12
    n     = int(sr * dur)
    t     = np.linspace(0, dur, n, endpoint=False)
    rng   = np.random.RandomState(4)

    sos   = butter(3, [1200.0, 12000.0], btype="band", fs=sr, output="sos")
    out   = np.zeros(n)
    for delay_ms in (0, 8, 16):
        delay_n = int(delay_ms / 1000.0 * sr)
        burst   = rng.randn(n - delay_n)
        burst   = sosfilt(sos, burst)
        burst  *= np.exp(-80.0 * t[:n - delay_n])
        out[delay_n:] += burst * 0.33

    return out.astype(np.float32)


# ── Bass synthesis ────────────────────────────────────────────────────────────

def _render_bass_note(midi_note: int, duration: float, sr: int) -> np.ndarray:
    """Bandlimited sawtooth bass with lowpass filter and quick envelope."""
    freq = 440.0 * 2.0 ** ((midi_note - 69) / 12.0)
    n    = int(sr * duration)
    t    = np.linspace(0, duration, n, endpoint=False)

    # Bandlimited sawtooth: sum of harmonics up to Nyquist
    saw = np.zeros(n)
    k   = 1
    while freq * k < sr / 2.0 and k <= 20:
        saw += ((-1) ** (k + 1)) * np.sin(2.0 * np.pi * freq * k * t) / k
        k   += 1
    saw *= 2.0 / np.pi

    # Lowpass filter (warm, house-like)
    cutoff = min(freq * 5.0, 3500.0)
    cutoff = max(cutoff, 100.0)
    lp_sos = butter(2, cutoff, btype="low", fs=sr, output="sos")
    filtered = sosfilt(lp_sos, saw)

    # Amplitude envelope: fast attack, sustain, short tail
    attack_n = min(int(sr * 0.008), n)
    tail_n   = min(int(sr * 0.04), n // 4)
    env = np.ones(n)
    if attack_n > 0:
        env[:attack_n] = np.linspace(0.0, 1.0, attack_n)
    if tail_n > 0:
        env[-tail_n:] *= np.linspace(1.0, 0.0, tail_n)

    return (filtered * env).astype(np.float32)


# ── Mixing utility ────────────────────────────────────────────────────────────

def _add_sample(
    mix: np.ndarray,
    sample: np.ndarray,
    start: int,
    gain: float = 1.0,
) -> None:
    end    = min(start + len(sample), len(mix))
    count  = end - start
    if count > 0:
        mix[start:end] += sample[:count] * gain
