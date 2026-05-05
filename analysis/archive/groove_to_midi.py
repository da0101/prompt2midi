#!/usr/bin/env python3
"""Convert a reference groove fingerprint to MIDI events with controllable pitch variation.

The rhythm grid (kick, bass accent, hat timing) is always preserved exactly.
The variation_level knob (0-10) touches pitch only:
  0  → reproduce extracted bass note sequence as closely as possible
  5  → same scale/key, roughly half the notes changed by ±1-2 scale steps
  10 → freely walk the scale in the same key

No audio library dependency — pure Python + standard library.
"""
from __future__ import annotations

import math
import random
from typing import Sequence

# ── Note / scale tables ───────────────────────────────────────────────────────

_NOTE_PC: dict[str, int] = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
    "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8,
    "A": 9, "A#": 10, "Bb": 10, "B": 11,
}

_PC_TO_NAME = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

_SCALE_INTERVALS: dict[str, list[int]] = {
    "minor":     [0, 2, 3, 5, 7, 8, 10],
    "major":     [0, 2, 4, 5, 7, 9, 11],
    "phrygian":  [0, 1, 3, 5, 7, 8, 10],
    "dorian":    [0, 2, 3, 5, 7, 9, 10],
}

# ── GM drum MIDI note constants ───────────────────────────────────────────────

KICK        = 36
SNARE       = 38
CLAP        = 39
HAT_CLOSED  = 42
HAT_OPEN    = 46

# Default house patterns (1-bar, 16 steps) used when extraction returns nothing
_DEFAULT_KICK  = [0, 4, 8, 12]
_DEFAULT_BASS  = [1, 4, 9, 13]
_DEFAULT_HAT   = list(range(16))


# ── Public API ────────────────────────────────────────────────────────────────

def groove_to_events(
    reference_groove: dict,
    variation_level: float,   # 0–10
    key: str = "Am",
    bpm: float = 124.0,
    bars: int = 8,
    seed: int | None = None,
) -> dict:
    """Convert a reference groove fingerprint to timed MIDI events.

    Returns a dict with keys:
        bass   – list of note-event dicts (channel 0)
        drums  – list of note-event dicts (channel 9)
        groove_grid_used  – {kick, bass, hat} lists actually used
        bass_notes_used   – sorted list of note names actually placed
        bpm, key, variation_level – echoed back
    """
    rng = random.Random(seed)

    kick_grid = _normalise_grid(reference_groove.get("kick_pattern_16th"))
    bass_grid = _normalise_grid(reference_groove.get("bass_accent_pattern_16th"))
    hat_grid  = _normalise_grid(reference_groove.get("hat_pattern_16th"))

    if not kick_grid:
        kick_grid = _DEFAULT_KICK[:]
    if not bass_grid:
        bass_grid = _DEFAULT_BASS[:]
    if not hat_grid:
        hat_grid = _DEFAULT_HAT[:]

    motif_map = _parse_motif(reference_groove.get("bass_motif_16th") or [])
    bass_notes_hint = list(reference_groove.get("bass_notes") or [])

    root_pc, mode = _parse_key(key)
    scale = _SCALE_INTERVALS.get(mode, _SCALE_INTERVALS["minor"])
    root_midi_bass = _bass_root_midi(root_pc, bass_notes_hint)

    sixteenth_s  = 60.0 / bpm / 4.0
    pattern_len  = 32  # 2-bar patterns (32 sixteenth steps)
    pattern_s    = pattern_len * sixteenth_s         # one 2-bar = 32 sixteenths
    total_s      = bars * 16.0 * sixteenth_s         # one bar = 16 sixteenth notes
    repetitions  = math.ceil(bars / 2)

    bass_events: list[dict] = []
    drum_events: list[dict] = []

    for rep in range(repetitions):
        t0 = rep * pattern_s
        if t0 >= total_s:
            break
        bass_events.extend(_gen_bass_events(
            bass_grid=bass_grid,
            motif_map=motif_map,
            root_midi=root_midi_bass,
            root_pc=root_pc,
            scale=scale,
            variation=variation_level,
            sixteenth_s=sixteenth_s,
            time_offset=t0,
            rng=rng,
        ))
        drum_events.extend(_gen_drum_events(
            kick_grid=kick_grid,
            hat_grid=hat_grid,
            sixteenth_s=sixteenth_s,
            time_offset=t0,
            bpm=bpm,
        ))

    bass_events = [e for e in bass_events if e["start"] < total_s]
    drum_events = [e for e in drum_events if e["start"] < total_s]

    bass_notes_used = sorted({_PC_TO_NAME[e["midi_note"] % 12] for e in bass_events})

    return {
        "bass": bass_events,
        "drums": drum_events,
        "groove_grid_used": {
            "kick": kick_grid,
            "bass": bass_grid,
            "hat": hat_grid,
        },
        "bass_notes_used": bass_notes_used,
        "bpm": bpm,
        "key": key,
        "variation_level": variation_level,
    }


def similarity_to_variation(similarity: float) -> float:
    """Convert a 0–1 (or 0–100) similarity value to a 0–10 variation level.

    100 % similar → 0 (no change)
    80 % similar  → 4
    0 % similar   → 10
    """
    if similarity > 1.0:
        similarity /= 100.0
    similarity = max(0.0, min(1.0, similarity))
    return round((1.0 - similarity) * 10.0, 2)


# ── Grid helpers ──────────────────────────────────────────────────────────────

def _normalise_grid(raw) -> list[int]:
    """Coerce the pattern field to a list of ints in 0-31 range, or []."""
    if not raw:
        return []
    out = []
    for item in raw:
        try:
            val = int(item)
        except (TypeError, ValueError):
            continue
        if 0 <= val <= 63:
            out.append(val)
    return sorted(set(out))


# ── Key / scale helpers ───────────────────────────────────────────────────────

def _parse_key(key: str) -> tuple[int, str]:
    """Return (root_pitch_class 0-11, mode_name) from a key string.

    Handles: 'Am', 'A minor', 'Dm', 'F#m', 'C major', 'Am (Phrygian)', etc.
    """
    key = key.strip()
    mode = "minor"
    if "major" in key.lower():
        mode = "major"
    elif "phrygian" in key.lower():
        mode = "phrygian"
    elif "dorian" in key.lower():
        mode = "dorian"
    elif not key.lower().endswith("m") and not "minor" in key.lower():
        mode = "major"

    # Strip mode tokens
    for token in (" major", " minor", " phrygian", " dorian", "m"):
        stripped = key.rstrip(token)
        if stripped != key:
            key = stripped
            break

    root = key.split()[0]
    pc = _NOTE_PC.get(root)
    if pc is None:
        # Try two-char then one-char prefix
        for length in (2, 1):
            pc = _NOTE_PC.get(root[:length])
            if pc is not None:
                break
    return (pc if pc is not None else 0), mode


def _bass_root_midi(root_pc: int, bass_notes_hint: list[str]) -> int:
    """Return MIDI note for the bass root, targeting register MIDI 33-47 (A1-B2)."""
    # Prefer the most common extracted note if it resolves cleanly
    if bass_notes_hint:
        pc = _NOTE_PC.get(bass_notes_hint[0])
        if pc is not None:
            for octave in (2, 3):
                midi = 12 * octave + pc
                if 33 <= midi <= 48:
                    return midi

    # Fall back to root_pc in bass register
    for octave in (2, 3):
        midi = 12 * octave + root_pc
        if 33 <= midi <= 48:
            return midi
    return 36 + root_pc


# ── Motif parsing ─────────────────────────────────────────────────────────────

def _parse_motif(motif: list[str]) -> dict[int, int]:
    """Parse bass_motif_16th like ['0:A', '4:F', '9:A'] into {step: midi_pc}."""
    out: dict[int, int] = {}
    for entry in motif:
        try:
            step_str, note_str = entry.split(":", 1)
            step = int(step_str)
            pc = _NOTE_PC.get(note_str.strip())
            if pc is not None and 0 <= step <= 31:
                out[step] = pc
        except (ValueError, AttributeError):
            continue
    return out


# ── Bass event generation ─────────────────────────────────────────────────────

def _gen_bass_events(
    *,
    bass_grid: list[int],
    motif_map: dict[int, int],
    root_midi: int,
    root_pc: int,
    scale: list[int],
    variation: float,
    sixteenth_s: float,
    time_offset: float,
    rng: random.Random,
) -> list[dict]:
    """Generate bass note events for one 2-bar repetition."""
    events: list[dict] = []
    grid_with_sentinel = sorted(set(bass_grid)) + [32]  # sentinel for last note duration

    for idx, step in enumerate(grid_with_sentinel[:-1]):
        next_step = grid_with_sentinel[idx + 1]
        gap_steps  = next_step - step
        # Cap note duration: leave a small gap, max 2 beats
        dur_steps  = min(gap_steps - 0.1, 8.0)
        dur_steps  = max(dur_steps, 0.5)

        start_t  = time_offset + step * sixteenth_s
        dur_t    = dur_steps * sixteenth_s

        midi_note = _select_bass_note(
            step=step,
            motif_map=motif_map,
            root_midi=root_midi,
            root_pc=root_pc,
            scale=scale,
            variation=variation,
            rng=rng,
        )
        velocity = _bass_velocity(step, variation, rng)

        events.append({
            "start":     round(start_t, 6),
            "duration":  round(dur_t, 6),
            "midi_note": midi_note,
            "velocity":  velocity,
            "channel":   0,
        })

    return events


def _select_bass_note(
    step: int,
    motif_map: dict[int, int],
    root_midi: int,
    root_pc: int,
    scale: list[int],
    variation: float,
    rng: random.Random,
) -> int:
    """Pick a MIDI note for this step, blending source fidelity with variation."""
    # Get source pitch class from motif or root
    source_pc = motif_map.get(step, root_pc)

    if variation == 0:
        return _pc_to_bass_midi(source_pc, root_midi)

    # Build scale PC set to validate source
    scale_pcs = [(root_pc + interval) % 12 for interval in scale]

    # Find the scale degree index of the source note
    if source_pc in scale_pcs:
        src_deg_idx = scale_pcs.index(source_pc)
    else:
        # Snap to nearest scale degree
        src_deg_idx = min(
            range(len(scale)),
            key=lambda i: (scale_pcs[i] - source_pc) % 12,
        )

    # Probability of changing a note grows non-linearly so that:
    #   variation=1  → ~25% change probability  (90% similarity: subtle)
    #   variation=2  → ~50% change probability  (80% similarity: noticeable)
    #   variation=5  → ~90% change probability  (50% similarity: very different)
    #   variation=10 → 100%                     (0% similarity: freely walks scale)
    change_prob = min(1.0, (variation / 10.0) ** 0.55)

    if rng.random() >= change_prob:
        return _pc_to_bass_midi(source_pc, root_midi)

    # Shift distance: variation=1 → ±1 step, variation=2 → ±2, variation=5 → ±3, variation=10 → ±6
    max_shift = max(1, int(math.ceil(variation * 0.6)))
    shift = rng.randint(-max_shift, max_shift)
    if shift == 0:
        shift = rng.choice([-1, 1])

    # Wrap around: going below 0 gives b7/b6 (melodically common in minor house bass)
    new_idx = (src_deg_idx + shift) % len(scale)
    new_pc  = scale_pcs[new_idx]
    return _pc_to_bass_midi(new_pc, root_midi)


def _pc_to_bass_midi(target_pc: int, root_midi: int) -> int:
    """Find the MIDI note in bass register (MIDI 28-55) closest to root_midi with target_pc."""
    root_pc = root_midi % 12
    interval = (target_pc - root_pc) % 12
    candidate = root_midi + interval
    # Shift into bass register
    while candidate > 55:
        candidate -= 12
    while candidate < 28:
        candidate += 12
    return candidate


def _bass_velocity(step: int, variation: float, rng: random.Random) -> int:
    """Emphasise downbeats; add slight humanisation proportional to variation."""
    on_downbeat = step % 8 == 0
    base = 100 if on_downbeat else 85
    jitter = int(variation * rng.uniform(-0.8, 0.8))
    return max(60, min(120, base + jitter))


# ── Drum event generation ─────────────────────────────────────────────────────

def _gen_drum_events(
    *,
    kick_grid: list[int],
    hat_grid: list[int],
    sixteenth_s: float,
    time_offset: float,
    bpm: float,
) -> list[dict]:
    """Generate drum events for one 2-bar repetition.

    Snare/clap is always placed at steps 4, 12, 20, 28 (beats 2 and 4).
    """
    events: list[dict] = []
    snare_steps = {4, 12, 20, 28}

    for step in sorted(set(kick_grid)):
        events.append({
            "start":     round(time_offset + step * sixteenth_s, 6),
            "duration":  round(sixteenth_s * 0.9, 6),
            "midi_note": KICK,
            "velocity":  110,
            "channel":   9,
        })

    for step in snare_steps:
        events.append({
            "start":     round(time_offset + step * sixteenth_s, 6),
            "duration":  round(sixteenth_s * 0.9, 6),
            "midi_note": CLAP,
            "velocity":  90,
            "channel":   9,
        })

    for idx, step in enumerate(sorted(set(hat_grid))):
        # Every other open hat → closed; use open hat on the last step of each group
        midi = HAT_OPEN if idx % 8 == 7 else HAT_CLOSED
        events.append({
            "start":     round(time_offset + step * sixteenth_s, 6),
            "duration":  round(sixteenth_s * 0.85, 6),
            "midi_note": midi,
            "velocity":  70,
            "channel":   9,
        })

    return events
