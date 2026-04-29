#!/usr/bin/env python3
"""Deterministic composition engine: generates a new inspired loop from analysis hints.

All output is original material, not transcribed from the source audio.
"""
from __future__ import annotations

import json
import os
import sys

from midi_extraction import write_multitrack_midi, write_note_events_midi

_KEY_NOTE: dict[str, int] = {
    "C": 60, "C#": 61, "Db": 61, "D": 62, "D#": 63, "Eb": 63,
    "E": 64, "F": 65, "F#": 66, "Gb": 66, "G": 67, "G#": 68,
    "Ab": 68, "A": 69, "A#": 70, "Bb": 70, "B": 71,
}
_MINOR_PENTATONIC = [0, 3, 5, 7, 10]
_MAJOR_PENTATONIC = [0, 2, 4, 7, 9]
_KICK, _SNARE, _CLAP, _HAT_CLOSED, _HAT_OPEN = 36, 38, 39, 42, 46
_DRUM_CH = 9  # GM percussion channel (0-indexed)
_clamp_bass = lambda n: max(24, min(55, n))  # sub-bass MIDI range


def generate_inspired_loop(
    analysis: dict,
    output_dir: str,
    bars: int = 32,
) -> tuple[dict, dict]:
    """Generate a new original loop and return (composition_dict, suno_prompt_dict)."""
    bpm = float(analysis.get("bpm") or 120.0)
    root_midi, mode = _parse_key(str(analysis.get("key") or "C major"))
    key_str = str(analysis.get("key") or "C major")
    style = _infer_style(analysis)

    midi_dir = os.path.join(output_dir, "midi")
    os.makedirs(midi_dir, exist_ok=True)

    detected_chords = (analysis.get("chords") or {}).get("progression") or []
    detected_drums = analysis.get("drums") or {}

    _progress(f"composition: generating bass — {key_str} {style}")
    bass = _bass_events(root_midi - 24, bpm, bars)
    _progress("composition: generating drums")
    drums = (_drum_events_from_pattern(detected_drums, bpm, bars)
             if detected_drums.get("kick") else _drum_events(bpm, bars))
    _progress("composition: generating chords")
    chords = (_chord_events_from_progression(detected_chords, bpm, bars)
              if len(detected_chords) >= 2 else _chord_events(root_midi - 12, mode, bpm, bars))
    _progress("composition: generating melody")
    melody = _melody_events(root_midi, mode, bpm, bars)
    _progress("composition: writing MIDI files")

    paths = {
        "bass": write_note_events_midi(os.path.join(midi_dir, "bass.mid"), bass, bpm),
        "drums": write_note_events_midi(os.path.join(midi_dir, "drums.mid"), drums, bpm),
        "chords": write_note_events_midi(os.path.join(midi_dir, "chords.mid"), chords, bpm),
        "melody": write_note_events_midi(os.path.join(midi_dir, "melody.mid"), melody, bpm),
        "full_loop": write_multitrack_midi(
            os.path.join(midi_dir, "full_loop.mid"), [bass, drums, chords, melody], bpm
        ),
    }
    _progress("composition: writing SUNO prompt")

    chord_quality = "minor seventh" if mode == "minor" else "major seventh"
    chord_desc = (f"chord progression {' → '.join(detected_chords[:4])} from reference"
                  if len(detected_chords) >= 2 else f"{chord_quality} stabs in {key_str}")
    drum_feel = detected_drums.get("tempo_feel", "tight") if detected_drums.get("kick") else "tight"
    drum_density = detected_drums.get("density", "medium") if detected_drums.get("kick") else "medium"
    drum_desc = (f"drum pattern from reference — {drum_feel} feel, {drum_density} density"
                 if detected_drums.get("kick") else "four-on-floor kick with 16th hats, clap on 2 and 4")
    description = {
        "bass": f"syncopated offbeat sub bass in {key_str}, inspired by reference groove",
        "drums": drum_desc,
        "chords": chord_desc,
        "melody": f"sparse pentatonic motif in {key_str} with call-response variation",
    }
    composition = {
        "bars": bars,
        "bpm": round(bpm, 2),
        "key": key_str,
        "style": style,
        "midi": paths,
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
    """Return a style label. Uses user-provided direction if present, else neutral BPM category."""
    user_direction = str(analysis.get("user_direction") or "").strip()
    if user_direction:
        return user_direction[:40]  # truncate if very long
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


def _progress(message: str) -> None:
    print(f"progress: {message}", file=sys.stderr, flush=True)


def _bass_events(root: int, bpm: float, bars: int) -> list[dict]:
    """Syncopated offbeat house sub bass with 8-bar variation phases."""
    bar_s = 4.0 * 60.0 / bpm
    step = bar_s / 8.0  # 1/8th note
    events: list[dict] = []
    for bar in range(bars):
        t = bar * bar_s
        phase = bar // 8
        alt = root + 7 if phase >= 1 else root       # 5th at bar 8
        b7 = root + 10 if phase >= 2 else root        # b7 at bar 16
        high = root + 12 if phase >= 3 else root      # octave at bar 24
        events += [
            {"start": t + step,     "duration": step * 1.5, "midi_note": _clamp_bass(root),                    "velocity": 95},
            {"start": t + step * 3, "duration": step,       "midi_note": _clamp_bass(alt if bar % 2 else root), "velocity": 80},
            {"start": t + step * 4, "duration": step * 1.5, "midi_note": _clamp_bass(b7),                       "velocity": 88},
            {"start": t + step * 7, "duration": step * 0.8, "midi_note": _clamp_bass(high),                     "velocity": 75},
        ]
    return events


def _drum_events(bpm: float, bars: int) -> list[dict]:
    """Four-on-floor kick, 16th-note hat grid, clap 2+4, open hat offbeats."""
    bar_s = 4.0 * 60.0 / bpm
    beat = bar_s / 4.0
    s16 = beat / 4.0
    hat_vel = [85, 60, 75, 55, 90, 58, 70, 52, 88, 62, 72, 50, 92, 60, 68, 55]
    events: list[dict] = []
    for bar in range(bars):
        t = bar * bar_s
        for b in range(4):
            events.append({"start": t + b * beat, "duration": s16, "midi_note": _KICK,
                           "velocity": 100 if b == 0 else 92, "channel": _DRUM_CH})
        events.append({"start": t + beat,     "duration": s16, "midi_note": _CLAP, "velocity": 85, "channel": _DRUM_CH})
        events.append({"start": t + beat * 3, "duration": s16, "midi_note": _CLAP, "velocity": 82, "channel": _DRUM_CH})
        for s in range(16):
            events.append({"start": t + s * s16, "duration": s16 * 0.6,
                           "midi_note": _HAT_CLOSED, "velocity": hat_vel[s], "channel": _DRUM_CH})
        events.append({"start": t + beat * 1.5, "duration": s16, "midi_note": _HAT_OPEN, "velocity": 65, "channel": _DRUM_CH})
        events.append({"start": t + beat * 3.5, "duration": s16, "midi_note": _HAT_OPEN, "velocity": 60, "channel": _DRUM_CH})
        if bar % 8 == 7:
            events.append({"start": t + beat * 3.75, "duration": s16 * 0.5,
                           "midi_note": _SNARE, "velocity": 65, "channel": _DRUM_CH})
    return events


def _chord_events(root: int, mode: str, bpm: float, bars: int) -> list[dict]:
    """Diatonic 7th stabs, 4-bar progression repeating for the full loop."""
    bar_s = 4.0 * 60.0 / bpm
    half = bar_s / 2.0
    if mode == "minor":
        # im7 — bVImaj7 — bVIImaj7 — vm7
        chord_intervals = [
            [0, 3, 7, 10],    # im7
            [-4, 0, 3, 7],    # bVImaj7
            [-2, 2, 5, 9],    # bVIImaj7
            [-5, -2, 2, 5],   # vm7
        ]
    else:
        # Imaj7 — IVmaj7 — Vmaj7 — IVmaj7
        chord_intervals = [
            [0, 4, 7, 11],
            [5, 9, 12, 16],
            [7, 11, 14, 17],
            [5, 9, 12, 16],
        ]
    events: list[dict] = []
    for bar in range(bars):
        t = bar * bar_s
        ivls = chord_intervals[bar % 4]
        vel = 85 if bar % 2 == 0 else 78
        for ivl in ivls:
            n = max(36, min(96, root + ivl))
            events += [
                {"start": t,        "duration": half * 0.9, "midi_note": n, "velocity": vel},
                {"start": t + half, "duration": half * 0.9, "midi_note": n, "velocity": vel - 8},
            ]
    return events


def _melody_events(root: int, mode: str, bpm: float, bars: int) -> list[dict]:
    """Sparse pentatonic motif, 2-bar repeating with 4-bar variation."""
    bar_s = 4.0 * 60.0 / bpm
    beat = bar_s / 4.0
    penta = _MINOR_PENTATONIC if mode == "minor" else _MAJOR_PENTATONIC
    scale = [root + penta[i % len(penta)] for i in range(8)]
    # (beat_offset, scale_idx, dur_beats, velocity)
    motif = [
        (0.0, 0, 0.75, 80), (1.5, 2, 0.5, 72), (2.5, 1, 0.75, 76),
        (4.0, 3, 0.5, 68),  (5.0, 0, 0.75, 74), (7.0, 4, 0.5, 65),
    ]
    events: list[dict] = []
    for bar in range(0, bars, 2):
        t = bar * bar_s
        phase = (bar // 4) % 4
        for beat_off, note_idx, dur_beats, vel in motif:
            note = scale[(note_idx + phase) % len(scale)]
            events.append({
                "start": t + beat_off * beat,
                "duration": dur_beats * beat,
                "midi_note": max(48, min(96, note)),
                "velocity": vel,
            })
    return events


_CHORD_ROOT: dict[str, int] = {
    "C": 48, "C#": 49, "Db": 49, "D": 50, "D#": 51, "Eb": 51,
    "E": 52, "F": 53, "F#": 54, "Gb": 54, "G": 55, "G#": 56,
    "Ab": 56, "A": 57, "A#": 58, "Bb": 58, "B": 59,
}


def _parse_chord(name: str) -> list[int]:
    """Return MIDI note offsets from root for a chord name like 'Am7', 'F', 'C#m'."""
    for root in sorted(_CHORD_ROOT, key=len, reverse=True):
        if name.startswith(root):
            quality = name[len(root):]
            base = _CHORD_ROOT[root]
            if "maj7" in quality or "M7" in quality:
                return [base, base + 4, base + 7, base + 11]
            if "m7" in quality or ("m" in quality and "7" in quality):
                return [base, base + 3, base + 7, base + 10]
            if "m" in quality or "min" in quality:
                return [base, base + 3, base + 7, base + 10]
            if "7" in quality:
                return [base, base + 4, base + 7, base + 10]
            if "sus4" in quality:
                return [base, base + 5, base + 7]
            if "sus2" in quality:
                return [base, base + 2, base + 7]
            # default: major 7th voicing
            return [base, base + 4, base + 7, base + 11]
    return [48, 52, 55, 59]  # C major 7th fallback


def _chord_events_from_progression(progression: list[str], bpm: float, bars: int) -> list[dict]:
    """Build chord stabs from detected chord progression (e.g. ['Am', 'F', 'C', 'G'])."""
    bar_s = 4.0 * 60.0 / bpm
    half = bar_s / 2.0
    events: list[dict] = []
    n = len(progression)
    for bar in range(bars):
        chord_name = progression[bar % n]
        notes = _parse_chord(chord_name)
        vel = 85 if bar % 2 == 0 else 78
        for note in notes:
            n_clamped = max(36, min(96, note))
            events += [
                {"start": bar * bar_s,        "duration": half * 0.9, "midi_note": n_clamped, "velocity": vel},
                {"start": bar * bar_s + half,  "duration": half * 0.9, "midi_note": n_clamped, "velocity": vel - 8},
            ]
    return events


def _drum_events_from_pattern(detected: dict, bpm: float, bars: int) -> list[dict]:
    """Build drum MIDI from detected kick/snare/hat 16th-note grid positions."""
    bar_s = 4.0 * 60.0 / bpm
    s16 = bar_s / 16.0
    kick_pos = detected.get("kick") or []
    snare_pos = detected.get("snare") or []
    hat_pos = detected.get("hat") or []
    hat_vel = [85, 60, 75, 55, 90, 58, 70, 52, 88, 62, 72, 50, 92, 60, 68, 55]
    events: list[dict] = []
    for bar in range(bars):
        t = bar * bar_s
        for pos in kick_pos:
            events.append({"start": t + pos * s16, "duration": s16, "midi_note": _KICK, "velocity": 100, "channel": _DRUM_CH})
        for pos in snare_pos:
            events.append({"start": t + pos * s16, "duration": s16, "midi_note": _CLAP, "velocity": 85, "channel": _DRUM_CH})
        for pos in hat_pos:
            vel = hat_vel[pos % len(hat_vel)]
            events.append({"start": t + pos * s16, "duration": s16 * 0.6, "midi_note": _HAT_CLOSED, "velocity": vel, "channel": _DRUM_CH})
        if bar % 8 == 7:
            events.append({"start": t + bar_s * 0.9375, "duration": s16 * 0.5, "midi_note": _SNARE, "velocity": 65, "channel": _DRUM_CH})
    return events


def _write_summary(output_dir: str, composition: dict) -> None:
    summary = {
        "bars": composition["bars"],
        "bpm": composition["bpm"],
        "key": composition["key"],
        "style": composition["style"],
        "midi": {k: os.path.basename(v) for k, v in composition["midi"].items()},
        "description": composition["description"],
    }
    with open(os.path.join(output_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def _stub_suno_prompt(output_dir: str, composition: dict) -> dict:
    """Write a human-readable SUNO prompt stub. Phase 4 will replace with Gemini."""
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
