#!/usr/bin/env python3
from __future__ import annotations

import os
import tempfile
import unittest

import numpy as np
from scipy.io import wavfile

from analysis.arrangement_continuation import continuation_arranger
from analysis.arrangement_continuation.continuation_arranger import arrange_continuation, load_stems


class ContinuationArrangerTest(unittest.TestCase):
    def test_load_stems_maps_roles_and_mutes_vocals_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_tone(os.path.join(tmp, "Drums.wav"), frequency=90)
            self._write_tone(os.path.join(tmp, "Bass.wav"), frequency=55)
            self._write_tone(os.path.join(tmp, "Vocals.wav"), frequency=220)
            self._write_tone(os.path.join(tmp, "candidate-4.wav"), frequency=330)

            stems, ignored = load_stems(tmp)

        self.assertEqual([stem.role for stem in stems], ["drums", "bass"])
        self.assertTrue(any(item.get("role") == "vocals" for item in ignored))
        self.assertTrue(any(item.get("reason") == "full_mix_or_candidate_not_used_as_stem" for item in ignored))

    def test_load_stems_prefers_filename_role_over_parent_folder_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = os.path.join(tmp, "candidate-3-stems-percussion-wav")
            os.makedirs(input_dir)
            for filename, frequency in {
                "kick.wav": 80,
                "snare.wav": 220,
                "hihats.wav": 7000,
                "toms.wav": 140,
                "cymbals.wav": 4000,
                "bass.wav": 55,
                "fx.wav": 1200,
                "synth.wav": 330,
            }.items():
                self._write_tone(os.path.join(input_dir, filename), frequency=frequency)

            stems, _ignored = load_stems(input_dir)

        self.assertEqual([stem.role for stem in stems], [
            "kick",
            "snare",
            "hihats",
            "toms",
            "cymbals",
            "bass",
            "synths",
            "fx",
        ])

    def test_arranger_preserves_original_stems_then_appends_to_target_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = os.path.join(tmp, "input")
            os.makedirs(input_dir)
            sr = 8000
            duration = 8.0
            drums = self._pattern(sr, duration, 90, [0, 4, 8, 12], amplitude=0.45)
            bass = self._pattern(sr, duration, 55, [2, 6, 10, 14], amplitude=0.3)
            stabs = self._pattern(sr, duration, 220, [0, 8], amplitude=0.18)
            wavfile.write(os.path.join(input_dir, "drums.wav"), sr, np.asarray(drums * 32767, dtype=np.int16))
            wavfile.write(os.path.join(input_dir, "bass.wav"), sr, np.asarray(bass * 32767, dtype=np.int16))
            wavfile.write(os.path.join(input_dir, "warm_stabs.wav"), sr, np.asarray(stabs * 32767, dtype=np.int16))

            out = os.path.join(tmp, "out")
            payload = arrange_continuation(
                input_dir=input_dir,
                output_dir=out,
                target_duration=14.0,
                continue_from=8.0,
                bpm=120,
                phrase_bars=2,
            )

            arranged_drums = wavfile.read(os.path.join(out, "arranged-stems", "drums.wav"))[1]
            original_drums = wavfile.read(os.path.join(input_dir, "drums.wav"))[1]
            full_mix_rate, full_mix = wavfile.read(os.path.join(out, "arranged-full-mix.wav"))

            self.assertTrue(payload["ok"])
            self.assertEqual(full_mix_rate, sr)
            self.assertAlmostEqual(len(full_mix) / sr, 14.0, places=2)
            np.testing.assert_allclose(arranged_drums[: len(original_drums)], original_drums, atol=1)
            self.assertTrue(os.path.exists(payload["outputs"]["arrangement_map"]))
            self.assertTrue(os.path.exists(payload["outputs"]["report"]))
            self.assertEqual([section["name"] for section in payload["sections"]], [
                "continue_groove",
                "stripped_breakdown",
                "return_to_groove",
                "dj_outro",
            ])

    def test_arranger_keeps_suno_drums_and_exports_ai_drum_substems_as_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = os.path.join(tmp, "input")
            os.makedirs(input_dir)
            sr = 8000
            duration = 8.0
            drums = self._pattern(sr, duration, 90, [0, 4, 8, 12], amplitude=0.45)
            bass = self._pattern(sr, duration, 55, [2, 6, 10, 14], amplitude=0.3)
            wavfile.write(os.path.join(input_dir, "drums.wav"), sr, np.asarray(drums * 32767, dtype=np.int16))
            wavfile.write(os.path.join(input_dir, "bass.wav"), sr, np.asarray(bass * 32767, dtype=np.int16))

            original_separator = continuation_arranger.separate_drum_elements

            def fake_separator(_drum_path, output_dir):
                os.makedirs(output_dir, exist_ok=True)
                stems = {}
                for role, freq in {"kick": 80, "snare": 220, "hihats": 7000, "cymbals": 4000, "toms": 140}.items():
                    path = os.path.join(output_dir, f"{role}.wav")
                    self._write_tone(path, frequency=freq, duration=duration, sample_rate=sr)
                    stems[role] = path
                return {"available": True, "method": "fake_drumsep", "stems": stems, "warnings": []}

            continuation_arranger.separate_drum_elements = fake_separator
            try:
                out = os.path.join(tmp, "out")
                payload = arrange_continuation(
                    input_dir=input_dir,
                    output_dir=out,
                    target_duration=14.0,
                    continue_from=8.0,
                    bpm=120,
                    phrase_bars=2,
                    drum_substems=True,
                )
            finally:
                continuation_arranger.separate_drum_elements = original_separator

            roles = [stem["role"] for stem in payload["stems"]]
            reference_roles = [stem["role"] for stem in payload["percussion_reference_stems"]]
            self.assertIn("drums", roles)
            self.assertNotIn("kick", roles)
            self.assertNotIn("snare", roles)
            self.assertIn("kick", reference_roles)
            self.assertIn("snare", reference_roles)
            self.assertIn("hihats", reference_roles)
            self.assertIn("cymbals", reference_roles)
            self.assertTrue(payload["drum_subseparation"]["available"])
            self.assertTrue(os.path.exists(os.path.join(out, "arranged-stems", "drums.wav")))
            self.assertFalse(os.path.exists(os.path.join(out, "arranged-stems", "kick.wav")))
            self.assertTrue(os.path.exists(os.path.join(out, "percussion-reference-stems", "kick.wav")))

    def test_arranger_can_render_explicit_percussion_reference_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = os.path.join(tmp, "input")
            reference_dir = os.path.join(tmp, "percussion")
            os.makedirs(input_dir)
            os.makedirs(reference_dir)
            sr = 8000
            duration = 8.0
            drums = self._pattern(sr, duration, 90, [0, 4, 8, 12], amplitude=0.45)
            bass = self._pattern(sr, duration, 55, [2, 6, 10, 14], amplitude=0.3)
            wavfile.write(os.path.join(input_dir, "drums.wav"), sr, np.asarray(drums * 32767, dtype=np.int16))
            wavfile.write(os.path.join(input_dir, "bass.wav"), sr, np.asarray(bass * 32767, dtype=np.int16))
            for filename, frequency in {
                "kick.wav": 80,
                "snare.wav": 220,
                "hihats.wav": 7000,
                "toms.wav": 140,
                "cymbals.wav": 4000,
                "bass.wav": 55,
            }.items():
                self._write_tone(os.path.join(reference_dir, filename), frequency=frequency, duration=duration, sample_rate=sr)

            out = os.path.join(tmp, "out")
            payload = arrange_continuation(
                input_dir=input_dir,
                output_dir=out,
                target_duration=14.0,
                continue_from=8.0,
                bpm=120,
                phrase_bars=2,
                percussion_reference_input_dir=reference_dir,
            )

            roles = [stem["role"] for stem in payload["stems"]]
            reference_roles = [stem["role"] for stem in payload["percussion_reference_stems"]]
            self.assertIn("drums", roles)
            self.assertNotIn("kick", roles)
            self.assertIn("kick", reference_roles)
            self.assertIn("snare", reference_roles)
            self.assertIn("hihats", reference_roles)
            self.assertNotIn("bass", reference_roles)
            self.assertTrue(os.path.exists(os.path.join(out, "arranged-stems", "drums.wav")))
            self.assertTrue(os.path.exists(os.path.join(out, "percussion-reference-stems", "kick.wav")))
            self.assertIsNotNone(payload["outputs"]["percussion_reference_dir"])

    def test_prebreak_diagnostic_uses_only_exact_bar_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = os.path.join(tmp, "input")
            os.makedirs(input_dir)
            sr = 8000
            duration = 64.0
            drums = self._pattern(sr, duration, 90, [0, 4, 8, 12], amplitude=0.45)
            bass = self._pattern(sr, duration, 55, [2, 6, 10, 14], amplitude=0.3)
            wavfile.write(os.path.join(input_dir, "drums.wav"), sr, np.asarray(drums * 32767, dtype=np.int16))
            wavfile.write(os.path.join(input_dir, "bass.wav"), sr, np.asarray(bass * 32767, dtype=np.int16))

            out = os.path.join(tmp, "out")
            payload = arrange_continuation(
                input_dir=input_dir,
                output_dir=out,
                target_duration=120.0,
                continue_from="auto",
                bpm=120,
                phrase_bars=2,
                arrangement_mode="prebreak-diagnostic",
                preserve_source_bars=8,
                pre_break_source_start_bars=8,
                pre_break_source_bars=4,
                pre_break_groove_bars=8,
                breakdown_source_start_bars=12,
                breakdown_source_bars=4,
            )

            self.assertEqual(payload["arrangement_mode"], "prebreak-diagnostic")
            self.assertAlmostEqual(payload["continue_from_seconds"], 16.0, places=2)
            self.assertAlmostEqual(payload["target_duration_seconds"], 40.0, places=2)
            self.assertEqual([section["name"] for section in payload["sections"]], [
                "pre_break_developed_groove",
                "stripped_breakdown",
            ])
            self.assertAlmostEqual(payload["sections"][0]["duration_seconds"], 16.0, places=2)
            self.assertAlmostEqual(payload["sections"][1]["duration_seconds"], 8.0, places=2)
            self.assertAlmostEqual(payload["sections"][0]["source_block"]["start_seconds"], 16.0, places=2)
            self.assertAlmostEqual(payload["sections"][0]["source_block"]["end_seconds"], 24.0, places=2)

    def test_bar_locked_modes_allow_eight_bar_intro_but_reject_off_grid_intro(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = os.path.join(tmp, "input")
            os.makedirs(input_dir)
            sr = 8000
            duration = 64.0
            drums = self._pattern(sr, duration, 90, [0, 4, 8, 12], amplitude=0.45)
            bass = self._pattern(sr, duration, 55, [2, 6, 10, 14], amplitude=0.3)
            wavfile.write(os.path.join(input_dir, "drums.wav"), sr, np.asarray(drums * 32767, dtype=np.int16))
            wavfile.write(os.path.join(input_dir, "bass.wav"), sr, np.asarray(bass * 32767, dtype=np.int16))

            payload = arrange_continuation(
                input_dir=input_dir,
                output_dir=os.path.join(tmp, "out_eight"),
                target_duration=120.0,
                bpm=120,
                phrase_bars=16,
                arrangement_mode="prebreak-diagnostic",
                intro_bars=16,
                source_intro_bars=8,
                breakdown_bars=16,
                outro_bars=16,
                preserve_source_bars=16,
                pre_break_source_start_bars=16,
                pre_break_source_bars=16,
                pre_break_groove_bars=16,
                breakdown_source_start_bars=16,
                breakdown_source_bars=16,
            )
            self.assertEqual(payload["intro_bars"], 16)
            self.assertEqual(payload["source_intro_bars"], 8)
            self.assertEqual(payload["prepend_intro_bars"], 8)
            self.assertEqual(payload["breakdown_bars"], 16)
            self.assertEqual(payload["outro_bars"], 16)
            self.assertEqual(payload["breakdown_source_bars"], 16)

            with self.assertRaisesRegex(ValueError, "intro_bars=12 is not house-grid locked"):
                arrange_continuation(
                    input_dir=input_dir,
                    output_dir=os.path.join(tmp, "out_twelve"),
                    target_duration=120.0,
                    bpm=120,
                    phrase_bars=16,
                    arrangement_mode="prebreak-diagnostic",
                    intro_bars=12,
                    source_intro_bars=0,
                    preserve_source_bars=16,
                    pre_break_source_start_bars=16,
                    pre_break_source_bars=16,
                    pre_break_groove_bars=16,
                    breakdown_source_start_bars=16,
                    breakdown_source_bars=16,
                )

            with self.assertRaisesRegex(ValueError, "breakdown_source_bars=12 is not house-grid locked"):
                arrange_continuation(
                    input_dir=input_dir,
                    output_dir=os.path.join(tmp, "out_bad_breakdown"),
                    target_duration=120.0,
                    bpm=120,
                    phrase_bars=16,
                    arrangement_mode="prebreak-diagnostic",
                    intro_bars=16,
                    source_intro_bars=0,
                    breakdown_bars=12,
                    preserve_source_bars=16,
                    pre_break_source_start_bars=16,
                    pre_break_source_bars=16,
                    breakdown_source_start_bars=16,
                )

    def test_club_second_half_uses_bar_locked_fft_selected_contiguous_post_drop(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = os.path.join(tmp, "input")
            os.makedirs(input_dir)
            sr = 8000
            duration = 40.0
            drums = self._pattern(sr, duration, 90, [0, 4, 8, 12], amplitude=0.45)
            bass = self._pattern(sr, duration, 55, [2, 6, 10, 14], amplitude=0.3)
            synth = self._pattern(sr, duration, 220, [0, 8], amplitude=0.15)
            wavfile.write(os.path.join(input_dir, "drums.wav"), sr, np.asarray(drums * 32767, dtype=np.int16))
            wavfile.write(os.path.join(input_dir, "bass.wav"), sr, np.asarray(bass * 32767, dtype=np.int16))
            wavfile.write(os.path.join(input_dir, "synth.wav"), sr, np.asarray(synth * 32767, dtype=np.int16))

            payload = arrange_continuation(
                input_dir=input_dir,
                output_dir=os.path.join(tmp, "out_second_half"),
                target_duration=120.0,
                bpm=120,
                phrase_bars=2,
                arrangement_mode="club-second-half",
                intro_bars=4,
                source_intro_bars=2,
                preserve_source_bars=4,
                transition_grid_bars=2,
                pre_break_source_start_bars=4,
                pre_break_source_bars=2,
                pre_break_groove_bars=4,
                breakdown_source_start_bars=6,
                breakdown_bars=2,
                post_drop_groove_bars=4,
                second_half_extra_bars=2,
                post_drop_source_start_bars=4,
                post_drop_source_bars=4,
                outro_bars=2,
            )

            self.assertEqual(payload["arrangement_mode"], "club-second-half")
            self.assertEqual([section["name"] for section in payload["sections"]], [
                "pre_break_developed_groove",
                "stripped_breakdown",
                "post_drop_fft_selected_groove",
                "dj_outro",
            ])
            self.assertEqual([section["duration_bars"] for section in payload["sections"]], [4.0, 2.0, 6.0, 2.0])
            self.assertEqual(payload["post_drop_groove_bars"], 4)
            self.assertEqual(payload["second_half_extra_bars"], 2)
            self.assertEqual(payload["effective_post_drop_groove_bars"], 6)
            self.assertEqual(payload["post_drop_source_start_bars"], 4)
            self.assertEqual(payload["post_drop_source_bars"], 4)
            post_drop = payload["sections"][2]
            outro = payload["sections"][3]
            self.assertEqual(payload["blueprint"]["post_drop_selection"]["method"], "explicit_start")
            self.assertEqual(post_drop["source_start_bars"], 4.0)
            self.assertEqual(post_drop["source_end_bars"] - post_drop["source_start_bars"], 4.0)
            self.assertEqual(post_drop["duration_bars"], 6.0)
            self.assertEqual(outro["source_start_bars"], 4.0)
            self.assertEqual(outro["source_end_bars"], 6.0)
            self.assertIn("bass", outro["mute_roles"])

    def test_preserve_source_start_bars_skips_bad_leading_source_material(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = os.path.join(tmp, "input")
            os.makedirs(input_dir)
            sr = 8000
            duration = 20.0
            drums = self._pattern(sr, duration, 90, [0, 4, 8, 12], amplitude=0.45)
            bass = self._pattern(sr, duration, 55, [2, 6, 10, 14], amplitude=0.3)
            wavfile.write(os.path.join(input_dir, "drums.wav"), sr, np.asarray(drums * 32767, dtype=np.int16))
            wavfile.write(os.path.join(input_dir, "bass.wav"), sr, np.asarray(bass * 32767, dtype=np.int16))

            out = os.path.join(tmp, "out_skip")
            payload = arrange_continuation(
                input_dir=input_dir,
                output_dir=out,
                target_duration=16.0,
                bpm=120,
                phrase_bars=2,
                arrangement_mode="prebreak-diagnostic",
                preserve_source_start_bars=2,
                preserve_source_bars=4,
                pre_break_groove_bars=0,
                pre_break_source_start_bars=6,
                pre_break_source_bars=2,
                breakdown_source_start_bars=6,
                breakdown_bars=2,
            )

            sample_rate, arranged_drums = wavfile.read(os.path.join(out, "arranged-stems", "drums.wav"))
            _source_rate, original_drums = wavfile.read(os.path.join(input_dir, "drums.wav"))
            bar_samples = int(sample_rate * 2)
            expected = original_drums[2 * bar_samples : 6 * bar_samples]
            np.testing.assert_allclose(arranged_drums[: len(expected)], expected, atol=1)
            self.assertEqual(payload["preserve_source_start_bars"], 2)
            self.assertAlmostEqual(payload["preserve_source_start_seconds"], 4.0, places=2)

    def test_reference_blueprint_derives_bass_muted_and_outro_sections_from_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = os.path.join(tmp, "input")
            os.makedirs(input_dir)
            sr = 8000
            duration = 24.0
            drums = self._pattern(sr, duration, 90, [0, 4, 8, 12], amplitude=0.45)
            bass = self._pattern(sr, duration, 55, [2, 6, 10, 14], amplitude=0.3)
            synth = self._pattern(sr, duration, 220, [0, 8], amplitude=0.15)
            wavfile.write(os.path.join(input_dir, "drums.wav"), sr, np.asarray(drums * 32767, dtype=np.int16))
            wavfile.write(os.path.join(input_dir, "bass.wav"), sr, np.asarray(bass * 32767, dtype=np.int16))
            wavfile.write(os.path.join(input_dir, "synth.wav"), sr, np.asarray(synth * 32767, dtype=np.int16))

            blueprint = self._reference_blueprint(sr=sr, duration=40.0)
            blueprint_path = os.path.join(tmp, "reference.wav")
            wavfile.write(blueprint_path, sr, np.asarray(blueprint * 32767, dtype=np.int16))

            out = os.path.join(tmp, "out_reference")
            payload = arrange_continuation(
                input_dir=input_dir,
                output_dir=out,
                target_duration=40.0,
                bpm=120,
                phrase_bars=2,
                arrangement_mode="reference-blueprint",
                blueprint_audio=blueprint_path,
                preserve_source_bars=4,
                transition_grid_bars=2,
                breakdown_drum_mode="tops",
                outro_bars=2,
            )

            names = [section["name"] for section in payload["sections"]]
            self.assertEqual(payload["arrangement_mode"], "reference-blueprint")
            self.assertIn("reference_bass_muted_groove", names)
            self.assertIn("dj_outro", names)
            self.assertTrue(all(section["duration_bars"] % 2 == 0 for section in payload["sections"]))
            bass_muted = next(section for section in payload["sections"] if section["name"] == "reference_bass_muted_groove")
            outro = next(section for section in payload["sections"] if section["name"] == "dj_outro")
            self.assertIn("bass", bass_muted["mute_roles"])
            self.assertIn("bass", outro["mute_roles"])
            self.assertNotIn("kick", outro["mute_roles"])

    def test_breakdown_drum_mode_can_reintroduce_drums_halfway(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = os.path.join(tmp, "input")
            os.makedirs(input_dir)
            sr = 8000
            duration = 16.0
            drums = self._pattern(sr, duration, 90, [0, 4, 8, 12], amplitude=0.45)
            bass = self._pattern(sr, duration, 55, [2, 6, 10, 14], amplitude=0.3)
            wavfile.write(os.path.join(input_dir, "drums.wav"), sr, np.asarray(drums * 32767, dtype=np.int16))
            wavfile.write(os.path.join(input_dir, "bass.wav"), sr, np.asarray(bass * 32767, dtype=np.int16))

            original_separator = continuation_arranger.separate_drum_elements

            def fake_separator(_drum_path, output_dir):
                os.makedirs(output_dir, exist_ok=True)
                stems = {}
                for role, freq in {"kick": 80, "snare": 220, "hihats": 7000, "cymbals": 4000, "toms": 140}.items():
                    path = os.path.join(output_dir, f"{role}.wav")
                    self._write_tone(path, frequency=freq, duration=duration, sample_rate=sr)
                    stems[role] = path
                return {"available": True, "method": "fake_drumsep", "stems": stems, "warnings": []}

            continuation_arranger.separate_drum_elements = fake_separator
            try:
                out = os.path.join(tmp, "out_half_full")
                payload = arrange_continuation(
                    input_dir=input_dir,
                    output_dir=out,
                    target_duration=120.0,
                    bpm=120,
                    phrase_bars=2,
                    drum_substems=True,
                    arrangement_mode="prebreak-diagnostic",
                    preserve_source_bars=4,
                    pre_break_groove_bars=0,
                    pre_break_source_start_bars=4,
                    pre_break_source_bars=2,
                    breakdown_source_start_bars=4,
                    breakdown_bars=2,
                    breakdown_drum_mode="half-full",
                )
            finally:
                continuation_arranger.separate_drum_elements = original_separator

            self.assertEqual(payload["breakdown_drum_mode"], "half-full")
            self.assertEqual(payload["sections"][0]["breakdown_drum_mode"], "half-full")
            sample_rate, snare = wavfile.read(os.path.join(out, "percussion-reference-stems", "snare.wav"))
            self.assertEqual(sample_rate, sr)
            bar_samples = int(sr * 2)
            breakdown_start = 4 * bar_samples
            first_half = snare[breakdown_start : breakdown_start + bar_samples]
            second_half = snare[breakdown_start + bar_samples : breakdown_start + 2 * bar_samples]
            self.assertEqual(float(np.max(np.abs(first_half))), 0.0)
            self.assertGreater(float(np.max(np.abs(second_half))), 0.0)

    def _write_tone(self, path: str, frequency: float, duration: float = 1.0, sample_rate: int = 8000):
        t = np.arange(int(sample_rate * duration)) / sample_rate
        audio = 0.25 * np.sin(2 * np.pi * frequency * t)
        stereo = np.stack([audio, audio], axis=1)
        wavfile.write(path, sample_rate, np.asarray(stereo * 32767, dtype=np.int16))

    def _pattern(self, sample_rate: int, duration: float, frequency: float, sixteenths: list[int], amplitude: float):
        t = np.arange(int(sample_rate * duration)) / sample_rate
        audio = np.zeros_like(t, dtype=np.float32)
        sixteenth_seconds = 60.0 / 120.0 / 4.0
        for index, time in enumerate(t):
            position = int(time / sixteenth_seconds) % 16
            env = amplitude if position in sixteenths else amplitude * 0.03
            audio[index] = env * np.sin(2 * np.pi * frequency * time)
        return np.stack([audio, audio], axis=1)

    def _reference_blueprint(self, sr: int, duration: float):
        t = np.arange(int(sr * duration)) / sr
        audio = np.zeros_like(t, dtype=np.float32)
        bar_seconds = 2.0
        for index, time in enumerate(t):
            bar = int(time / bar_seconds)
            high = 0.12 * np.sin(2 * np.pi * 3500 * time)
            low = 0.28 * np.sin(2 * np.pi * 65 * time)
            mid = 0.12 * np.sin(2 * np.pi * 220 * time)
            if 8 <= bar < 12:
                audio[index] = 0.16 * np.sin(2 * np.pi * 65 * time) + high + 0.04 * mid
            elif bar >= 18:
                audio[index] = 0.18 * high + 0.04 * mid
            else:
                audio[index] = low + high + mid
        return np.stack([audio, audio], axis=1)


if __name__ == "__main__":
    unittest.main()
