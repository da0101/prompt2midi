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
    "house":      [[0, 4, 8, 12], [0, 3, 8, 11], [0, 4, 8, 10, 12]],
    "synth_wave": [[0, 8],        [0, 6, 8],      [0, 8, 10]],
    "hip_hop":    [[0, 6, 10],    [0, 5, 8],      [0, 3, 8, 11]],
    "techno":     [[0, 4, 8, 12], [0, 2, 4, 8, 10, 12], [0, 4, 6, 8, 12, 14]],
    "ambient":    [[0, 8],        [0],             []],
}
_HAT_PATTERNS = {
    "house":      [list(range(16)), [0,2,4,6,8,10,12,14], [0,1,2,4,6,8,9,10,12,14]],
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

    # Scale tones available to every style (minor pentatonic + b7 + chromatic approach)
    scale_pool = [_clamp_bass(root + ivl) for ivl in [0, 3, 5, 7, 10, 12, -2, 15]]

    if style == "synth_wave":
        # Arp shape chosen fresh each run from 4 different shapes
        arp_shapes = [
            [0, 3, 7, 10, 12, 10, 7, 3],
            [0, 7, 10, 12, 10, 7, 3, 0],
            [0, 3, 5, 7, 10, 12, 7, 5],
            [0, 5, 7, 10, 7, 5, 3, 0],
        ]
        shape = rng.choice(arp_shapes)
        arp = [_clamp_bass(root + ivl) for ivl in shape]
        vel_base = rng.randint(72, 88)
        for bar in range(bars):
            t = bar * bar_s
            pattern_offset = rng.randint(0, len(arp) - 1)
            for i, pos in enumerate([0, 2, 4, 6, 8, 10, 12, 14]):
                note = arp[(i + pattern_offset) % len(arp)]
                vel = max(50, min(100, vel_base + rng.randint(-6, 6)))
                events.append({"start": t + pos * step, "duration": step * 1.8, "midi_note": note, "velocity": vel})

    elif style == "hip_hop":
        # 808-style: root anchors, passing notes vary each bar
        vel_base = rng.randint(88, 100)
        for bar in range(bars):
            t = bar * bar_s
            positions = rng.choice([[0, 8], [0, 6, 8], [0, 8, 12], [0]])
            # Pick a different scale tone for non-root hits each bar
            accent = rng.choice(scale_pool)
            for i, pos in enumerate(positions):
                note = _clamp_bass(root) if i == 0 else accent
                vel = max(70, vel_base + rng.randint(-8, 8))
                dur = step * rng.choice([4, 6, 8])
                events.append({"start": t + pos * step, "duration": dur, "midi_note": note, "velocity": vel})

    elif style == "ambient":
        # Long sustained notes, very sparse
        for bar in range(0, bars, 2):
            t = bar * bar_s
            if rng.random() > 0.25:
                note = _clamp_bass(root + rng.choice([0, 7, 10]))
                vel = rng.randint(55, 75)
                events.append({"start": t, "duration": bar_s * 2 * 0.92, "midi_note": note, "velocity": vel})

    else:
        # house / techno: offbeat syncopated with randomly chosen passing notes per bar
        step8 = bar_s / 8.0
        r = _clamp_bass(root)
        for bar in range(bars):
            t = bar * bar_s
            # Pick 3 scale tones randomly — different pitches every bar, every run
            n1 = rng.choice(scale_pool)
            n2 = rng.choice(scale_pool)
            n3 = rng.choice(scale_pool)
            vel_root = rng.randint(88, 98)
            pattern = rng.choice([
                [(1, step8*1.5, r,  vel_root), (3, step8,   n1, 80), (5, step8*1.5, n2, 85), (7, step8*0.8, n3, 75)],
                [(0, step8*2,   r,  vel_root), (3, step8,   n1, 78), (5, step8*1.5, n2, 82), (7, step8,     n3, 72)],
                [(1, step8*1.5, r,  vel_root), (4, step8*2, n1, 85), (7, step8,     n2, 75)],
                [(0, step8*1.5, r,  vel_root), (2, step8,   n1, 78), (4, step8*1.5, n2, 84), (6, step8,     n3, 70)],
            ])
            for pos, dur, note, vel in pattern:
                events.append({"start": t + pos*step8, "duration": dur, "midi_note": _clamp_bass(note), "velocity": max(60, vel + rng.randint(-5, 5))})
    return events


def _drum_events(bpm: float, bars: int, style: str, rng: random.Random, detected: dict | None = None) -> list[dict]:
    bar_s = 4.0 * 60.0 / bpm
    s16 = bar_s / 16.0
    events: list[dict] = []

    if detected and detected.get("kick") and detected.get("method") != "unavailable":
        fixed_kick = detected["kick"]
        fixed_snare = detected.get("snare") or _SNARE_ON_2_4
        fixed_hat = detected.get("hat") or list(range(16))
        rotate_patterns = False
    else:
        fixed_kick = None
        fixed_snare = _SNARE_HH_TRAP if style == "hip_hop" else _SNARE_ON_2_4
        fixed_hat = None
        rotate_patterns = True

    hat_vel_table = [85, 60, 75, 55, 90, 58, 70, 52, 88, 62, 72, 50, 92, 60, 68, 55]
    kick_vel = rng.randint(90, 100)
    clap_vel = rng.randint(78, 90)
    open_hat = rng.random() > 0.4

    kick_pos = fixed_kick or rng.choice(_KICK_PATTERNS.get(style, _KICK_PATTERNS["house"]))
    hat_pos = fixed_hat or rng.choice(_HAT_PATTERNS.get(style, _HAT_PATTERNS["house"]))
    snare_pos = fixed_snare

    for bar in range(bars):
        # Rotate kick/hat pattern at every 8-bar section boundary for structural variety
        if rotate_patterns and bar > 0 and bar % 8 == 0:
            kick_pos = rng.choice(_KICK_PATTERNS.get(style, _KICK_PATTERNS["house"]))
            hat_pos = rng.choice(_HAT_PATTERNS.get(style, _HAT_PATTERNS["house"]))
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
        # Pick a rhythmic feel for this section; rotate every 8 bars
        rhythm_options = ["half_bar", "quarter_bar", "downbeat_only", "offbeat"]
        section_rhythm = rng.choice(rhythm_options)
        for bar in range(bars):
            if bar % 8 == 0 and bar > 0:
                section_rhythm = rng.choice(rhythm_options)
            t = bar * bar_s
            notes = chord_sets[bar % n]
            vel = vel_base + rng.randint(-6, 6)
            if section_rhythm == "downbeat_only":
                offsets = [0.0]
            elif section_rhythm == "quarter_bar":
                offsets = [0.0, bar_s * 0.25, bar_s * 0.5, bar_s * 0.75]
            elif section_rhythm == "offbeat":
                offsets = [bar_s * 0.25, bar_s * 0.75]
            else:  # half_bar
                offsets = [0.0, bar_s * 0.5]
            for i, off in enumerate(offsets):
                for note in notes:
                    n_clamped = max(36, min(96, note))
                    events.append({"start": t + off, "duration": dur * 0.9,
                                   "midi_note": n_clamped, "velocity": max(40, vel - i * 4)})
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
    # Three motifs: sparse call-response, mid-density, dense staccato
    motif_pool = [
        [(0.0,0,0.75,78), (1.5,2,0.5,70), (2.5,1,0.75,74), (4.0,3,0.5,66), (5.0,0,0.75,72), (7.0,4,0.5,63)],
        [(0.0,1,0.75,78), (2.0,3,0.5,70), (3.5,0,0.75,74), (5.0,2,0.5,68), (6.5,4,0.5,65)],
        [(0.5,0,0.4,76), (1.5,2,0.4,70), (2.5,1,0.4,74), (3.5,3,0.4,68), (4.5,4,0.4,72), (5.5,0,0.4,65), (6.5,2,0.4,62), (7.5,1,0.3,58)],
    ]
    events = []
    motif = rng.choice(motif_pool)
    for bar in range(0, bars, 2):
        # Rotate motif every 8 bars so sections sound distinct
        if bar % 8 == 0 and bar > 0:
            motif = rng.choice(motif_pool)
        t = bar * bar_s
        phase = (bar // 4) % 4
        for beat_off, note_idx, dur_beats, vel in motif:
            note = scale[(note_idx + phase) % len(scale)]
            events.append({"start": t + beat_off * beat, "duration": dur_beats * beat,
                           "midi_note": max(48, min(96, note)),
                           "velocity": max(50, vel + rng.randint(-5, 5))})
    return events
