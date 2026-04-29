#!/usr/bin/env python3
"""Style-aware, randomised MIDI pattern generators for the composition engine."""
from __future__ import annotations

import random

_MINOR_PENTATONIC = [0, 3, 5, 7, 10]
_MAJOR_PENTATONIC = [0, 2, 4, 7, 9]
_KICK, _SNARE, _CLAP, _HAT_CLOSED, _HAT_OPEN = 36, 38, 39, 42, 46
_DRUM_CH = 9
_clamp_bass = lambda n: max(24, min(55, n))

# ── Kick patterns (16th-note positions 0-15 per bar) ──────────────────────────
_KICK_PATTERNS = {
    "house":      [[0, 4, 8, 12], [0, 4, 8, 12], [0, 3, 8, 12]],
    "synth_wave": [[0, 8],        [0, 6, 8],      [0, 8, 10]],
    "hip_hop":    [[0, 6, 10],    [0, 5, 8],      [0, 3, 8, 11]],
    "techno":     [[0, 4, 8, 12], [0, 4, 8, 12],  [0, 2, 4, 8, 10, 12]],
    "ambient":    [[0, 8],        [0],             []],
}
_HAT_PATTERNS = {
    "house":      [list(range(16)), list(range(16)), [0,2,4,6,8,10,12,14]],
    "synth_wave": [[0,2,4,6,8,10,12,14], [0,4,8,12], [0,2,4,6,8,10,12,14]],
    "hip_hop":    [[0,1,2,4,6,8,10,12,14], [0,2,6,10,14], [0,4,6,8,14]],
    "techno":     [list(range(16)), list(range(16)), [0,2,4,6,8,10,12,14]],
    "ambient":    [[0, 8], [0, 4, 8, 12], []],
}
_SNARE_ON_2_4 = [4, 12]
_SNARE_HH_TRAP = [4, 8, 12, 14]


def _bass_events(root: int, bpm: float, bars: int, style: str, rng: random.Random) -> list[dict]:
    bar_s = 4.0 * 60.0 / bpm
    step = bar_s / 16.0  # 1/16th note
    events: list[dict] = []

    if style == "synth_wave":
        # Smooth ascending/descending arp through root/3rd/5th
        arp = [root, root + 3, root + 7, root + 10, root + 12, root + 7, root + 3, root]
        arp = [_clamp_bass(n) for n in arp]
        vel_base = rng.randint(72, 88)
        for bar in range(bars):
            t = bar * bar_s
            pattern_offset = rng.randint(0, 2)
            for i, pos in enumerate([0, 2, 4, 6, 8, 10, 12, 14]):
                note = arp[(i + pattern_offset) % len(arp)]
                vel = max(50, min(100, vel_base + rng.randint(-6, 6)))
                events.append({"start": t + pos * step, "duration": step * 1.8, "midi_note": note, "velocity": vel})

    elif style == "hip_hop":
        # Sparse 808-style: root on beat 1, occasional accent
        vel_base = rng.randint(88, 100)
        for bar in range(bars):
            t = bar * bar_s
            positions = rng.choice([[0, 8], [0, 6, 8], [0, 8, 12], [0]])
            root_note = _clamp_bass(root)
            for pos in positions:
                vel = max(70, vel_base + rng.randint(-8, 8))
                dur = step * rng.choice([4, 6, 8])
                events.append({"start": t + pos * step, "duration": dur, "midi_note": root_note, "velocity": vel})

    elif style == "ambient":
        # Long sustained notes, very sparse
        for bar in range(0, bars, 2):
            t = bar * bar_s
            if rng.random() > 0.25:
                note = _clamp_bass(root + rng.choice([0, 7, 10]))
                vel = rng.randint(55, 75)
                events.append({"start": t, "duration": bar_s * 2 * 0.92, "midi_note": note, "velocity": vel})

    else:
        # house / techno: offbeat syncopated
        phase_notes = [root, root + 7, root + 10, root + 12]
        for bar in range(bars):
            t = bar * bar_s
            phase = bar // 8
            step8 = bar_s / 8.0
            alt = _clamp_bass(phase_notes[min(phase, 1)])
            b7  = _clamp_bass(phase_notes[min(phase, 2)])
            high = _clamp_bass(phase_notes[min(phase, 3)])
            vel_root = rng.randint(88, 98)
            pattern = rng.choice([
                [(1, step8 * 1.5, root, vel_root), (3, step8, alt if bar%2 else root, 80), (4, step8 * 1.5, b7, 88), (7, step8 * 0.8, high, 75)],
                [(0, step8 * 2, root, vel_root), (3, step8, root, 78), (5, step8 * 1.5, b7, 85), (7, step8, high, 72)],
                [(1, step8 * 1.5, root, vel_root), (4, step8 * 2, alt, 85), (7, step8, root, 75)],
            ])
            for pos, dur, note, vel in pattern:
                events.append({"start": t + pos * step8, "duration": dur, "midi_note": _clamp_bass(note), "velocity": max(60, vel + rng.randint(-5, 5))})
    return events


def _drum_events(bpm: float, bars: int, style: str, rng: random.Random, detected: dict | None = None) -> list[dict]:
    bar_s = 4.0 * 60.0 / bpm
    s16 = bar_s / 16.0
    events: list[dict] = []

    if detected and detected.get("kick") and detected.get("method") != "unavailable":
        kick_pos = detected["kick"]
        snare_pos = detected.get("snare") or _SNARE_ON_2_4
        hat_pos = detected.get("hat") or list(range(16))
    else:
        kick_pos = rng.choice(_KICK_PATTERNS.get(style, _KICK_PATTERNS["house"]))
        snare_pos = _SNARE_HH_TRAP if style == "hip_hop" else _SNARE_ON_2_4
        hat_pos = rng.choice(_HAT_PATTERNS.get(style, _HAT_PATTERNS["house"]))

    hat_vel_table = [85, 60, 75, 55, 90, 58, 70, 52, 88, 62, 72, 50, 92, 60, 68, 55]
    kick_vel = rng.randint(90, 100)
    clap_vel = rng.randint(78, 90)
    open_hat = rng.random() > 0.4

    for bar in range(bars):
        t = bar * bar_s
        for pos in kick_pos:
            events.append({"start": t + pos * s16, "duration": s16, "midi_note": _KICK,
                           "velocity": kick_vel if pos == 0 else rng.randint(82, 96), "channel": _DRUM_CH})
        for pos in snare_pos:
            events.append({"start": t + pos * s16, "duration": s16, "midi_note": _CLAP,
                           "velocity": clap_vel + rng.randint(-4, 4), "channel": _DRUM_CH})
        for pos in hat_pos:
            vel = max(40, hat_vel_table[pos % 16] + rng.randint(-10, 10))
            events.append({"start": t + pos * s16, "duration": s16 * 0.6,
                           "midi_note": _HAT_CLOSED, "velocity": vel, "channel": _DRUM_CH})
        if open_hat and style != "ambient":
            oh_positions = [6, 14] if style == "synth_wave" else [rng.choice([6, 10, 14])]
            for pos in oh_positions:
                events.append({"start": t + pos * s16, "duration": s16,
                               "midi_note": _HAT_OPEN, "velocity": rng.randint(55, 70), "channel": _DRUM_CH})
        if bar % 8 == 7 and rng.random() > 0.4:
            events.append({"start": t + bar_s * 0.9375, "duration": s16 * 0.5,
                           "midi_note": _SNARE, "velocity": rng.randint(60, 72), "channel": _DRUM_CH})
    return events


_CHORD_VOICINGS = {
    "house":      {"dur_mult": 0.45, "vel_base": 83},   # half-bar stabs
    "synth_wave": {"dur_mult": 0.92, "vel_base": 70},   # full-bar pads
    "hip_hop":    {"dur_mult": 0.35, "vel_base": 78},   # short stabs
    "techno":     {"dur_mult": 0.2,  "vel_base": 88},   # tight punchy
    "ambient":    {"dur_mult": 1.85, "vel_base": 62},   # 2-bar swells
}
_MINOR_PROGRESSIONS = [
    [[0,3,7,10], [-4,0,3,7],  [-2,2,5,9],  [-5,-2,2,5]],   # i – bVI – bVII – v
    [[0,3,7,10], [-5,-2,2,5], [-4,0,3,7],  [-2,2,5,9]],    # i – v – bVI – bVII
    [[0,3,7,10], [-2,2,5,9],  [-5,-2,2,5], [-4,0,3,7]],    # i – bVII – v – bVI
]
_MAJOR_PROGRESSIONS = [
    [[0,4,7,11], [5,9,12,16], [7,11,14,17], [5,9,12,16]],  # I – IV – V – IV
    [[0,4,7,11], [7,11,14,17],[5,9,12,16],  [0,4,7,11]],   # I – V – IV – I
]

_CHORD_NOTE_MAP: dict[str, int] = {
    "C":48,"C#":49,"Db":49,"D":50,"D#":51,"Eb":51,"E":52,
    "F":53,"F#":54,"Gb":54,"G":55,"G#":56,"Ab":56,"A":57,"A#":58,"Bb":58,"B":59,
}


def _parse_chord(name: str) -> list[int]:
    for root in sorted(_CHORD_NOTE_MAP, key=len, reverse=True):
        if name.startswith(root):
            quality = name[len(root):]
            base = _CHORD_NOTE_MAP[root]
            if "maj7" in quality or "M7" in quality:
                return [base, base+4, base+7, base+11]
            if "m7" in quality or ("m" in quality and "7" in quality):
                return [base, base+3, base+7, base+10]
            if "m" in quality or "min" in quality:
                return [base, base+3, base+7, base+10]
            if "7" in quality:
                return [base, base+4, base+7, base+10]
            return [base, base+4, base+7, base+11]
    return [48, 52, 55, 59]


def _chord_events(root: int, mode: str, bpm: float, bars: int, style: str, rng: random.Random,
                  progression: list[str] | None = None) -> list[dict]:
    bar_s = 4.0 * 60.0 / bpm
    cfg = _CHORD_VOICINGS.get(style, _CHORD_VOICINGS["house"])
    dur = bar_s * cfg["dur_mult"]
    vel_base = cfg["vel_base"]
    events: list[dict] = []

    if progression and len(progression) >= 2:
        chord_sets = [_parse_chord(c) for c in progression]
        n = len(chord_sets)
        for bar in range(bars):
            t = bar * bar_s
            notes = chord_sets[bar % n]
            vel = vel_base + rng.randint(-6, 6)
            repeat = max(1, int(bar_s / dur))
            for rep in range(repeat):
                for note in notes:
                    n_clamped = max(36, min(96, note))
                    events.append({"start": t + rep*(bar_s/repeat), "duration": dur * 0.95,
                                   "midi_note": n_clamped, "velocity": vel - rep*5})
    else:
        progs = _MINOR_PROGRESSIONS if mode == "minor" else _MAJOR_PROGRESSIONS
        chord_intervals = rng.choice(progs)
        for bar in range(bars):
            t = bar * bar_s
            ivls = chord_intervals[bar % 4]
            vel = vel_base + rng.randint(-5, 5)
            repeat = max(1, int(bar_s / dur))
            for rep in range(repeat):
                for ivl in ivls:
                    n_clamped = max(36, min(96, root + ivl))
                    events.append({"start": t + rep*(bar_s/repeat), "duration": dur * 0.95,
                                   "midi_note": n_clamped, "velocity": max(40, vel - rep*5)})
    return events


def _melody_events(root: int, mode: str, bpm: float, bars: int, style: str, rng: random.Random) -> list[dict]:
    bar_s = 4.0 * 60.0 / bpm
    beat = bar_s / 4.0
    penta = _MINOR_PENTATONIC if mode == "minor" else _MAJOR_PENTATONIC
    scale = [root + penta[i % len(penta)] for i in range(8)]

    if style == "synth_wave":
        # Fast 16th-note arp pattern
        s16 = beat / 4.0
        arp_notes = [root + p for p in penta] + [root + 12 + penta[0]]
        arp_notes = [max(48, min(96, n)) for n in arp_notes]
        events = []
        offset = rng.randint(0, len(arp_notes) - 1)
        vel_base = rng.randint(65, 80)
        for bar in range(bars):
            t = bar * bar_s
            density = rng.choice([4, 6, 8])
            positions = sorted(rng.sample(range(16), density))
            for pos in positions:
                note = arp_notes[(offset + pos) % len(arp_notes)]
                vel = max(50, vel_base + rng.randint(-8, 8))
                events.append({"start": t + pos * s16, "duration": s16 * 0.7,
                               "midi_note": note, "velocity": vel})
        return events

    if style == "ambient":
        events = []
        for bar in range(0, bars, 4):
            if rng.random() > 0.5:
                note = max(48, min(96, root + rng.choice(penta) + 12))
                events.append({"start": bar * bar_s, "duration": bar_s * 3.5,
                               "midi_note": note, "velocity": rng.randint(50, 65)})
        return events

    # Default sparse motif (house/hip-hop/techno) with variation
    motif_pool = [
        [(0.0,0,0.75,78), (1.5,2,0.5,70), (2.5,1,0.75,74), (4.0,3,0.5,66), (5.0,0,0.75,72), (7.0,4,0.5,63)],
        [(0.0,1,0.75,78), (2.0,3,0.5,70), (3.5,0,0.75,74), (5.0,2,0.5,68), (6.5,4,0.5,65)],
        [(0.5,0,0.75,76), (2.5,2,0.75,70), (4.5,1,0.5,72), (6.0,3,0.5,65), (7.5,0,0.3,60)],
    ]
    motif = rng.choice(motif_pool)
    events = []
    for bar in range(0, bars, 2):
        t = bar * bar_s
        phase = (bar // 4) % 4
        for beat_off, note_idx, dur_beats, vel in motif:
            note = scale[(note_idx + phase) % len(scale)]
            events.append({"start": t + beat_off * beat, "duration": dur_beats * beat,
                           "midi_note": max(48, min(96, note)),
                           "velocity": max(50, vel + rng.randint(-5, 5))})
    return events
