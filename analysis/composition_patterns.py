#!/usr/bin/env python3
"""Style-aware, randomised MIDI pattern generators for the composition engine."""
from __future__ import annotations

import random

_MINOR_PENTATONIC = [0, 3, 5, 7, 10]
_MAJOR_PENTATONIC = [0, 2, 4, 7, 9]
_KICK, _SNARE, _CLAP, _HAT_CLOSED, _HAT_OPEN = 36, 38, 39, 42, 46
_DRUM_CH = 9
_clamp_bass = lambda n: max(24, min(60, n))

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

# ── House/techno bass grooves ─────────────────────────────────────────────────
# Each entry: list of (16th_pos, dur_16ths, semitone_from_chord_root, vel_adjust)
# These are real musical grooves, not random notes.
_HOUSE_GROOVES = [
    # Funky upbeat pump — classic house
    [(2, 3, 0, 0), (6, 2, 7, -6), (9, 3, 0, -4), (13, 2, 10, -8)],
    # Offbeat syncopated walk
    [(1, 3, 0, 0), (5, 3, 5, -5), (9, 3, 7, -4), (13, 3, 0, -8)],
    # Downbeat anchor + upbeat accent
    [(0, 2, 0, 0), (4, 3, 7, -5), (8, 2, 0, -3), (11, 3, 10, -7), (15, 1, 12, -10)],
    # Walking bass (4-on-floor feel with movement)
    [(0, 3, 0, 0), (3, 2, 3, -4), (6, 2, 5, -6), (9, 2, 7, -4), (12, 2, 10, -6), (15, 1, 0, -10)],
    # Deep two-note sustain
    [(1, 7, 0, 0), (9, 6, 7, -5)],
    # Driving eighth pattern
    [(0, 2, 0, 2), (2, 2, 0, -4), (4, 2, 7, -2), (6, 2, 5, -6),
     (8, 2, 0, 2), (10, 2, 5, -4), (12, 2, 7, -2), (14, 2, 0, -6)],
]
_TECHNO_GROOVES = [
    # Tight four-on-floor bass hits
    [(0, 2, 0, 0), (4, 2, 0, -4), (8, 2, 0, -3), (12, 2, 0, -5)],
    # Industrial riff: root + b7
    [(0, 3, 0, 0), (4, 2, 10, -5), (8, 3, 0, -3), (12, 2, 10, -6)],
    # Driving 8th roots
    [(0, 2, 0, 0), (2, 2, 0, -6), (4, 2, 0, -3), (6, 2, 0, -7),
     (8, 2, 0, -2), (10, 2, 0, -6), (12, 2, 0, -3), (14, 2, 0, -7)],
    # Root + octave drive
    [(1, 3, 0, 0), (5, 2, 12, -4), (9, 3, 0, -3), (13, 2, 12, -6)],
]

# ── Chord note map (base register — will be shifted to mid-range) ─────────────
_CHORD_NOTE_MAP: dict[str, int] = {
    "C": 48, "C#": 49, "Db": 49, "D": 50, "D#": 51, "Eb": 51, "E": 52,
    "F": 53, "F#": 54, "Gb": 54, "G": 55, "G#": 56, "Ab": 56,
    "A": 57, "A#": 58, "Bb": 58, "B": 59,
}


def _chord_notes(name: str, key_root_pc: int | None = None, mode: str = "major") -> list[int]:
    """Parse a chord name to MIDI notes in mid-range (MIDI 60-84).

    When no quality is specified in the name, infers major/minor from key context.
    """
    for root_name in sorted(_CHORD_NOTE_MAP, key=len, reverse=True):
        if name.startswith(root_name):
            quality = name[len(root_name):]
            base = _CHORD_NOTE_MAP[root_name]
            base_pc = base % 12

            if "maj7" in quality or "M7" in quality:
                raw = [base, base + 4, base + 7, base + 11]
            elif "m7" in quality or ("m" in quality and "7" in quality):
                raw = [base, base + 3, base + 7, base + 10]
            elif "m" in quality or "min" in quality:
                raw = [base, base + 3, base + 7]
            elif "7" in quality:
                raw = [base, base + 4, base + 7, base + 10]
            elif "sus4" in quality:
                raw = [base, base + 5, base + 7]
            elif "sus2" in quality:
                raw = [base, base + 2, base + 7]
            elif quality:
                raw = [base, base + 4, base + 7]
            else:
                # No explicit quality — infer from key
                if key_root_pc is not None:
                    intervals = [0, 2, 3, 5, 7, 8, 10] if mode == "minor" else [0, 2, 4, 5, 7, 9, 11]
                    scale = frozenset((key_root_pc + i) % 12 for i in intervals)
                    M3 = (base_pc + 4) % 12
                    m3 = (base_pc + 3) % 12
                    if M3 in scale and m3 not in scale:
                        raw = [base, base + 4, base + 7]  # major triad
                    else:
                        raw = [base, base + 3, base + 7]  # minor triad
                else:
                    raw = [base, base + 4, base + 7] if mode == "major" else [base, base + 3, base + 7]

            # Shift into mid-range (MIDI 60-84) so chords sit above the bass
            while raw[0] < 60:
                raw = [n + 12 for n in raw]
            while raw[0] > 72:
                raw = [n - 12 for n in raw]
            return raw

    return [60, 64, 67]  # C major triad fallback


def _bass_events(
    root: int, bpm: float, bars: int, style: str, rng: random.Random,
    progression: list[str] | None = None,
) -> list[dict]:
    bar_s = 4.0 * 60.0 / bpm
    step = bar_s / 16.0
    s16 = step
    events: list[dict] = []

    # Compute bar-by-bar chord roots for chord-following bass.
    # Look up directly in _CHORD_NOTE_MAP and subtract one octave to land in bass range.
    def _bass_root(name: str) -> int:
        for rn in sorted(_CHORD_NOTE_MAP, key=len, reverse=True):
            if name.startswith(rn):
                return _clamp_bass(_CHORD_NOTE_MAP[rn] - 12)  # e.g. Bb3(58)-12 = Bb2(46)
        return _clamp_bass(root)

    if progression and len(progression) >= 2:
        chord_roots = [_bass_root(progression[i % len(progression)]) for i in range(bars)]
    else:
        chord_roots = [_clamp_bass(root)] * bars

    if style == "synth_wave":
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
                events.append({"start": t + pos * s16, "duration": s16 * 1.8, "midi_note": note, "velocity": vel})

    elif style == "hip_hop":
        vel_base = rng.randint(88, 100)
        for bar in range(bars):
            t = bar * bar_s
            bar_root = chord_roots[bar]
            positions = rng.choice([[0, 8], [0, 6, 8], [0, 8, 12], [0]])
            # Accent note: chord root or 5th above
            accent = _clamp_bass(bar_root + rng.choice([0, 7, 10]))
            for i, pos in enumerate(positions):
                note = bar_root if i == 0 else accent
                vel = max(70, vel_base + rng.randint(-8, 8))
                dur = s16 * rng.choice([4, 6, 8])
                events.append({"start": t + pos * s16, "duration": dur, "midi_note": note, "velocity": vel})

    elif style == "ambient":
        for bar in range(0, bars, 2):
            t = bar * bar_s
            if rng.random() > 0.25:
                note = _clamp_bass(chord_roots[bar] + rng.choice([0, 7]))
                vel = rng.randint(55, 75)
                events.append({"start": t, "duration": bar_s * 2 * 0.92, "midi_note": note, "velocity": vel})

    else:
        # house / techno: pre-composed grooves, chord-following
        groove_pool = _TECHNO_GROOVES if style == "techno" else _HOUSE_GROOVES
        groove = rng.choice(groove_pool)
        vel_base = rng.randint(88, 98)

        for bar in range(bars):
            # Pick a new groove every 4 bars for structural variety
            if bar % 4 == 0 and bar > 0:
                groove = rng.choice(groove_pool)
            t = bar * bar_s
            bar_root = chord_roots[bar]

            for pos, dur_16, ivl, vel_adj in groove:
                note = _clamp_bass(bar_root + ivl)
                vel = max(55, vel_base + vel_adj + rng.randint(-4, 4))
                events.append({
                    "start": t + pos * s16,
                    "duration": dur_16 * s16 * 0.88,
                    "midi_note": note,
                    "velocity": vel,
                })

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
    "house":      {"dur_mult": 0.45, "vel_base": 78},
    "synth_wave": {"dur_mult": 0.92, "vel_base": 65},
    "hip_hop":    {"dur_mult": 0.35, "vel_base": 73},
    "techno":     {"dur_mult": 0.2,  "vel_base": 82},
    "ambient":    {"dur_mult": 1.85, "vel_base": 58},
}
_MINOR_PROGRESSIONS = [
    [[0, 3, 7], [-4, 0, 3],  [-2, 2, 5],  [-5, -2, 2]],   # i – bVI – bVII – v
    [[0, 3, 7], [-5, -2, 2], [-4, 0, 3],  [-2, 2, 5]],    # i – v – bVI – bVII
    [[0, 3, 7], [-2, 2, 5],  [-5, -2, 2], [-4, 0, 3]],    # i – bVII – v – bVI
]
_MAJOR_PROGRESSIONS = [
    [[0, 4, 7], [5, 9, 12], [7, 11, 14], [5, 9, 12]],     # I – IV – V – IV
    [[0, 4, 7], [7, 11, 14], [5, 9, 12], [0, 4, 7]],      # I – V – IV – I
]


def _chord_events(
    root: int, mode: str, bpm: float, bars: int, style: str, rng: random.Random,
    progression: list[str] | None = None,
) -> list[dict]:
    bar_s = 4.0 * 60.0 / bpm
    cfg = _CHORD_VOICINGS.get(style, _CHORD_VOICINGS["house"])
    dur = bar_s * cfg["dur_mult"]
    vel_base = cfg["vel_base"]
    events: list[dict] = []
    key_root_pc = root % 12  # pitch class of the key root

    if progression and len(progression) >= 2:
        # Parse with key-aware quality so Bb in F minor → Bbm, not BbM7
        chord_sets = [_chord_notes(c, key_root_pc, mode) for c in progression]
        n = len(chord_sets)
        # House-appropriate rhythm options only (no "offbeat" which sounds like reggae)
        rhythm_options = ["half_bar", "half_bar", "downbeat_only", "syncopated"]
        section_rhythm = rng.choice(rhythm_options)
        for bar in range(bars):
            if bar % 8 == 0 and bar > 0:
                section_rhythm = rng.choice(rhythm_options)
            t = bar * bar_s
            notes = chord_sets[bar % n]
            vel = vel_base + rng.randint(-5, 5)
            if section_rhythm == "downbeat_only":
                offsets = [0.0]
            elif section_rhythm == "syncopated":
                # Stab just before beat 1 and beat 3 (classic house syncopation)
                offsets = [bar_s * 0.875, bar_s * 0.375] if bar % 2 == 0 else [0.0, bar_s * 0.5]
            else:  # half_bar — 2 stabs per bar on beats 1 and 3
                offsets = [0.0, bar_s * 0.5]
            for i, off in enumerate(offsets):
                for note in notes:
                    events.append({
                        "start": t + off,
                        "duration": dur * 0.88,
                        "midi_note": max(48, min(96, note)),
                        "velocity": max(40, vel - i * 3),
                    })
    else:
        progs = _MINOR_PROGRESSIONS if mode == "minor" else _MAJOR_PROGRESSIONS
        chord_intervals = rng.choice(progs)
        # Shift root up to mid-range for chords
        chord_root = root + 12 if root < 53 else root
        for bar in range(bars):
            t = bar * bar_s
            ivls = chord_intervals[bar % 4]
            vel = vel_base + rng.randint(-5, 5)
            repeat = max(1, int(bar_s / dur))
            for rep in range(repeat):
                for ivl in ivls:
                    n_clamped = max(48, min(84, chord_root + ivl))
                    events.append({"start": t + rep * (bar_s / repeat), "duration": dur * 0.92,
                                   "midi_note": n_clamped, "velocity": max(40, vel - rep * 4)})
    return events


def _melody_events(root: int, mode: str, bpm: float, bars: int, style: str, rng: random.Random) -> list[dict]:
    bar_s = 4.0 * 60.0 / bpm
    beat = bar_s / 4.0
    penta = _MINOR_PENTATONIC if mode == "minor" else _MAJOR_PENTATONIC
    scale = [root + penta[i % len(penta)] for i in range(8)]

    if style == "synth_wave":
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

    # Three motifs: sparse call-response, mid-density, dense staccato
    motif_pool = [
        [(0.0, 0, 0.75, 78), (1.5, 2, 0.5, 70), (2.5, 1, 0.75, 74),
         (4.0, 3, 0.5, 66), (5.0, 0, 0.75, 72), (7.0, 4, 0.5, 63)],
        [(0.0, 1, 0.75, 78), (2.0, 3, 0.5, 70), (3.5, 0, 0.75, 74),
         (5.0, 2, 0.5, 68), (6.5, 4, 0.5, 65)],
        [(0.5, 0, 0.4, 76), (1.5, 2, 0.4, 70), (2.5, 1, 0.4, 74), (3.5, 3, 0.4, 68),
         (4.5, 4, 0.4, 72), (5.5, 0, 0.4, 65), (6.5, 2, 0.4, 62), (7.5, 1, 0.3, 58)],
    ]
    events = []
    motif = rng.choice(motif_pool)
    for bar in range(0, bars, 2):
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
