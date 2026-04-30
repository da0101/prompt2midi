import math
import os
import struct
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(__file__))

from feature_extraction import analyze_wav
from analyze import _promote_exports, run as run_analysis
from audio_generation import _condition_prompt, _sanitize_user_prompt_for_model
from ace_step_generation import _choose_candidate, _select_candidate_for_promotion, _selection_score, _source_conditioning, _task_type
from bass_transcription import transcribe_bassline
from composition import _composition_style
from drum_analysis import drum_pattern_to_midi_events
from midi_extraction import write_note_events_midi, write_reference_sketch_midi
from reference_transform import build_reference_transform
from reference_groove import score_groove_similarity
from source_transcription import _extract_bassline, transcribe_with_model
from stem_separation import separate_for_transcription


class FeatureExtractionTest(unittest.TestCase):
    def test_analyze_wav_returns_phase_one_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = os.path.join(temp_dir, "pulse.wav")
            self._write_pulsed_wav(wav_path, bpm=120)

            result = analyze_wav(wav_path)

        self.assertEqual(result["sample_rate"], 8000)
        self.assertGreater(result["duration_seconds"], 3.9)
        self.assertIsNotNone(result["bpm"])
        self.assertAlmostEqual(result["bpm"], 120, delta=1)
        self.assertIn("bpm_confidence", result)
        self.assertGreater(result["bpm_confidence"], 0)
        self.assertIn("key", result)
        self.assertIn("key_confidence", result)
        self.assertGreater(len(result["energy_curve"]), 2)
        self.assertIn("loudness", result)
        self.assertTrue(any("not source-track transcription" in warning for warning in result["warnings"]))

    def test_write_reference_sketch_midi_creates_standard_midi_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            midi_path = os.path.join(temp_dir, "reference-sketch.mid")
            written = write_reference_sketch_midi(midi_path, key="A major", bpm=124)

            with open(written, "rb") as midi_file:
                header = midi_file.read(4)

        self.assertEqual(header, b"MThd")

    def test_transcribe_bassline_tracks_simple_low_notes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = os.path.join(temp_dir, "bass.wav")
            self._write_bass_pattern_wav(wav_path)

            transcription = transcribe_bassline(wav_path, bpm=120)
            midi_path = os.path.join(temp_dir, "bass-transcription.mid")
            written = write_note_events_midi(midi_path, transcription["events"], bpm=120)

            with open(written, "rb") as midi_file:
                midi_bytes = midi_file.read()

        notes = [event["midi_note"] for event in transcription["events"]]
        self.assertGreaterEqual(len(notes), 3)
        self.assertIn(36, notes)
        self.assertIn(43, notes)
        self.assertGreater(transcription["confidence"], 0.1)
        self.assertEqual(midi_bytes[:4], b"MThd")

    def test_full_analysis_labels_generated_and_heuristic_midi_assets(self):
        old_disable = os.environ.get("PROMPT2MIDI_DISABLE_MODEL")
        old_disable_stems = os.environ.get("PROMPT2MIDI_DISABLE_STEMS")
        os.environ["PROMPT2MIDI_DISABLE_MODEL"] = "1"
        os.environ["PROMPT2MIDI_DISABLE_STEMS"] = "1"
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                wav_path = os.path.join(temp_dir, "pulse.wav")
                self._write_pulsed_wav(wav_path, bpm=120)

                result = run_analysis(wav_path, os.path.join(temp_dir, "job"))
        finally:
            if old_disable is None:
                os.environ.pop("PROMPT2MIDI_DISABLE_MODEL", None)
            else:
                os.environ["PROMPT2MIDI_DISABLE_MODEL"] = old_disable
            if old_disable_stems is None:
                os.environ.pop("PROMPT2MIDI_DISABLE_STEMS", None)
            else:
                os.environ["PROMPT2MIDI_DISABLE_STEMS"] = old_disable_stems

        assets = {asset["key"]: asset for asset in result["midi_assets"]}
        self.assertFalse(assets["reference_sketch"]["is_transcription"])
        self.assertEqual(assets["reference_sketch"]["kind"], "generated_sketch")
        self.assertIn("bass_transcription", assets)
        self.assertEqual(assets["bass_transcription"]["source_method"], "full_mix_low_frequency_tracking")
        self.assertFalse(result["analysis"]["model_transcription"]["available"])
        self.assertFalse(result["analysis"]["stem_separation"]["available"])

    def test_model_transcription_can_be_explicitly_disabled(self):
        old_disable = os.environ.get("PROMPT2MIDI_DISABLE_MODEL")
        os.environ["PROMPT2MIDI_DISABLE_MODEL"] = "1"
        try:
            result = transcribe_with_model("unused.wav", "/tmp", bpm=120)
        finally:
            if old_disable is None:
                os.environ.pop("PROMPT2MIDI_DISABLE_MODEL", None)
            else:
                os.environ["PROMPT2MIDI_DISABLE_MODEL"] = old_disable

        self.assertFalse(result["available"])
        self.assertIn("disabled", result["warnings"][0])

    def test_stem_separation_can_be_explicitly_disabled(self):
        old_disable = os.environ.get("PROMPT2MIDI_DISABLE_STEMS")
        os.environ["PROMPT2MIDI_DISABLE_STEMS"] = "1"
        try:
            result = separate_for_transcription("unused.wav", "/tmp")
        finally:
            if old_disable is None:
                os.environ.pop("PROMPT2MIDI_DISABLE_STEMS", None)
            else:
                os.environ["PROMPT2MIDI_DISABLE_STEMS"] = old_disable

        self.assertFalse(result["available"])
        self.assertEqual(result["method"], "disabled")
        self.assertIn("disabled", result["warnings"][0])

    def test_missing_stem_engine_returns_warning_without_failing(self):
        old_disable = os.environ.get("PROMPT2MIDI_DISABLE_STEMS")
        old_engine = os.environ.get("PROMPT2MIDI_DEMUCS")
        old_engine_alt = os.environ.get("PROMPT2MIDI_STEM_ENGINE")
        os.environ.pop("PROMPT2MIDI_DISABLE_STEMS", None)
        os.environ["PROMPT2MIDI_DEMUCS"] = "/definitely/not/demucs"
        os.environ.pop("PROMPT2MIDI_STEM_ENGINE", None)
        try:
            result = separate_for_transcription("unused.wav", "/tmp")
        finally:
            if old_disable is None:
                os.environ.pop("PROMPT2MIDI_DISABLE_STEMS", None)
            else:
                os.environ["PROMPT2MIDI_DISABLE_STEMS"] = old_disable
            if old_engine is None:
                os.environ.pop("PROMPT2MIDI_DEMUCS", None)
            else:
                os.environ["PROMPT2MIDI_DEMUCS"] = old_engine
            if old_engine_alt is None:
                os.environ.pop("PROMPT2MIDI_STEM_ENGINE", None)
            else:
                os.environ["PROMPT2MIDI_STEM_ENGINE"] = old_engine_alt

        self.assertFalse(result["available"])
        self.assertIn("not installed", result["warnings"][0])

    def test_model_transcription_uses_bass_stem_when_available(self):
        old_engine = os.environ.get("PROMPT2MIDI_BASIC_PITCH")
        old_disable = os.environ.get("PROMPT2MIDI_DISABLE_MODEL")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                fake_engine = os.path.join(temp_dir, "fake-basic-pitch")
                calls_path = os.path.join(temp_dir, "calls.txt")
                self._write_fake_basic_pitch(fake_engine, calls_path)
                os.environ["PROMPT2MIDI_BASIC_PITCH"] = fake_engine
                os.environ.pop("PROMPT2MIDI_DISABLE_MODEL", None)

                mix_path = os.path.join(temp_dir, "mix.wav")
                stem_path = os.path.join(temp_dir, "bass.wav")
                self._write_pulsed_wav(mix_path, bpm=120)
                self._write_bass_pattern_wav(stem_path)

                result = transcribe_with_model(
                    mix_path,
                    os.path.join(temp_dir, "job"),
                    bpm=120,
                    stem_result={"available": True, "method": "demucs_htdemucs", "stems": {"bass": stem_path}, "warnings": []},
                )
                with open(calls_path) as call_file:
                    calls = call_file.read()
        finally:
            if old_engine is None:
                os.environ.pop("PROMPT2MIDI_BASIC_PITCH", None)
            else:
                os.environ["PROMPT2MIDI_BASIC_PITCH"] = old_engine
            if old_disable is None:
                os.environ.pop("PROMPT2MIDI_DISABLE_MODEL", None)
            else:
                os.environ["PROMPT2MIDI_DISABLE_MODEL"] = old_disable

        tracks = {track["key"]: track for track in result["tracks"]}
        self.assertTrue(result["available"])
        self.assertIn("source_bass_transcription", tracks)
        self.assertEqual(tracks["source_bass_transcription"]["kind"], "source_aware_transcription")
        self.assertEqual(tracks["source_bass_transcription"]["source_stem"], "bass")
        self.assertIn(stem_path, calls)

    def test_model_bass_filter_keeps_one_low_note_per_time_bin(self):
        events = [
            {"start": 0.01, "duration": 0.1, "midi_note": 55, "velocity": 70, "confidence": 0.7},
            {"start": 0.02, "duration": 0.1, "midi_note": 43, "velocity": 65, "confidence": 0.7},
            {"start": 0.26, "duration": 0.1, "midi_note": 43, "velocity": 60, "confidence": 0.7},
            {"start": 0.52, "duration": 0.1, "midi_note": 67, "velocity": 80, "confidence": 0.7},
        ]

        bassline = _extract_bassline(events)

        self.assertEqual(len(bassline), 1)
        self.assertEqual(bassline[0]["midi_note"], 43)
        self.assertAlmostEqual(bassline[0]["duration"], 0.5)

    def test_exports_promote_only_recommended_midi_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            midi_files = {}
            assets = []
            for key in [
                "reference_sketch",
                "model_transcription",
                "source_bass_transcription",
                "source_drum_groove",
                "model_bass_transcription",
            ]:
                path = os.path.join(temp_dir, f"{key}.mid")
                with open(path, "wb") as midi_file:
                    midi_file.write(b"MThd" + bytes(18))
                midi_files[key] = path
                assets.append(
                    {
                        "key": key,
                        "path": path,
                        "label": key,
                        "kind": "model_transcription",
                        "limitations": [],
                    }
                )

            export_files = _promote_exports(os.path.join(temp_dir, "job"), midi_files, assets)

        assets_by_key = {asset["key"]: asset for asset in assets}
        self.assertIn("model_transcription", export_files)
        self.assertIn("source_bass_transcription", export_files)
        self.assertIn("source_drum_groove", export_files)
        self.assertNotIn("reference_sketch", export_files)
        self.assertNotIn("model_bass_transcription", export_files)
        self.assertTrue(assets_by_key["model_transcription"]["is_recommended_output"])
        self.assertTrue(assets_by_key["source_bass_transcription"]["is_recommended_output"])
        self.assertFalse(assets_by_key["reference_sketch"]["is_recommended_output"])

    def test_reference_transform_keeps_groove_and_replaces_stab_role(self):
        transform = build_reference_transform(
            "keep the banger bass line groove but make it a bit different and replace the main stabbing effect",
            {
                "reference_groove": {
                    "bass_accent_pattern_16th": [3, 7, 8],
                    "kick_pattern_16th": [0, 4, 8],
                    "hat_pattern_16th": [2, 6, 10],
                },
                "bass_transcription": {"event_count": 12},
                "drums": {"method": "onset_detection"},
            },
        )

        self.assertGreaterEqual(transform["groove_similarity"], 0.85)
        self.assertEqual(transform["generation_mode"], "source_conditioned")
        self.assertTrue(transform["bass"]["keep_rhythm"])
        self.assertTrue(transform["bass"]["vary_notes"])
        self.assertLess(transform["bass"]["source_pitch_lock"], transform["bass"]["source_rhythm_lock"])
        self.assertTrue(transform["stab_replacement"]["enabled"])
        self.assertIn("replace the main stab role", transform["prompt"])

    def test_same_groove_different_bass_notes_keeps_rhythm_but_lowers_pitch_lock(self):
        transform = build_reference_transform(
            "same groove, same feeling, same mood, change the bassline notes a little",
            {},
        )
        task_type = _task_type(transform, transform["groove_similarity"])
        conditioning = _source_conditioning(transform, transform["groove_similarity"], is_cover=task_type == "cover")

        self.assertEqual(task_type, "cover")
        self.assertLessEqual(transform["groove_similarity"], 0.82)
        self.assertGreaterEqual(transform["bass"]["source_rhythm_lock"], 0.9)
        self.assertLessEqual(transform["bass"]["source_pitch_lock"], 0.5)
        self.assertGreaterEqual(float(conditioning["reference_strength"]), 0.65)
        self.assertGreaterEqual(float(conditioning["cover_noise_strength"]), 0.1)
        self.assertLessEqual(float(conditioning["cover_noise_strength"]), 0.3)

    def test_reference_difference_can_be_parametrized_by_number_or_percent(self):
        almost_copy = build_reference_transform("100% identical", {})
        ninety = build_reference_transform("90% identical with 10% variation", {})
        different = build_reference_transform("same percussion different bass line notes", {"reference_difference": 7})

        self.assertEqual(_task_type(almost_copy, almost_copy["groove_similarity"]), "cover")
        self.assertGreater(almost_copy["groove_similarity"], ninety["groove_similarity"])
        self.assertGreater(ninety["groove_similarity"], different["groove_similarity"])
        self.assertEqual(_task_type(different, different["groove_similarity"]), "cover")

    def test_named_similarity_levels_replace_percentage_control(self):
        low = build_reference_transform("low similarity, same genre and speed", {})
        medium_low = build_reference_transform("medium-low similarity, keep some reference pocket", {})
        medium = build_reference_transform("medium similarity, keep the pocket", {})
        medium_high = build_reference_transform("medium-high similarity, close but not high", {})
        high = build_reference_transform("high similarity, keep the groove", {})
        near = build_reference_transform("identical similarity with a twist", {})

        self.assertEqual(low["similarity_profile"]["id"], "low")
        self.assertEqual(medium_low["similarity_profile"]["id"], "medium_low")
        self.assertEqual(medium["similarity_profile"]["id"], "medium")
        self.assertEqual(medium_high["similarity_profile"]["id"], "medium_high")
        self.assertEqual(high["similarity_profile"]["id"], "high")
        self.assertEqual(near["similarity_profile"]["id"], "near_identical_twist")
        self.assertLess(low["groove_similarity"], medium_low["groove_similarity"])
        self.assertLess(medium_low["groove_similarity"], medium["groove_similarity"])
        self.assertLess(medium["groove_similarity"], medium_high["groove_similarity"])
        self.assertLess(medium_high["groove_similarity"], high["groove_similarity"])
        self.assertLess(high["groove_similarity"], near["groove_similarity"])
        self.assertLess(near["groove_similarity"], 0.96)

    def test_similarity_level_from_cli_metadata_overrides_prompt(self):
        transform = build_reference_transform(
            "make it high energy with low-end weight",
            {"reference_similarity_level": "high"},
        )

        self.assertEqual(transform["similarity_profile"]["id"], "high")
        self.assertAlmostEqual(transform["groove_similarity"], 0.8)

    def test_low_similarity_still_uses_reference_style_floor(self):
        transform = build_reference_transform(
            "20% similar reference-inspired underground minimal house, same speed and genre but new bass notes",
            {},
        )
        task_type = _task_type(transform, transform["groove_similarity"])
        conditioning = _source_conditioning(transform, transform["groove_similarity"], is_cover=task_type == "cover")

        self.assertAlmostEqual(transform["groove_similarity"], 0.2)
        self.assertEqual(transform["generation_mode"], "source_conditioned")
        self.assertEqual(task_type, "text2music")
        self.assertEqual(float(conditioning["reference_strength"]), 0.0)
        self.assertEqual(float(conditioning["cover_noise_strength"]), 0.0)
        self.assertIn("same BPM", transform["prompt"])

        conditioned = _condition_prompt(
            "20% similar reference-inspired underground minimal house, same speed and genre but new bass notes",
            {},
            transform,
        )
        self.assertNotIn("20% similar", conditioned)
        self.assertNotIn("20 percent", conditioned)
        self.assertIn("same BPM", conditioned)

    def test_named_similarity_levels_map_to_distinct_ace_control_modes(self):
        low = build_reference_transform("", {"reference_similarity_level": "low"})
        medium_low = build_reference_transform("", {"reference_similarity_level": "medium-low"})
        medium = build_reference_transform("", {"reference_similarity_level": "medium"})
        medium_high = build_reference_transform("", {"reference_similarity_level": "medium-high"})
        high = build_reference_transform("", {"reference_similarity_level": "high"})
        near = build_reference_transform("", {"reference_similarity_level": "near-identical"})

        levels = [low, medium_low, medium, medium_high, high, near]
        tasks = [_task_type(transform, transform["groove_similarity"]) for transform in levels]
        conditioning = [
            _source_conditioning(transform, transform["groove_similarity"], is_cover=task == "cover")
            for transform, task in zip(levels, tasks, strict=True)
        ]

        self.assertEqual(tasks[0], "text2music")
        self.assertEqual(tasks[1:], ["cover", "cover", "cover", "cover", "cover"])
        self.assertLess(float(conditioning[1]["reference_strength"]), float(conditioning[2]["reference_strength"]))
        self.assertLess(float(conditioning[2]["reference_strength"]), float(conditioning[3]["reference_strength"]))
        self.assertLess(float(conditioning[3]["reference_strength"]), float(conditioning[4]["reference_strength"]))
        self.assertLess(float(conditioning[4]["reference_strength"]), float(conditioning[5]["reference_strength"]))
        self.assertGreater(
            float(conditioning[5]["reference_strength"]) - float(conditioning[1]["reference_strength"]),
            0.2,
        )
        self.assertIn("micro-percussion", near["prompt"])
        self.assertIn("rhythmic vocal", near["prompt"])

    def test_low_similarity_candidate_selection_prefers_originality(self):
        close_copy = _selection_score(quality_score=0.82, exact_similarity_score=0.72, target_similarity=0.2)
        more_original = _selection_score(quality_score=0.80, exact_similarity_score=0.34, target_similarity=0.2)
        high_similarity_copy = _selection_score(quality_score=0.82, exact_similarity_score=0.72, target_similarity=0.8)
        high_similarity_loose = _selection_score(quality_score=0.80, exact_similarity_score=0.34, target_similarity=0.8)

        self.assertGreater(more_original, close_copy)
        self.assertGreater(high_similarity_copy, high_similarity_loose)

    def test_candidate_selection_can_be_overridden_after_listening(self):
        previous = os.environ.get("PROMPT2MIDI_ACE_STEP_SELECT_CANDIDATE")
        os.environ["PROMPT2MIDI_ACE_STEP_SELECT_CANDIDATE"] = "2"
        try:
            selected, selected_by = _choose_candidate([
                {"path": "candidate-1.wav", "quality": {"score": 0.9}},
                {"path": "candidate-2.wav", "quality": {"score": 0.5}},
            ])
        finally:
            if previous is None:
                os.environ.pop("PROMPT2MIDI_ACE_STEP_SELECT_CANDIDATE", None)
            else:
                os.environ["PROMPT2MIDI_ACE_STEP_SELECT_CANDIDATE"] = previous

        self.assertEqual(selected["path"], "candidate-2.wav")
        self.assertEqual(selected_by, "manual_candidate_override")

    def test_candidates_await_user_selection_by_default(self):
        previous = os.environ.get("PROMPT2MIDI_ACE_STEP_SELECT_CANDIDATE")
        previous_auto = os.environ.get("PROMPT2MIDI_ACE_STEP_AUTO_SELECT")
        os.environ.pop("PROMPT2MIDI_ACE_STEP_SELECT_CANDIDATE", None)
        os.environ.pop("PROMPT2MIDI_ACE_STEP_AUTO_SELECT", None)
        try:
            selected, selected_by = _select_candidate_for_promotion([
                {"path": "candidate-1.wav", "quality": {"score": 0.9}},
                {"path": "candidate-2.wav", "quality": {"score": 0.5}},
            ])
            suggested, suggested_by = _choose_candidate([
                {"path": "candidate-1.wav", "quality": {"score": 0.9}},
                {"path": "candidate-2.wav", "quality": {"score": 0.5}},
            ])
        finally:
            if previous is not None:
                os.environ["PROMPT2MIDI_ACE_STEP_SELECT_CANDIDATE"] = previous
            if previous_auto is not None:
                os.environ["PROMPT2MIDI_ACE_STEP_AUTO_SELECT"] = previous_auto

        self.assertIsNone(selected)
        self.assertEqual(selected_by, "awaiting_user_selection")
        self.assertEqual(suggested["path"], "candidate-1.wav")
        self.assertEqual(suggested_by, "quality_rank_only")

    def test_reference_transform_uses_detected_style_instead_of_house_default(self):
        transform = build_reference_transform(
            "20% similar, same speed and genre but different bassline",
            {
                "bpm": 118,
                "key": "C# minor",
                "genre_deep": {
                    "primary": "dance pop",
                    "tags": ["dance pop", "funk", "synth pop"],
                    "confidence": 0.42,
                },
                "groove": {"description": "tight syncopated funk-pop groove"},
            },
        )
        conditioned = _condition_prompt("20% similar, same speed and genre but different bassline", {}, transform)

        self.assertIn("dance pop", transform["style_brief"])
        self.assertIn("C# minor", transform["style_brief"])
        self.assertIn("dance pop", conditioned)
        self.assertNotIn("underground minimal house", conditioned)

    def test_similarity_percentage_stays_out_of_model_prompt_text(self):
        transform = build_reference_transform("90% similar with 10% variation, same groove", {})
        conditioned = _condition_prompt("90% similar with 10% variation, same groove", {}, transform)

        self.assertIn("same groove", conditioned)
        self.assertNotIn("90% similar", conditioned)
        self.assertNotIn("10% variation", conditioned)
        self.assertNotIn("percent copying similarity", conditioned)
        self.assertEqual(_sanitize_user_prompt_for_model("90% similar with 10% variation, same groove"), "same groove")
        self.assertEqual(_sanitize_user_prompt_for_model("high similarity, same groove"), "same groove")
        self.assertEqual(_sanitize_user_prompt_for_model("medium-high similarity: same groove"), "same groove")
        self.assertEqual(_sanitize_user_prompt_for_model("medium-low similarity: same groove"), "same groove")

    def test_unavailable_reference_groove_does_not_score_as_perfect_match(self):
        score = score_groove_similarity({"method": "unavailable", "warnings": ["skipped"]}, "missing.wav", 120)

        self.assertEqual(score["score"], 0.0)
        self.assertIn("skipped", score["warnings"])

    def test_drum_pattern_to_midi_events_creates_drum_channel_events(self):
        events = drum_pattern_to_midi_events(
            {"kick": [0, 8], "snare": [4], "hat": [2, 6], "method": "onset_detection"},
            bpm=120,
            bars=1,
        )

        notes = [event["midi_note"] for event in events]
        self.assertEqual(notes.count(36), 2)
        self.assertIn(38, notes)
        self.assertEqual({event["channel"] for event in events}, {9})

    def test_explicit_tech_house_direction_overrides_funky_keyword(self):
        style = _composition_style(
            {
                "user_direction": (
                    "groove-led tech house, minimal deep tech, Chicago-influenced house, "
                    "rolling bassline, tribal-funky percussion"
                ),
                "genre_deep": {"primary": "breakbeat", "confidence": 0.4},
                "bpm": 126,
            }
        )

        self.assertEqual(style, "house")

    @staticmethod
    def _write_pulsed_wav(path: str, bpm: int):
        sample_rate = 8000
        seconds = 4
        beat_interval = 60.0 / bpm
        samples = []
        for index in range(sample_rate * seconds):
            time = index / sample_rate
            beat_phase = time % beat_interval
            envelope = 1.0 if beat_phase < 0.06 else 0.08
            tone = math.sin(2 * math.pi * 220 * time)
            samples.append(int(max(-1.0, min(1.0, envelope * tone)) * 32767))

        with wave.open(path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b"".join(struct.pack("<h", sample) for sample in samples))

    @staticmethod
    def _write_bass_pattern_wav(path: str):
        sample_rate = 8000
        note_frequencies = [65.406, 97.999, 110.0, 87.307]
        samples = []
        for frequency in note_frequencies:
            for index in range(sample_rate):
                time = index / sample_rate
                envelope = 0.9 if index < sample_rate * 0.85 else 0.2
                tone = math.sin(2 * math.pi * frequency * time)
                samples.append(int(envelope * tone * 32767))

        with wave.open(path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b"".join(struct.pack("<h", sample) for sample in samples))

    @staticmethod
    def _write_fake_basic_pitch(path: str, calls_path: str):
        script = f"""#!/usr/bin/env python3
import csv
import os
import sys

out_dir = sys.argv[1]
audio_path = sys.argv[2]
os.makedirs(out_dir, exist_ok=True)
with open({calls_path!r}, "a") as calls:
    calls.write(audio_path + "\\n")
with open(os.path.join(out_dir, "fake.mid"), "wb") as midi:
    midi.write(b"MThd" + bytes(18))
with open(os.path.join(out_dir, "fake.csv"), "w", newline="") as csv_file:
    writer = csv.DictWriter(csv_file, fieldnames=["start_time_s", "end_time_s", "pitch_midi", "velocity"])
    writer.writeheader()
    writer.writerow({{"start_time_s": "0.0", "end_time_s": "0.4", "pitch_midi": "43", "velocity": "80"}})
    writer.writerow({{"start_time_s": "0.5", "end_time_s": "0.9", "pitch_midi": "47", "velocity": "75"}})
"""
        with open(path, "w") as script_file:
            script_file.write(script)
        os.chmod(path, 0o755)


if __name__ == "__main__":
    unittest.main()
