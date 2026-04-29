#!/usr/bin/env python3
"""Composition engine: generates a style-aware, randomised inspired loop from analysis hints."""
from __future__ import annotations

import json
import os
import random
import sys
import time

from composition_patterns import (
    _bass_events,
    _chord_events,
    _drum_events,
    _melody_events,
)
from midi_extraction import write_multitrack_midi, write_note_events_midi

_KEY_NOTE: dict[str, int] = {
    "C": 60, "C#": 61, "Db": 61, "D": 62, "D#": 63, "Eb": 63,
    "E": 64, "F": 65, "F#": 66, "Gb": 66, "G": 67, "G#": 68,
    "Ab": 68, "A": 69, "A#": 70, "Bb": 70, "B": 71,
}

_STYLE_KEYWORDS: dict[str, list[str]] = {
    "synth_wave": ["synth wave", "synthwave", "retrowave", "new wave", "synth pop",
                   "vapor wave", "vaporwave", "electropop", "italo"],
    "hip_hop":    ["hip hop", "hip-hop", "trap", "r&b", "rnb", "lo-fi", "lofi",
                   "boom bap", "soul", "funk"],
    "techno":     ["techno", "minimal", "ebm", "industrial", "drum and bass",
                   "dnb", "dubstep", "breakbeat"],
    "ambient":    ["ambient", "chillout", "chill out", "downtempo", "drone",
                   "new age", "atmospheric"],
    "house":      ["house", "tech house", "deep house", "progressive house",
                   "trance", "electro", "disco", "dance"],
}


def generate_inspired_loop(
    analysis: dict,
    output_dir: str,
    bars: int = 32,
) -> tuple[dict, dict]:
    """Generate a new original loop and return (composition_dict, suno_prompt_dict)."""
    bpm = float(analysis.get("bpm") or 120.0)
    root_midi, mode = _parse_key(str(analysis.get("key") or "C major"))
    key_str = str(analysis.get("key") or "C major")
    style_label = _infer_style(analysis)
    style = _composition_style(analysis)
    rng = random.Random(int(time.time() * 1000) % (2 ** 32))

    midi_dir = os.path.join(output_dir, "midi")
    os.makedirs(midi_dir, exist_ok=True)

    detected_chords = (analysis.get("chords") or {}).get("progression") or []
    detected_drums = analysis.get("drums") or {}

    _progress(f"composition: generating bass — {key_str} style={style}")
    bass = _bass_events(root_midi - 24, bpm, bars, style, rng)
    _progress(f"composition: generating drums — style={style}")
    drums = _drum_events(bpm, bars, style, rng,
                         detected_drums if detected_drums.get("kick") else None)
    _progress("composition: generating chords")
    chords = _chord_events(root_midi - 12, mode, bpm, bars, style, rng,
                           detected_chords if len(detected_chords) >= 2 else None)
    _progress("composition: generating melody")
    melody = _melody_events(root_midi, mode, bpm, bars, style, rng)
    _progress("composition: writing MIDI files")

    paths = {
        "bass":      write_note_events_midi(os.path.join(midi_dir, "bass.mid"),      bass,   bpm),
        "drums":     write_note_events_midi(os.path.join(midi_dir, "drums.mid"),     drums,  bpm),
        "chords":    write_note_events_midi(os.path.join(midi_dir, "chords.mid"),    chords, bpm),
        "melody":    write_note_events_midi(os.path.join(midi_dir, "melody.mid"),    melody, bpm),
        "full_loop": write_multitrack_midi(
            os.path.join(midi_dir, "full_loop.mid"), [bass, drums, chords, melody], bpm
        ),
    }
    _progress("composition: writing SUNO prompt")

    description = _build_description(style, key_str, mode, detected_chords, detected_drums)
    composition = {
        "bars":        bars,
        "bpm":         round(bpm, 2),
        "key":         key_str,
        "style":       style_label,
        "midi":        paths,
        "description": description,
    }
    _write_summary(output_dir, composition)
    suno = _stub_suno_prompt(output_dir, composition)
    return composition, suno


def _parse_key(key_string: str) -> tuple[int, str]:
    parts = key_string.strip().split()
    root_name = parts[0] if parts else "C"
    mode = "minor" if len(parts) > 1 and "min" in parts[1].lower() else "major"
    return _KEY_NOTE.get(root_name, 60), mode


def _infer_style(analysis: dict) -> str:
    """Return a human-readable style label for display."""
    user_direction = str(analysis.get("user_direction") or "").strip()
    if user_direction:
        return user_direction[:40]
    bpm = float(analysis.get("bpm") or 120.0)
    if bpm >= 150:
        return f"Fast Electronic ({round(bpm)} BPM)"
    if bpm >= 130:
        return f"Driving Electronic ({round(bpm)} BPM)"
    if bpm >= 110:
        return f"Club Electronic ({round(bpm)} BPM)"
    if bpm >= 90:
        return f"Mid-Tempo Electronic ({round(bpm)} BPM)"
    return f"Downtempo Electronic ({round(bpm)} BPM)"


def _composition_style(analysis: dict) -> str:
    """Map analysis to one of: house, synth_wave, hip_hop, techno, ambient."""
    user_dir = str(analysis.get("user_direction") or "").lower()
    genre_deep = analysis.get("genre_deep") or {}
    genre_str = (genre_deep.get("primary") or "").lower() if genre_deep.get("confidence", 0) > 0.1 else ""
    combined = f"{user_dir} {genre_str}"

    for style, keywords in _STYLE_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return style

    bpm = float(analysis.get("bpm") or 120.0)
    if bpm >= 150:
        return "techno"
    if bpm >= 130:
        return "techno"
    if bpm >= 110:
        return "house"
    if bpm >= 90:
        return "hip_hop"
    return "ambient"


def _build_description(
    style: str, key_str: str, mode: str,
    detected_chords: list, detected_drums: dict,
) -> dict:
    chord_quality = "minor seventh" if mode == "minor" else "major seventh"

    if len(detected_chords) >= 2:
        chord_desc = f"chord progression {' → '.join(detected_chords[:4])} from reference"
    elif style == "synth_wave":
        chord_desc = f"lush sustained pad chords in {key_str}"
    elif style == "techno":
        chord_desc = f"tight punchy {chord_quality} chords in {key_str}"
    elif style == "ambient":
        chord_desc = f"long swelling {chord_quality} pads in {key_str}"
    else:
        chord_desc = f"{chord_quality} stabs in {key_str}"

    if detected_drums.get("kick"):
        tempo_feel = detected_drums.get("tempo_feel", "tight")
        density = detected_drums.get("density", "medium")
        drum_desc = f"drum pattern from reference — {tempo_feel} feel, {density} density"
    elif style == "synth_wave":
        drum_desc = "sparse kick pattern with 8th-note hat groove and open hat accents"
    elif style == "hip_hop":
        drum_desc = "trap-influenced kick and snare with layered hi-hat rolls"
    elif style == "techno":
        drum_desc = "driving four-on-floor kick with dense hi-hat grid"
    elif style == "ambient":
        drum_desc = "minimal atmospheric percussion, very sparse kick"
    else:
        drum_desc = "four-on-floor kick with 16th hats, clap on 2 and 4"

    if style == "synth_wave":
        bass_desc = f"arpeggiated chord-tone bass line in {key_str}"
    elif style == "hip_hop":
        bass_desc = f"sparse 808-style sub bass in {key_str}"
    elif style == "ambient":
        bass_desc = f"sustained long-note sub bass in {key_str}"
    else:
        bass_desc = f"syncopated offbeat sub bass in {key_str}, inspired by reference groove"

    if style == "synth_wave":
        melody_desc = f"fast arpeggiated synth lead in {key_str}"
    elif style == "ambient":
        melody_desc = f"sparse atmospheric melodic phrases in {key_str}"
    else:
        melody_desc = f"sparse pentatonic motif in {key_str} with call-response variation"

    return {"bass": bass_desc, "drums": drum_desc, "chords": chord_desc, "melody": melody_desc}


def _progress(message: str) -> None:
    print(f"progress: {message}", file=sys.stderr, flush=True)


def _write_summary(output_dir: str, composition: dict) -> None:
    summary = {
        "bars":        composition["bars"],
        "bpm":         composition["bpm"],
        "key":         composition["key"],
        "style":       composition["style"],
        "midi":        {k: os.path.basename(v) for k, v in composition["midi"].items()},
        "description": composition["description"],
    }
    with open(os.path.join(output_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def _stub_suno_prompt(output_dir: str, composition: dict) -> dict:
    """Write a human-readable SUNO prompt stub."""
    style, bpm, key = composition["style"], composition["bpm"], composition["key"]
    d = composition["description"]
    text = (
        f"Create an original {style} track at {bpm} BPM in {key}. "
        f"{d['drums'].capitalize()}. {d['bass'].capitalize()}. "
        f"{d['chords'].capitalize()}. {d['melody'].capitalize()}. "
        "Instrumental, no vocals. Inspired by the reference groove and "
        "production style, not a cover and not a copy."
    )
    path = os.path.join(output_dir, "prompt.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return {"text": text, "path": os.path.abspath(path)}
