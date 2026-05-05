import json
import os
import tempfile
import unittest

from analysis.composition.composition import (
    _bass_events,
    _chord_events,
    _drum_events,
    _infer_style,
    _melody_events,
    _parse_key,
    generate_inspired_loop,
)
from analysis.core.enhanced_analysis import better_bpm, better_key


class ParseKeyTest(unittest.TestCase):
    def test_minor_key(self):
        midi, mode = _parse_key("D minor")
        self.assertEqual(midi, 62)
        self.assertEqual(mode, "minor")

    def test_major_key(self):
        midi, mode = _parse_key("A major")
        self.assertEqual(midi, 69)
        self.assertEqual(mode, "major")

    def test_unknown_root_falls_back_to_c(self):
        midi, mode = _parse_key("X minor")
        self.assertEqual(midi, 60)

    def test_sharp_root(self):
        midi, _ = _parse_key("F# minor")
        self.assertEqual(midi, 66)


class EnhancedAnalysisFallbackTest(unittest.TestCase):
    def test_better_bpm_returns_fallback_when_disabled(self):
        old = os.environ.get("PROMPT2MIDI_DISABLE_LIBROSA")
        os.environ["PROMPT2MIDI_DISABLE_LIBROSA"] = "1"
        try:
            result = better_bpm("unused.wav", 126.0, 0.7)
            self.assertEqual(result["bpm"], 126.0)
            self.assertEqual(result["confidence"], 0.7)
            self.assertEqual(result["method"], "autocorrelation")
        finally:
            if old is None:
                os.environ.pop("PROMPT2MIDI_DISABLE_LIBROSA", None)
            else:
                os.environ["PROMPT2MIDI_DISABLE_LIBROSA"] = old

    def test_better_key_returns_fallback_when_disabled(self):
        old = os.environ.get("PROMPT2MIDI_DISABLE_LIBROSA")
        os.environ["PROMPT2MIDI_DISABLE_LIBROSA"] = "1"
        try:
            result = better_key("unused.wav", "D minor", 0.75)
            self.assertEqual(result["key"], "D minor")
            self.assertEqual(result["confidence"], 0.75)
            self.assertEqual(result["method"], "fundamental_freq")
        finally:
            if old is None:
                os.environ.pop("PROMPT2MIDI_DISABLE_LIBROSA", None)
            else:
                os.environ["PROMPT2MIDI_DISABLE_LIBROSA"] = old


class InferStyleTest(unittest.TestCase):
    def test_club_bpm_range(self):
        style = _infer_style({"bpm": 125})
        self.assertIn("125", style)
        self.assertIn("Electronic", style)

    def test_fast_bpm_range(self):
        style = _infer_style({"bpm": 140})
        self.assertIn("Electronic", style)

    def test_user_direction_takes_priority(self):
        style = _infer_style({"bpm": 90, "user_direction": "synth wave"})
        self.assertEqual(style, "synth wave")

    def test_user_direction_overrides_bpm(self):
        style = _infer_style({"bpm": 125, "user_direction": "dark techno"})
        self.assertEqual(style, "dark techno")

    def test_long_similarity_instruction_does_not_become_style_label(self):
        style = _infer_style({
            "bpm": 133,
            "user_direction": (
                "full-track inspired version at about 50 percent similarity; "
                "use the tribal percussion preset; instrumental club track"
            ),
        })
        self.assertEqual(style, "Driving Electronic (133 BPM)")


class BassEventsTest(unittest.TestCase):
    def test_bass_stays_in_sub_range(self):
        # Test multiple roots including the highest (B = root_midi 71, bass root 47)
        for root in (38, 43, 47):
            with self.subTest(root=root):
                events = _bass_events(root=root, bpm=126, bars=32)
                for event in events:
                    self.assertGreaterEqual(event["midi_note"], 24)
                    self.assertLessEqual(event["midi_note"], 55)

    def test_bass_root_note_present(self):
        events = _bass_events(root=38, bpm=126, bars=4)
        notes = {e["midi_note"] for e in events}
        self.assertIn(38, notes)

    def test_bass_covers_32_bars(self):
        bpm = 126
        events = _bass_events(root=38, bpm=bpm, bars=32)
        bar_s = 4.0 * 60.0 / bpm
        max_start = max(e["start"] for e in events)
        self.assertGreaterEqual(max_start, bar_s * 31)

    def test_bass_introduces_fifth_after_bar_8(self):
        events = _bass_events(root=38, bpm=120, bars=16)
        late_notes = {e["midi_note"] for e in events if e["start"] >= 8 * (4 * 60.0 / 120)}
        self.assertIn(38 + 7, late_notes)


class DrumEventsTest(unittest.TestCase):
    def test_kick_present(self):
        events = _drum_events(bpm=126, bars=4)
        kicks = [e for e in events if e["midi_note"] == 36]
        self.assertGreater(len(kicks), 0)

    def test_clap_present(self):
        events = _drum_events(bpm=126, bars=4)
        claps = [e for e in events if e["midi_note"] == 39]
        self.assertGreater(len(claps), 0)

    def test_hat_closed_present(self):
        events = _drum_events(bpm=126, bars=4)
        hats = [e for e in events if e["midi_note"] == 42]
        self.assertGreater(len(hats), 0)

    def test_drums_on_channel_9(self):
        events = _drum_events(bpm=126, bars=4)
        for event in events:
            self.assertEqual(event["channel"], 9)

    def test_four_kicks_per_bar(self):
        events = _drum_events(bpm=120, bars=1)
        kicks = [e for e in events if e["midi_note"] == 36]
        self.assertEqual(len(kicks), 4)


class ChordEventsTest(unittest.TestCase):
    def test_minor_chord_notes_in_range(self):
        events = _chord_events(root=50, mode="minor", bpm=126, bars=4)
        for e in events:
            self.assertGreaterEqual(e["midi_note"], 36)
            self.assertLessEqual(e["midi_note"], 96)

    def test_chord_progression_repeats_every_4_bars(self):
        events_4 = _chord_events(root=50, mode="minor", bpm=120, bars=4)
        events_8 = _chord_events(root=50, mode="minor", bpm=120, bars=8)
        bar_s = 4 * 60.0 / 120
        first_4 = [e["midi_note"] for e in events_4]
        second_4 = [e["midi_note"] for e in events_8 if e["start"] >= bar_s * 4]
        self.assertEqual(first_4, second_4)


class MelodyEventsTest(unittest.TestCase):
    def test_melody_notes_in_range(self):
        events = _melody_events(root=62, mode="minor", bpm=126, bars=32)
        for e in events:
            self.assertGreaterEqual(e["midi_note"], 48)
            self.assertLessEqual(e["midi_note"], 96)

    def test_melody_uses_pentatonic(self):
        root = 62  # D
        events = _melody_events(root=root, mode="minor", bpm=120, bars=4)
        minor_penta = {root + ivl for ivl in [0, 3, 5, 7, 10]}
        minor_penta_extended = minor_penta | {n + 12 for n in minor_penta} | {n - 12 for n in minor_penta}
        for e in events:
            self.assertIn(e["midi_note"], minor_penta_extended,
                          f"Note {e['midi_note']} not in D minor pentatonic")


class GenerateInspiredLoopTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _make_analysis(self, bpm=126, key="D minor"):
        return {
            "bpm": bpm,
            "bpm_confidence": 0.8,
            "key": key,
            "key_confidence": 0.75,
            "energy_curve": [{"time": i * 0.1, "energy": 0.3} for i in range(40)],
        }

    def test_all_five_midi_files_written(self):
        analysis = self._make_analysis()
        comp, _ = generate_inspired_loop(analysis, self._tmp, bars=32)
        for track in ("bass", "drums", "chords", "melody", "full_loop"):
            self.assertIn(track, comp["midi"])
            self.assertTrue(os.path.isfile(comp["midi"][track]),
                            f"Missing: {comp['midi'][track]}")

    def test_midi_files_are_valid_midi(self):
        analysis = self._make_analysis()
        comp, _ = generate_inspired_loop(analysis, self._tmp, bars=32)
        for track, path in comp["midi"].items():
            with open(path, "rb") as f:
                header = f.read(4)
            self.assertEqual(header, b"MThd", f"{track}: invalid MIDI header")

    def test_full_loop_is_format_1(self):
        analysis = self._make_analysis()
        comp, _ = generate_inspired_loop(analysis, self._tmp, bars=32)
        with open(comp["midi"]["full_loop"], "rb") as f:
            f.read(8)  # MThd + length
            import struct
            fmt = struct.unpack(">H", f.read(2))[0]
        self.assertEqual(fmt, 1)

    def test_summary_json_written(self):
        analysis = self._make_analysis()
        generate_inspired_loop(analysis, self._tmp, bars=32)
        summary_path = os.path.join(self._tmp, "summary.json")
        self.assertTrue(os.path.isfile(summary_path))
        with open(summary_path) as f:
            summary = json.load(f)
        self.assertEqual(summary["bars"], 32)
        self.assertEqual(summary["key"], "D minor")
        for track in ("bass", "drums", "chords", "melody", "full_loop"):
            self.assertIn(track, summary["midi"])

    def test_prompt_txt_written(self):
        analysis = self._make_analysis()
        _, suno = generate_inspired_loop(analysis, self._tmp, bars=32)
        self.assertTrue(os.path.isfile(suno["path"]))
        self.assertIn("D minor", suno["text"])
        self.assertGreater(len(suno["text"]), 50)

    def test_instrumental_hook_proxy_prompt_does_not_request_lead_vocal(self):
        analysis = self._make_analysis()
        analysis["reference_transform"] = {
            "vocals": {
                "preserve_role": True,
                "render_mode": "instrumental_hook_proxy",
                "role": "lead vocal hook",
            }
        }
        _, suno = generate_inspired_loop(analysis, self._tmp, bars=32)
        self.assertIn("Instrumental, no lead vocal", suno["text"])
        self.assertNotIn("Include a new lead vocal hook", suno["text"])

    def test_loop_duration_matches_bpm_and_bars(self):
        bpm = 120.0
        bars = 32
        analysis = self._make_analysis(bpm=bpm)
        comp, _ = generate_inspired_loop(analysis, self._tmp, bars=bars)
        expected_duration = bars * 4 * 60.0 / bpm
        bass_events = _bass_events(root=38, bpm=bpm, bars=bars)
        actual_last = max(e["start"] + e["duration"] for e in bass_events)
        self.assertAlmostEqual(actual_last, expected_duration, delta=0.5)

    def test_composition_dict_has_required_keys(self):
        analysis = self._make_analysis()
        comp, suno = generate_inspired_loop(analysis, self._tmp, bars=32)
        for key in ("bars", "bpm", "key", "style", "midi", "description"):
            self.assertIn(key, comp)
        self.assertIn("text", suno)
        self.assertIn("path", suno)

    def test_major_key_generates_major_chords(self):
        # I chord shifted into the mid register: C=60, E=64, G=67.
        events = _chord_events(root=48, mode="major", bpm=120, bars=4)
        notes = {e["midi_note"] for e in events}
        self.assertIn(64, notes, "major third (E) missing from C major chord")
        self.assertNotIn(63, notes, "minor third (Eb) should not appear in C major")


if __name__ == "__main__":
    unittest.main()
