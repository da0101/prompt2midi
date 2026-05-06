#!/usr/bin/env python3
"""Tests for groove_to_midi transformation logic.

Run with:
    cd analysis && python3 -m pytest test_groove_transform.py -v
    # or
    cd analysis && python3 test_groove_transform.py
"""
from __future__ import annotations

import os
import unittest

from analysis.archive.groove_to_midi import (
    _parse_key,
    _parse_motif,
    _pc_to_bass_midi,
    groove_to_events,
    similarity_to_variation,
)


# ── Helper fixtures ────────────────────────────────────────────────────────────

CALLAO_LIKE_GROOVE = {
    "kick_pattern_16th":        [0, 4, 8, 12, 16, 20, 24, 28],
    "bass_accent_pattern_16th": [1, 4, 9, 13, 17, 20, 25, 29],
    "hat_pattern_16th":         list(range(0, 32, 2)),   # 8th-note hats
    "bass_motif_16th":          ["1:A", "4:F", "9:A", "13:C", "17:A", "20:E", "25:A", "29:F"],
    "bass_notes":               ["A", "F", "C", "E"],
    "swing":                    0.02,
    "low_end_weight":           "heavy",
    "drum_feel":                "straight four-on-floor foundation",
    "bass_feel":                "syncopated bassline answering the kick",
    "club_energy":              "club",
}


# ── similarity_to_variation ────────────────────────────────────────────────────

class TestSimilarityToVariation(unittest.TestCase):

    def test_100_percent_is_zero_variation(self):
        self.assertEqual(similarity_to_variation(100), 0.0)

    def test_100_fraction_is_zero_variation(self):
        self.assertEqual(similarity_to_variation(1.0), 0.0)

    def test_90_percent_is_1_variation(self):
        self.assertEqual(similarity_to_variation(90), 1.0)

    def test_80_percent_is_2_variation(self):
        self.assertEqual(similarity_to_variation(80), 2.0)

    def test_50_percent_is_5_variation(self):
        self.assertEqual(similarity_to_variation(50), 5.0)

    def test_0_percent_is_10_variation(self):
        self.assertEqual(similarity_to_variation(0), 10.0)

    def test_monotonically_decreasing(self):
        values = [similarity_to_variation(s) for s in [100, 90, 80, 70, 60, 50, 0]]
        for a, b in zip(values, values[1:]):
            self.assertLessEqual(a, b)

    def test_clamped_above_100(self):
        self.assertEqual(similarity_to_variation(120), 0.0)

    def test_clamped_below_0(self):
        self.assertEqual(similarity_to_variation(-5), 10.0)


# ── _parse_key ─────────────────────────────────────────────────────────────────

class TestParseKey(unittest.TestCase):

    def test_am_short(self):
        pc, mode = _parse_key("Am")
        self.assertEqual(pc, 9)
        self.assertIn(mode, ("minor",))

    def test_dm_short(self):
        pc, mode = _parse_key("Dm")
        self.assertEqual(pc, 2)

    def test_a_minor_long(self):
        pc, mode = _parse_key("A minor")
        self.assertEqual(pc, 9)
        self.assertEqual(mode, "minor")

    def test_c_major(self):
        pc, mode = _parse_key("C major")
        self.assertEqual(pc, 0)
        self.assertEqual(mode, "major")

    def test_fsharp_minor(self):
        pc, mode = _parse_key("F#m")
        self.assertEqual(pc, 6)


# ── _parse_motif ──────────────────────────────────────────────────────────────

class TestParseMotif(unittest.TestCase):

    def test_standard_motif(self):
        motif = ["0:A", "4:F", "9:C"]
        result = _parse_motif(motif)
        self.assertEqual(result[0], 9)   # A = pc 9
        self.assertEqual(result[4], 5)   # F = pc 5
        self.assertEqual(result[9], 0)   # C = pc 0

    def test_empty_motif(self):
        self.assertEqual(_parse_motif([]), {})

    def test_ignores_bad_entries(self):
        result = _parse_motif(["bad", "0:A", "garbage:Z"])
        self.assertIn(0, result)
        self.assertEqual(len(result), 1)


# ── Rhythm grid preservation ──────────────────────────────────────────────────

class TestRhythmGridPreservation(unittest.TestCase):

    def _extract_bass_steps(self, events, sixteenth_s):
        """Extract 16th-grid positions from bass event start times."""
        steps = set()
        for e in events:
            step = round(e["start"] / sixteenth_s) % 32
            steps.add(step)
        return steps

    def test_bass_rhythm_matches_reference_at_variation_0(self):
        """At variation=0 the bass onset steps must match the reference grid exactly."""
        events = groove_to_events(CALLAO_LIKE_GROOVE, variation_level=0, key="Am", bpm=124, bars=2, seed=0)
        sixteenth_s = 60.0 / 124 / 4.0
        used_steps = self._extract_bass_steps(events["bass"], sixteenth_s)
        ref_steps = set(CALLAO_LIKE_GROOVE["bass_accent_pattern_16th"])
        self.assertEqual(used_steps, ref_steps,
                         f"Rhythm mismatch: got {sorted(used_steps)}, expected {sorted(ref_steps)}")

    def test_bass_rhythm_matches_reference_at_variation_5(self):
        """Pitch varies but onset timing must be identical at any variation level."""
        for variation in (0, 2, 5, 8, 10):
            with self.subTest(variation=variation):
                events = groove_to_events(
                    CALLAO_LIKE_GROOVE, variation_level=variation, key="Am", bpm=124, bars=2, seed=42
                )
                sixteenth_s = 60.0 / 124 / 4.0
                used_steps = self._extract_bass_steps(events["bass"], sixteenth_s)
                ref_steps = set(CALLAO_LIKE_GROOVE["bass_accent_pattern_16th"])
                self.assertEqual(used_steps, ref_steps,
                                 f"variation={variation}: rhythm drifted")

    def test_kick_rhythm_matches_reference(self):
        """Kick positions in drum events must always match the reference kick grid."""
        events = groove_to_events(CALLAO_LIKE_GROOVE, variation_level=7, key="Am", bpm=124, bars=2, seed=0)
        from analysis.archive.groove_to_midi import KICK
        sixteenth_s = 60.0 / 124 / 4.0
        kick_steps = set()
        for e in events["drums"]:
            if e["midi_note"] == KICK:
                step = round(e["start"] / sixteenth_s) % 32
                kick_steps.add(step)
        ref_kick = set(CALLAO_LIKE_GROOVE["kick_pattern_16th"])
        self.assertEqual(kick_steps, ref_kick)


# ── Pitch variation distance ──────────────────────────────────────────────────

class TestPitchVariationDistance(unittest.TestCase):

    def _pitch_set(self, events):
        return {e["midi_note"] for e in events["bass"]}

    def _hamming_distance(self, a, b):
        """Fraction of distinct notes between two pitch sets."""
        if not a and not b:
            return 0.0
        return len(a.symmetric_difference(b)) / len(a.union(b))

    def test_variation_0_uses_extracted_notes(self):
        """At variation=0 all notes must be from the extracted motif scale."""
        events = groove_to_events(CALLAO_LIKE_GROOVE, variation_level=0, key="Am", bpm=2, seed=0)
        from analysis.archive.groove_to_midi import _NOTE_PC
        ref_pcs = {_NOTE_PC.get(n) for n in CALLAO_LIKE_GROOVE["bass_notes"] if n in _NOTE_PC}
        used_pcs = {e["midi_note"] % 12 for e in events["bass"]}
        # All used pitch classes should be in the reference set (or very close)
        self.assertTrue(used_pcs.issubset(ref_pcs | {(pc + 2) % 12 for pc in ref_pcs} | {(pc - 2) % 12 for pc in ref_pcs}),
                        f"variation=0 used unexpected notes: {used_pcs - ref_pcs}")

    def test_pitch_distance_increases_with_variation(self):
        """Higher variation levels must produce progressively more pitch change."""
        baseline = groove_to_events(CALLAO_LIKE_GROOVE, variation_level=0, key="Am", bpm=124, bars=4, seed=7)
        distances = []
        for level in (0, 2, 5, 10):
            ev = groove_to_events(CALLAO_LIKE_GROOVE, variation_level=level, key="Am", bpm=124, bars=4, seed=7)
            d = self._hamming_distance(self._pitch_set(baseline), self._pitch_set(ev))
            distances.append((level, d))

        # Variation 10 must be more different from baseline than variation 0
        d_at_0 = distances[0][1]
        d_at_10 = distances[-1][1]
        self.assertGreater(d_at_10, d_at_0,
                           f"variation=10 not further than variation=0: {distances}")

    def test_variation_5_notes_stay_in_key(self):
        """At variation=5 all bass notes must remain in Am scale."""
        from analysis.archive.groove_to_midi import _SCALE_INTERVALS, _NOTE_PC
        events = groove_to_events(CALLAO_LIKE_GROOVE, variation_level=5, key="Am", bpm=124, bars=4, seed=1)
        root_pc = _NOTE_PC["A"]  # 9
        scale = _SCALE_INTERVALS["minor"]
        scale_pcs = {(root_pc + interval) % 12 for interval in scale}
        used_pcs = {e["midi_note"] % 12 for e in events["bass"]}
        off_key = used_pcs - scale_pcs
        self.assertEqual(off_key, set(), f"Notes outside Am scale: {off_key}")

    def test_bass_register_always_in_range(self):
        """Bass MIDI notes must stay within MIDI 24-60 (reasonable bass register)."""
        for variation in (0, 5, 10):
            with self.subTest(variation=variation):
                events = groove_to_events(
                    CALLAO_LIKE_GROOVE, variation_level=variation, key="Am", bpm=124, bars=2, seed=0
                )
                for e in events["bass"]:
                    self.assertGreaterEqual(e["midi_note"], 24, f"Note too low: {e}")
                    self.assertLessEqual(e["midi_note"], 60, f"Note too high: {e}")


# ── Output structure ──────────────────────────────────────────────────────────

class TestOutputStructure(unittest.TestCase):

    def setUp(self):
        self.events = groove_to_events(CALLAO_LIKE_GROOVE, variation_level=3, key="Am", bpm=124, bars=4)

    def test_has_bass_and_drums(self):
        self.assertIn("bass", self.events)
        self.assertIn("drums", self.events)

    def test_bass_events_have_required_keys(self):
        for e in self.events["bass"]:
            for key in ("start", "duration", "midi_note", "velocity", "channel"):
                self.assertIn(key, e, f"Missing key {key} in bass event {e}")

    def test_drum_events_on_channel_9(self):
        for e in self.events["drums"]:
            self.assertEqual(e["channel"], 9)

    def test_bass_events_on_channel_0(self):
        for e in self.events["bass"]:
            self.assertEqual(e["channel"], 0)

    def test_returns_groove_grid_used(self):
        self.assertIn("groove_grid_used", self.events)
        grid = self.events["groove_grid_used"]
        for key in ("kick", "bass", "hat"):
            self.assertIn(key, grid)

    def test_bars_duration_approximately_correct(self):
        """Events for 4 bars at 124 BPM should span ~7.74 seconds."""
        bars = 4
        bpm  = 124.0
        expected_s = bars * 4 * 60.0 / bpm
        events = groove_to_events(CALLAO_LIKE_GROOVE, 3, "Am", bpm=bpm, bars=bars)
        max_start = max(e["start"] for e in events["bass"])
        self.assertLess(max_start, expected_s + 0.5)
        self.assertGreater(max_start, expected_s * 0.6)

    def test_empty_groove_falls_back_to_defaults(self):
        """Empty groove dict should still produce valid events using built-in defaults."""
        events = groove_to_events({}, variation_level=5, key="Am", bpm=120, bars=2)
        self.assertGreater(len(events["bass"]), 0)
        self.assertGreater(len(events["drums"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
