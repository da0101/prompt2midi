#!/usr/bin/env python3
"""Spectral instrument and production type analysis for prompt2midi.

Uses librosa band-energy ratios, onset characteristics, and timbral
features to produce producer-readable descriptions of:
- Production type (electronic / acoustic / orchestral / hybrid)
- Bass character (sub synth / synth bass / bass guitar / acoustic)
- Drum character (drum machine / live kit / hybrid)
- Instrument presence hints (strings, brass, guitar, piano, etc.)
- Era and production style hints

All functions degrade gracefully when librosa is unavailable.
"""
from __future__ import annotations

import math
import os

_ANALYSIS_DURATION = 60.0  # seconds to analyse (centre window)
_SR = 22050


def analyze_instruments(audio_path: str, bpm: float = 120.0, key: str = "") -> dict:
    """Return production type, bass/drum character, instrument hints, and a description string.

    The ``description`` field is suitable for injecting directly into an ACE or Suno prompt.
    """
    if os.environ.get("PROMPT2MIDI_DISABLE_INSTRUMENT_ANALYSIS") == "1":
        return _unavailable("disabled by environment")

    try:
        import librosa
        import numpy as np
    except ImportError:
        return _unavailable("librosa not available")

    try:
        y, sr = librosa.load(audio_path, sr=_SR, mono=True)
        y = _centre_window(y, sr, _ANALYSIS_DURATION)
    except Exception as exc:
        return _unavailable(f"audio load failed: {exc}")

    try:
        return _run_analysis(y, sr, bpm, key)
    except Exception as exc:
        return _unavailable(f"analysis error: {exc}")


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def _run_analysis(y, sr, bpm: float, key: str) -> dict:
    import librosa
    import numpy as np

    # --- band energy ratios --------------------------------------------------
    bands = _band_energies(y, sr)
    total_e = max(1e-9, sum(bands.values()))
    sub_ratio   = bands["sub"]   / total_e   # 40-120 Hz
    bass_ratio  = bands["bass"]  / total_e   # 120-400 Hz
    low_mid_ratio = bands["low_mid"] / total_e  # 400-1000 Hz
    mid_ratio   = bands["mid"]   / total_e   # 1000-3000 Hz
    hi_mid_ratio = bands["hi_mid"] / total_e  # 3000-8000 Hz

    # --- spectral centroid ---------------------------------------------------
    centroid_mean = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
    # Electronic dance music: typically 1500-3500 Hz; orchestral: 1200-2800 Hz; rock/pop: 1800-3200 Hz

    # --- spectral flatness (0=tonal, 1=noise) --------------------------------
    flatness_mean = float(np.mean(librosa.feature.spectral_flatness(y=y)))
    # Electronic synths: 0.03-0.15; acoustic instruments: 0.005-0.04; live recordings: very low

    # --- spectral contrast (instrument separation) --------------------------
    contrast = librosa.feature.spectral_contrast(y=y, sr=sr, n_bands=6)
    contrast_mean = float(np.mean(contrast))
    # High contrast = clear instrument separation (live/orchestral)
    # Low contrast = dense/compressed mix (typical EDM master)

    # --- onset sharpness for drum character ----------------------------------
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onset_mean = float(np.mean(onset_env))
    onset_max = float(np.max(onset_env))
    onset_ratio = onset_mean / max(1e-9, onset_max)
    # High onset_mean / max ratio = many transients (busy/electronic)
    # Low ratio = sparse sharp hits (punchy live kit)

    # --- zero crossing rate --------------------------------------------------
    zcr_mean = float(np.mean(librosa.feature.zero_crossing_rate(y=y)))
    # High ZCR = lots of high-frequency content or noise (electronic)

    # --- HPSS harmonic/percussive ratio -------------------------------------
    y_harm, y_perc = librosa.effects.hpss(y)
    harm_energy = float(np.sum(y_harm ** 2))
    perc_energy = float(np.sum(y_perc ** 2))
    perc_ratio = perc_energy / max(1e-9, harm_energy + perc_energy)
    # High perc_ratio = percussion-dominated (drum-heavy)

    # --- derive production characteristics ----------------------------------
    production_type = _classify_production(
        sub_ratio, bass_ratio, mid_ratio, hi_mid_ratio,
        flatness_mean, contrast_mean, centroid_mean, bpm,
        onset_ratio=onset_ratio, zcr_mean=zcr_mean,
    )

    bass_character = _classify_bass(sub_ratio, bass_ratio, low_mid_ratio, bpm)

    drum_character = _classify_drums(
        onset_ratio, perc_ratio, contrast_mean, bpm, production_type,
    )

    instrument_hints = _detect_instrument_hints(
        mid_ratio, hi_mid_ratio, low_mid_ratio, bass_ratio,
        harm_energy, perc_energy, contrast_mean, flatness_mean,
    )

    era_hint = _infer_era(
        bpm, contrast_mean, sub_ratio, bass_ratio, mid_ratio, production_type,
    )

    genre_suggestion = _suggest_genre(
        production_type, bass_character, drum_character,
        instrument_hints, era_hint, bpm,
    )

    description = _build_description(
        production_type, bass_character, drum_character,
        instrument_hints, era_hint, genre_suggestion,
    )

    return {
        "available": True,
        "production_type": production_type,
        "bass_character": bass_character,
        "drum_character": drum_character,
        "instrument_hints": instrument_hints,
        "era_hint": era_hint,
        "genre_suggestion": genre_suggestion,
        "description": description,
        "spectral_features": {
            "sub_ratio": round(sub_ratio, 4),
            "bass_ratio": round(bass_ratio, 4),
            "mid_ratio": round(mid_ratio, 4),
            "hi_mid_ratio": round(hi_mid_ratio, 4),
            "spectral_centroid_hz": round(centroid_mean, 1),
            "spectral_flatness": round(flatness_mean, 5),
            "spectral_contrast": round(contrast_mean, 3),
            "percussive_ratio": round(perc_ratio, 3),
            "onset_ratio": round(onset_ratio, 4),
        },
        "method": "librosa_spectral",
    }


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

def _band_energies(y, sr) -> dict:
    import numpy as np
    import librosa

    stft = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr)

    def band(lo, hi):
        mask = (freqs >= lo) & (freqs < hi)
        return float(np.mean(stft[mask] ** 2)) if mask.any() else 0.0

    return {
        "sub":     band(40, 120),
        "bass":    band(120, 400),
        "low_mid": band(400, 1000),
        "mid":     band(1000, 3000),
        "hi_mid":  band(3000, 8000),
        "air":     band(8000, 20000),
    }


def _classify_production(
    sub_ratio, bass_ratio, mid_ratio, hi_mid_ratio,
    flatness, contrast, centroid, bpm,
    onset_ratio: float = 0.07,
    zcr_mean: float = 0.1,
) -> str:
    """Classify into: electronic / acoustic / orchestral / hybrid.

    Primary discriminator: bass_harmonic_ratio = bass_ratio / sub_ratio.
    Electronic music uses sub-only bass patches (ratio ~0.04).
    Live/acoustic music (bass guitar, Minimoog) has rich harmonics (ratio ~0.15+).
    This cleanly separates house/techno from 80s pop-funk even at the same BPM.
    """
    electronic_score = 0.0
    orchestral_score = 0.0

    # PRIMARY: bass harmonic ratio (most reliable live-vs-electronic discriminator)
    # Electronic bass = sub-only (bass_ratio << sub_ratio)
    # Live/acoustic bass = harmonically rich (bass_ratio is meaningful)
    bass_harmonic = bass_ratio / max(1e-9, sub_ratio)
    if bass_harmonic > 0.12:
        orchestral_score += 0.45   # rich harmonic bass → live instrument
    elif bass_harmonic > 0.07:
        orchestral_score += 0.15   # some harmonics → possibly warm synth
    elif bass_harmonic < 0.06:
        electronic_score += 0.30   # sub-only bass → electronic patch

    # SECONDARY: spectral flatness (synthesizer noise vs tonal instruments)
    if flatness > 0.07:
        electronic_score += 0.25   # noisy/synthetic
    elif flatness > 0.05:
        electronic_score += 0.10
    elif flatness < 0.035:
        orchestral_score += 0.15   # very tonal → acoustic

    # SECONDARY: onset density (busy electronic transients from hi-hats/synths)
    if onset_ratio > 0.09:
        electronic_score += 0.15   # many small transients → drum machine / hi-hat patterns

    # SECONDARY: ZCR (vocals, dense synths, hi-hat heavy mixes)
    if zcr_mean > 0.16:
        electronic_score += 0.10   # lots of high-frequency content
    elif zcr_mean > 0.13:
        electronic_score += 0.05

    # WEAK: mid-range energy relative to sub+bass total
    mid_to_bass = mid_ratio / max(1e-9, sub_ratio + bass_ratio)
    if mid_to_bass > 0.008:
        orchestral_score += 0.12   # meaningful orchestral midrange

    # Decision
    if electronic_score >= 0.40 and orchestral_score < 0.25:
        return "electronic"
    if orchestral_score >= 0.45 and electronic_score < 0.20:
        return "orchestral" if mid_to_bass > 0.008 else "acoustic"
    if orchestral_score >= 0.35 and electronic_score < 0.15:
        return "hybrid"
    if orchestral_score >= 0.25 and electronic_score >= 0.15:
        return "hybrid"
    if electronic_score >= 0.25:
        return "hybrid"
    return "acoustic"


def _classify_bass(sub_ratio, bass_ratio, low_mid_ratio, bpm) -> str:
    """Classify bass as: sub_synth / synth_bass / bass_guitar / warm_synth / acoustic_bass."""
    if sub_ratio > 0.40 and bass_ratio < 0.12:
        return "sub_synth"  # Very sub-heavy, almost no bass guitar midrange — sub-bass synth
    if sub_ratio > 0.30 and bass_ratio < 0.18:
        return "synth_bass"  # Significant sub + some mid — classic synth bass
    if bass_ratio > sub_ratio and low_mid_ratio > 0.08:
        return "bass_guitar"  # More midrange than sub — bass guitar signature
    if sub_ratio > 0.20 and bass_ratio > 0.12:
        return "warm_synth_or_bass_guitar"  # Ambiguous — warm synth or bass guitar
    if bass_ratio > 0.20 and sub_ratio < 0.15:
        return "acoustic_bass"  # Mostly midrange bass, little sub
    return "bass"


def _classify_drums(onset_ratio, perc_ratio, contrast, bpm, production_type) -> str:
    """Classify drum character: drum_machine / live_kit / hybrid / programming."""
    if production_type == "electronic" and perc_ratio > 0.45:
        return "drum_machine"
    if production_type == "electronic" and onset_ratio > 0.25:
        return "programming"  # Electronic but less punchy
    if perc_ratio > 0.40 and contrast > 15.0:
        return "live_kit"  # High percussive energy + high contrast = real drums
    if perc_ratio > 0.35 and production_type in ("acoustic", "orchestral", "hybrid"):
        return "live_kit"
    if perc_ratio > 0.30:
        return "hybrid_kit"
    if perc_ratio < 0.15:
        return "minimal_percussion"
    return "hybrid_kit"


def _detect_instrument_hints(
    mid_ratio, hi_mid_ratio, low_mid_ratio, bass_ratio,
    harm_energy, perc_energy, contrast, flatness,
) -> list[str]:
    """Return list of likely instrument types from spectral signatures.

    Uses ratios relative to bass energy to handle bass-dominated mixes where
    absolute mid-range ratios look small even when orchestral instruments are present.
    """
    hints = []
    bass_ref = max(1e-9, bass_ratio)

    # Strings/orchestral: energy in 1-3 kHz relative to bass + high contrast + harmonic content
    if (mid_ratio / bass_ref > 0.05 or contrast > 17.0) and harm_energy > perc_energy * 0.6:
        hints.append("strings_or_orchestral")

    # Brass: mid + hi-mid with harmonic richness and high contrast
    if mid_ratio / bass_ref > 0.04 and contrast > 17.0 and hi_mid_ratio / bass_ref > 0.01:
        hints.append("brass_or_horns")

    # Guitar: low-mid + mid energy relative to bass
    if low_mid_ratio / bass_ref > 0.3 and mid_ratio / bass_ref > 0.05 and contrast > 12.0:
        hints.append("electric_or_acoustic_guitar")

    # Piano/keyboard: harmonic richness, tonal, some mid content
    if harm_energy > perc_energy * 1.2 and mid_ratio / bass_ref > 0.04 and flatness < 0.04:
        hints.append("piano_or_keyboard")

    # Synth pads: harmonic content + moderate flatness (not as flat as pure electronic)
    if 0.04 < flatness < 0.09 and harm_energy > perc_energy * 0.8 and mid_ratio / bass_ref > 0.03:
        hints.append("synth_pads")

    return hints


def _infer_era(bpm, contrast, sub_ratio, bass_ratio, mid_ratio, production_type) -> str:
    """Infer rough era/decade from spectral + tempo characteristics."""
    if production_type == "electronic" and sub_ratio > 0.35 and bpm >= 128:
        return "2000s_2020s"  # Modern EDM: heavy sub, high BPM
    # High contrast non-electronic productions often 80s-90s (pre-loudness-war mastering)
    if production_type in ("acoustic", "orchestral", "hybrid") and contrast > 17.0:
        if 95 <= bpm <= 135:
            return "1980s_1990s"
    if production_type in ("acoustic", "orchestral", "hybrid") and contrast > 15.0:
        if bass_ratio > 0.08:
            return "1980s_1990s"
    if production_type == "electronic" and sub_ratio > 0.25 and 115 <= bpm <= 135:
        return "1990s_2010s"  # Classic house/techno era
    return "contemporary"


def _suggest_genre(
    production_type, bass_character, drum_character,
    instrument_hints, era_hint, bpm,
) -> str:
    """Suggest a human-readable genre description from the combined features."""
    has_strings = "strings_or_orchestral" in instrument_hints
    has_brass = "brass_or_horns" in instrument_hints
    has_guitar = "electric_or_acoustic_guitar" in instrument_hints
    has_piano = "piano_or_keyboard" in instrument_hints
    has_synth = "synth_pads" in instrument_hints

    live_drums = drum_character in ("live_kit",)
    live_bass = bass_character in ("bass_guitar", "acoustic_bass")

    # Orchestral / cinematic pop
    if (has_strings or has_brass) and production_type in ("orchestral", "hybrid", "acoustic"):
        if era_hint in ("1980s_1990s",) and live_drums:
            return "1980s pop-funk with orchestral production"
        if has_brass and live_drums:
            return "funk-pop with brass and live drums"
        return "orchestral pop"

    # Electronic dance
    if production_type == "electronic":
        if drum_character == "drum_machine" and 118 <= bpm <= 135:
            return "electronic dance music"
        if 118 <= bpm <= 132:
            return "house or techno"
        if bpm >= 132:
            return "hard dance or techno"
        return "electronic"

    # Acoustic / organic
    if live_bass and live_drums and not has_synth:
        if has_brass or has_strings:
            return "funk or R&B with live band"
        return "live band recording"

    # Hybrid
    if production_type == "hybrid":
        if has_piano or has_strings:
            return "pop production"
        return "hybrid electronic-acoustic"

    return "mixed production"


def _build_description(
    production_type, bass_character, drum_character,
    instrument_hints, era_hint, genre_suggestion,
) -> str:
    """Build a human-readable production description for the ACE/Suno prompt."""
    parts = []

    # Production type
    prod_desc = {
        "electronic": "electronic production",
        "acoustic": "acoustic or live production",
        "orchestral": "orchestral production with live instruments",
        "hybrid": "hybrid production mixing live and electronic elements",
    }.get(production_type, "mixed production")
    parts.append(prod_desc)

    # Drums
    drum_desc = {
        "drum_machine": "programmed drum machine",
        "live_kit": "live drum kit with acoustic character",
        "hybrid_kit": "hybrid drum sound mixing live and programmed elements",
        "programming": "electronically programmed drums",
        "minimal_percussion": "minimal or sparse percussion",
    }.get(drum_character, "drums")
    parts.append(drum_desc)

    # Bass
    bass_desc = {
        "sub_synth": "deep sub-bass synthesizer",
        "synth_bass": "synthesizer bass line",
        "bass_guitar": "bass guitar with warm midrange tone",
        "warm_synth_or_bass_guitar": "warm bass — bass guitar or characterful synth bass",
        "acoustic_bass": "acoustic or upright bass",
        "bass": "bass",
    }.get(bass_character, "bass")
    parts.append(bass_desc)

    # Instrument hints
    hint_descs = {
        "strings_or_orchestral": "orchestral strings",
        "brass_or_horns": "brass and horn accents",
        "electric_or_acoustic_guitar": "guitar",
        "piano_or_keyboard": "piano or keyboard",
        "synth_pads": "synthesizer pads",
    }
    for hint in instrument_hints:
        if hint in hint_descs:
            parts.append(hint_descs[hint])

    # Era
    if era_hint == "1980s_1990s":
        parts.append("1980s–1990s production style")
    elif era_hint == "2000s_2020s":
        parts.append("modern production")

    combined = "; ".join(parts)
    return f"{genre_suggestion} — {combined}" if genre_suggestion else combined


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _centre_window(y, sr: int, max_seconds: float):
    """Return a centre-extracted window of the audio."""
    import numpy as np
    target = int(sr * max_seconds)
    if len(y) <= target:
        return y
    start = (len(y) - target) // 2
    return y[start: start + target]


def _unavailable(reason: str) -> dict:
    return {
        "available": False,
        "production_type": "unknown",
        "bass_character": "unknown",
        "drum_character": "unknown",
        "instrument_hints": [],
        "era_hint": "unknown",
        "genre_suggestion": "",
        "description": "",
        "method": "unavailable",
        "warnings": [reason],
    }
