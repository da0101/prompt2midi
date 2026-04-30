#!/usr/bin/env python3
"""Deterministic groove-to-audio pipeline.

Usage (CLI):
    NUMBA_CACHE_DIR=/tmp/prompt2midi-numba-cache \\
    python3 analysis/groove_render.py \\
        --ref "test/fixtures/Callao (Edit).mp3" \\
        --out /tmp/callao-90 \\
        --similarity 90 \\
        --bars 16

Outputs written to <out>/:
    sample.wav   – synthesised audio loop
    bass.mid     – bass MIDI
    drums.mid    – drum MIDI
    groove.json  – extracted groove + event summary

Use --similarity 100 for closest-to-reference, 80 for noticeably different bass.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from groove_to_midi import groove_to_events, similarity_to_variation
from midi_extraction import write_note_events_midi, write_multitrack_midi
from simple_synth import render_groove_audio, write_wav


DEFAULT_DURATION = 30.0
DEFAULT_SR       = 44100


def render_groove_sample(
    reference_audio: str,
    output_dir: str,
    similarity: float = 90.0,        # 0–100, higher = closer to reference
    key: str | None = None,
    bpm: float | None = None,
    bars: int = 16,
    duration_seconds: float = DEFAULT_DURATION,
    seed: int | None = None,
) -> dict:
    """Full pipeline: analyse reference → generate MIDI → synthesise audio.

    Returns a result dict describing outputs and groove metadata.
    """
    os.makedirs(output_dir, exist_ok=True)

    # ── 1. Analyse reference groove ──────────────────────────────────────────
    groove = _analyse_groove(reference_audio, bpm)
    actual_bpm  = bpm  or float(groove.get("bpm")  or 124.0)
    actual_key  = key  or _infer_key(groove)

    # ── 2. Derive variation level ────────────────────────────────────────────
    variation_level = similarity_to_variation(similarity)

    # ── 3. Generate MIDI events ──────────────────────────────────────────────
    events = groove_to_events(
        reference_groove=groove,
        variation_level=variation_level,
        key=actual_key,
        bpm=actual_bpm,
        bars=bars,
        seed=seed,
    )
    bass_events = events["bass"]
    drum_events = events["drums"]

    # ── 4. Write MIDI files ──────────────────────────────────────────────────
    midi_dir  = os.path.join(output_dir, "midi")
    bass_mid  = write_note_events_midi(os.path.join(midi_dir, "bass.mid"), bass_events, actual_bpm)
    drums_mid = write_note_events_midi(os.path.join(midi_dir, "drums.mid"), drum_events, actual_bpm)
    full_mid  = write_multitrack_midi(
        os.path.join(midi_dir, "full_loop.mid"),
        [bass_events, drum_events],
        actual_bpm,
    )

    # ── 5. Synthesise audio ──────────────────────────────────────────────────
    audio = render_groove_audio(
        bass_events=bass_events,
        drum_events=drum_events,
        bpm=actual_bpm,
        sr=DEFAULT_SR,
        duration_seconds=duration_seconds,
    )
    wav_path = write_wav(os.path.join(output_dir, "sample.wav"), audio, DEFAULT_SR)

    # ── 6. Write inspection JSON ─────────────────────────────────────────────
    result = {
        "status":           "succeeded",
        "provider":         "groove_render",
        "sample":           wav_path,
        "midi": {
            "bass":      bass_mid,
            "drums":     drums_mid,
            "full_loop": full_mid,
        },
        "bpm":              actual_bpm,
        "key":              actual_key,
        "similarity":       similarity,
        "variation_level":  variation_level,
        "bass_notes_used":  events["bass_notes_used"],
        "groove_grid_used": events["groove_grid_used"],
        "reference_groove": {
            k: v for k, v in groove.items()
            if k not in ("prompt", "warnings")
        },
        "duration_seconds": duration_seconds,
    }

    groove_json = os.path.join(output_dir, "groove.json")
    with open(groove_json, "w") as fh:
        json.dump(result, fh, indent=2, default=str)

    return result


# ── Groove analysis (wraps reference_groove with fallback) ────────────────────

def _analyse_groove(audio_path: str, bpm: float | None) -> dict:
    """Call reference_groove analysis; fall back to minimal stub if unavailable."""
    try:
        from reference_groove import analyze_reference_groove
        groove = analyze_reference_groove(audio_path, bpm)
        return groove
    except Exception as exc:
        return {
            "method": "unavailable",
            "kick_pattern_16th": [],
            "bass_accent_pattern_16th": [],
            "hat_pattern_16th": [],
            "bass_motif_16th": [],
            "bass_notes": [],
            "swing": 0.0,
            "warnings": [str(exc)],
        }


def _infer_key(groove: dict) -> str:
    """Return a best-guess key from the groove fingerprint."""
    notes = groove.get("bass_notes") or []
    if notes:
        root = notes[0]
        return f"{root}m"   # assume minor for underground house
    return "Am"


# ── Suno prompt builder ───────────────────────────────────────────────────────

def build_suno_prompt(result: dict) -> str:
    """Return a Suno-ready text prompt derived from the groove analysis."""
    bpm   = result.get("bpm", 124)
    key   = result.get("key", "Am")
    notes = result.get("bass_notes_used") or []
    grid  = result.get("groove_grid_used") or {}
    groove = result.get("reference_groove") or {}

    drum_feel   = groove.get("drum_feel", "four-on-floor")
    bass_feel   = groove.get("bass_feel", "syncopated bassline")
    low_weight  = groove.get("low_end_weight", "heavy")
    energy      = groove.get("club_energy", "club")

    kick_positions = grid.get("kick", [])
    bass_positions = grid.get("bass", [])

    parts = [
        f"underground minimal tech house, {round(bpm)} BPM, {key}",
        f"{energy} energy, {low_weight} low-end",
        drum_feel,
        bass_feel,
        "punchy transient kick, tight hi-hats, sparse dark chord stabs",
        "dry club mix, no reverb on kick, gritty distorted bass",
    ]

    if kick_positions:
        parts.append(f"kick accent pattern (16th grid): {kick_positions[:8]}")
    if bass_positions:
        parts.append(f"bass rhythm accents: {bass_positions[:8]}")
    if notes:
        parts.append(f"bass uses notes: {', '.join(notes[:4])}")

    parts += [
        "no vocals, no melody, no pads, instrumental only",
        "30 seconds, tight loop, production ready",
    ]

    return ". ".join(parts) + "."


# ── CLI ───────────────────────────────────────────────────────────────────────

def _cli() -> None:
    parser = argparse.ArgumentParser(description="Render a groove-inspired sample from a reference track.")
    parser.add_argument("--ref",        required=True, help="Reference MP3/WAV path")
    parser.add_argument("--out",        required=True, help="Output directory")
    parser.add_argument("--similarity", type=float, default=90.0, help="0-100, 100=closest to ref")
    parser.add_argument("--key",        default=None, help="Override key, e.g. 'Am'")
    parser.add_argument("--bpm",        type=float, default=None, help="Override BPM")
    parser.add_argument("--bars",       type=int, default=16, help="Bars to generate (default 16 ≈ 30s)")
    parser.add_argument("--duration",   type=float, default=DEFAULT_DURATION, help="Target seconds")
    parser.add_argument("--seed",       type=int, default=None)
    args = parser.parse_args()

    result = render_groove_sample(
        reference_audio=args.ref,
        output_dir=args.out,
        similarity=args.similarity,
        key=args.key,
        bpm=args.bpm,
        bars=args.bars,
        duration_seconds=args.duration,
        seed=args.seed,
    )

    print(json.dumps(result, indent=2, default=str))

    suno = build_suno_prompt(result)
    suno_path = os.path.join(args.out, "suno_prompt.txt")
    with open(suno_path, "w") as fh:
        fh.write(suno + "\n")
    print(f"\n── Suno prompt written to {suno_path} ──")
    print(suno)


if __name__ == "__main__":
    _cli()
