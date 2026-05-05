import json
import math
import os
import struct
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(__file__))

from feature_extraction import analyze_wav
from full_arrangement import build_arrangement_map, build_full_arrangement_package
from full_guide_audio import generate_full_arrangement_guide_audio
from external_analyzers import analyze_allin1_structure, analyze_essentia_descriptors
from analyze import _promote_exports, _prompt_vocal_hint, _reference_sample_duration, run as run_analysis
from audio_generation import _condition_prompt, _sanitize_user_prompt_for_model, _should_use_control_scaffold
from ace_preflight import build_ace_preflight
from ace_step_generation import (
    _apply_level_quality_gate,
    _build_payload,
    _choose_candidate,
    _caption,
    _explicit_layer_requests,
    _select_candidate_for_promotion,
    _selection_score,
    _source_conditioning,
    _suggest_candidate,
    _task_type,
)
from bass_transcription import transcribe_bassline
from composition import _composition_style
from drum_analysis import drum_pattern_to_midi_events
from midi_extraction import write_note_events_midi, write_reference_sketch_midi
from reference_transform import build_reference_transform
from reference_groove import _analyze_reference_groove_safe, score_groove_similarity
from source_transcription import _extract_bassline, transcribe_with_model
from stem_separation import separate_for_transcription
from vocal_analysis import analyze_vocal_role


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
        self.assertIn("full_arrangement", result)
        full = result["full_arrangement"]
        self.assertEqual(full["status"], "ready")
        self.assertGreaterEqual(full["total_bars"], 1)
        self.assertTrue(full["paths"]["arrangement_map"].endswith("arrangement-map.json"))
        self.assertTrue(full["paths"]["analysis_report"].endswith("analysis-report.md"))
        self.assertTrue(full["paths"]["suno_structure_prompt"].endswith("suno-structure-prompt.md"))
        self.assertTrue(full["paths"]["full_arrangement_guide_midi"].endswith("full-arrangement-guide.mid"))

    def test_full_arrangement_package_writes_suno_structure_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            analysis = {
                "duration_seconds": 180.0,
                "bpm": 120.0,
                "bpm_confidence": 0.8,
                "key": "A minor",
                "key_confidence": 0.7,
                "genre": {"primary": "Tech House", "tags": ["tech house", "minimal"], "confidence": 0.6},
                "groove": {"description": "tight rolling club groove"},
                "structure": {
                    "method": "test_sections",
                    "sections": [
                        {"start": 0.0, "end": 32.0, "label": "intro", "energy": 0.25},
                        {"start": 32.0, "end": 96.0, "label": "groove", "energy": 0.8},
                        {"start": 96.0, "end": 128.0, "label": "breakdown", "energy": 0.15},
                        {"start": 128.0, "end": 180.0, "label": "drop", "energy": 0.95},
                    ],
                },
            }

            package = build_full_arrangement_package(
                analysis,
                temp_dir,
                user_prompt="darker bass, less vocal texture",
                similarity_level="medium_high",
            )

            with open(package["paths"]["arrangement_map"], encoding="utf-8") as handle:
                arrangement = json.load(handle)
            with open(package["paths"]["analysis_report"], encoding="utf-8") as handle:
                report = handle.read()
            with open(package["paths"]["suno_structure_prompt"], encoding="utf-8") as handle:
                prompt = handle.read()

        self.assertEqual(package["status"], "ready")
        self.assertEqual(arrangement["similarity_level"], "medium_high")
        self.assertGreaterEqual(arrangement["total_bars"], 80)
        self.assertEqual(arrangement["sections"][0]["role"], "intro")
        self.assertIn("Arrangement Map", report)
        self.assertIn("Use the attached ACE guide audio", prompt)
        self.assertIn("darker bass", prompt)

    def test_arrangement_map_falls_back_to_bar_grid_without_structure_model(self):
        arrangement = build_arrangement_map(
            {
                "duration_seconds": 240.0,
                "bpm": 120.0,
                "key": "C minor",
                "structure": {"sections": []},
            },
            similarity_level="low",
        )

        self.assertEqual(arrangement["method"], "fallback_bar_grid")
        self.assertEqual(arrangement["similarity_level"], "low")
        self.assertEqual(arrangement["sections"][0]["start_bar"], 1)
        self.assertEqual(arrangement["sections"][-1]["end_bar"], arrangement["total_bars"])
        self.assertTrue(any(section["role"] == "breakdown" for section in arrangement["sections"]))

    def test_external_analyzers_degrade_when_disabled(self):
        old_allin1 = os.environ.get("PROMPT2MIDI_DISABLE_ALLIN1")
        old_essentia = os.environ.get("PROMPT2MIDI_DISABLE_ESSENTIA")
        os.environ["PROMPT2MIDI_DISABLE_ALLIN1"] = "1"
        os.environ["PROMPT2MIDI_DISABLE_ESSENTIA"] = "1"
        try:
            allin1 = analyze_allin1_structure("unused.wav", "/tmp")
            essentia = analyze_essentia_descriptors("unused.wav", "/tmp")
        finally:
            if old_allin1 is None:
                os.environ.pop("PROMPT2MIDI_DISABLE_ALLIN1", None)
            else:
                os.environ["PROMPT2MIDI_DISABLE_ALLIN1"] = old_allin1
            if old_essentia is None:
                os.environ.pop("PROMPT2MIDI_DISABLE_ESSENTIA", None)
            else:
                os.environ["PROMPT2MIDI_DISABLE_ESSENTIA"] = old_essentia

        self.assertFalse(allin1["available"])
        self.assertFalse(essentia["available"])
        self.assertIn("disabled", allin1["warnings"][0])
        self.assertIn("disabled", essentia["warnings"][0])

    def test_full_guide_audio_is_disabled_by_default(self):
        result = generate_full_arrangement_guide_audio(
            reference_audio="unused.wav",
            output_dir="/tmp",
            analysis={},
            full_arrangement={"sections": [{"start_seconds": 0, "end_seconds": 8, "role": "intro"}]},
            user_prompt="",
        )

        self.assertEqual(result["status"], "not_generated")
        self.assertIn("PROMPT2MIDI_ENABLE_FULL_ACE_GUIDE", result["reason"])

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
        very_high = build_reference_transform("very high similarity, close but not copied", {})
        near = build_reference_transform("identical similarity with a twist", {})

        self.assertEqual(low["similarity_profile"]["id"], "low")
        self.assertEqual(medium_low["similarity_profile"]["id"], "medium_low")
        self.assertEqual(medium["similarity_profile"]["id"], "medium")
        self.assertEqual(medium_high["similarity_profile"]["id"], "medium_high")
        self.assertEqual(high["similarity_profile"]["id"], "high")
        self.assertEqual(very_high["similarity_profile"]["id"], "very_high")
        self.assertEqual(near["similarity_profile"]["id"], "near_identical_twist")
        self.assertLess(low["groove_similarity"], medium_low["groove_similarity"])
        self.assertLess(medium_low["groove_similarity"], medium["groove_similarity"])
        self.assertLess(medium["groove_similarity"], medium_high["groove_similarity"])
        self.assertLess(medium_high["groove_similarity"], high["groove_similarity"])
        self.assertLess(high["groove_similarity"], very_high["groove_similarity"])
        self.assertLess(very_high["groove_similarity"], near["groove_similarity"])
        self.assertLess(high["groove_similarity"], near["groove_similarity"])
        self.assertLess(near["groove_similarity"], 0.96)

    def test_similarity_level_from_cli_metadata_overrides_prompt(self):
        transform = build_reference_transform(
            "make it high energy with low-end weight",
            {"reference_similarity_level": "high"},
        )

        self.assertEqual(transform["similarity_profile"]["id"], "high")
        self.assertAlmostEqual(transform["groove_similarity"], 0.52)

    def test_low_similarity_still_uses_reference_style_floor(self):
        transform = build_reference_transform(
            "20% similar reference-inspired underground minimal house, same speed and genre but new bass notes",
            {},
        )
        task_type = _task_type(transform, transform["groove_similarity"])
        conditioning = _source_conditioning(transform, transform["groove_similarity"], is_cover=task_type == "cover")

        self.assertAlmostEqual(transform["groove_similarity"], 0.2)
        self.assertEqual(transform["generation_mode"], "source_conditioned")
        self.assertEqual(task_type, "cover")
        self.assertGreaterEqual(float(conditioning["reference_strength"]), 0.2)
        self.assertGreaterEqual(float(conditioning["cover_noise_strength"]), 0.1)
        self.assertLessEqual(float(conditioning["reference_strength"]), 0.3)
        self.assertLessEqual(float(conditioning["cover_noise_strength"]), 0.18)
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

        self.assertEqual(tasks, ["cover", "cover", "cover", "cover", "cover", "cover"])
        self.assertLess(float(conditioning[1]["reference_strength"]), float(conditioning[2]["reference_strength"]))
        self.assertLess(float(conditioning[2]["reference_strength"]), float(conditioning[3]["reference_strength"]))
        self.assertLess(float(conditioning[3]["reference_strength"]), float(conditioning[4]["reference_strength"]))
        self.assertLess(float(conditioning[4]["reference_strength"]), float(conditioning[5]["reference_strength"]))
        self.assertGreater(
            float(conditioning[5]["reference_strength"]) - float(conditioning[3]["reference_strength"]),
            0.45,
        )
        self.assertIn("micro-percussion", near["prompt"])
        self.assertIn("rhythmic vocal", near["prompt"])
        self.assertTrue(high["bass"]["vary_notes"])
        self.assertTrue(medium_high["bass"]["vary_notes"])
        self.assertLess(medium_high["bass"]["source_pitch_lock"], high["bass"]["source_pitch_lock"])
        self.assertLess(high["bass"]["source_pitch_lock"], near["bass"]["source_pitch_lock"])
        self.assertIn("must still be audibly changed", high["prompt"])
        self.assertIn("audibly different", medium_high["prompt"])
        self.assertAlmostEqual(float(conditioning[0]["reference_strength"]), 0.21)
        self.assertAlmostEqual(float(conditioning[0]["cover_noise_strength"]), 0.11)
        self.assertGreater(low["bass"]["variation_amount"], medium["bass"]["variation_amount"])
        self.assertIn("style, energy, BPM", low["prompt"])
        self.assertIn("signature sounds", low["prompt"])

    def test_tribal_percussion_prompt_is_promoted_to_ace_priority_layer(self):
        prompt = (
            "continuous fast tribal percussion, loud congas and bongos, shakers, tambourine, "
            "clave, wood hits, and toms over a house groove"
        )

        requested = _explicit_layer_requests(prompt)

        self.assertIn("continuous loud fast tribal percussion", requested)
        self.assertIn("first bar to last bar", requested)
        self.assertIn("congas", requested)

    def test_very_high_profile_sits_between_high_and_near_identical(self):
        high = build_reference_transform("", {"reference_similarity_level": "high"})
        very_high = build_reference_transform("", {"reference_similarity_level": "very-high"})
        near = build_reference_transform("", {"reference_similarity_level": "near-identical"})
        high_task = _task_type(high, high["groove_similarity"])
        very_task = _task_type(very_high, very_high["groove_similarity"])
        near_task = _task_type(near, near["groove_similarity"])
        high_controls = _source_conditioning(high, high["groove_similarity"], is_cover=high_task == "cover")
        very_controls = _source_conditioning(very_high, very_high["groove_similarity"], is_cover=very_task == "cover")
        near_controls = _source_conditioning(near, near["groove_similarity"], is_cover=near_task == "cover")

        self.assertEqual(very_high["similarity_profile"]["id"], "very_high")
        self.assertGreater(very_high["groove_similarity"], high["groove_similarity"])
        self.assertLess(very_high["groove_similarity"], near["groove_similarity"])
        self.assertGreater(float(very_controls["reference_strength"]), float(high_controls["reference_strength"]))
        self.assertLess(float(very_controls["reference_strength"]), float(near_controls["reference_strength"]))
        self.assertIn("reference-locked", very_high["prompt"])

    def test_ace_preflight_flags_rich_vocal_reference_for_yue(self):
        analysis = {
            "reference_similarity_level": "medium",
            "bpm": 118.0,
            "bpm_confidence": 0.8,
            "key": "C minor",
            "genre": {"primary": "dance pop / funk", "tags": ["dance pop", "funk", "soul"], "confidence": 0.7},
            "chords": {"confidence": 0.85, "progression": ["Cm", "Ab", "Eb", "Bb", "Fm", "Gm"]},
            "vocals": {"available": True, "present": True, "role": "lead vocal hook", "confidence": 0.9},
        }
        transform = build_reference_transform("same groove but new vocal hook", analysis)
        preflight = build_ace_preflight(analysis, transform, "same groove but new vocal hook")

        self.assertIn(preflight["ace_suitability"], {"low", "medium-low"})
        self.assertIn("yue", preflight["recommended_generator"])
        self.assertTrue(any(risk["code"] == "lead_vocal_or_hook" for risk in preflight["risk_reasons"]))
        self.assertIn("RunPod YuE", preflight["message"])

    def test_ace_preflight_accepts_groove_driven_house_reference(self):
        analysis = {
            "reference_similarity_level": "low",
            "bpm": 126.0,
            "bpm_confidence": 0.85,
            "key": "C minor",
            "genre": {"primary": "minimal tech house", "tags": ["minimal house", "tech house", "club"], "confidence": 0.8},
            "chords": {"confidence": 0.4, "progression": ["Cm", "Cm", "Ab", "Cm"]},
            "vocals": {"available": False, "present": False, "role": "none", "confidence": 0.0},
        }
        transform = build_reference_transform("same energy, new bassline", analysis)
        preflight = build_ace_preflight(analysis, transform, "same energy, new bassline")

        self.assertIn(preflight["ace_suitability"], {"high", "medium"})
        self.assertEqual(preflight["recommended_generator"], "ace_step")
        self.assertEqual(preflight["hidden_controls"]["route"], "source_conditioned_cover")
        self.assertGreaterEqual(preflight["hidden_controls"]["reference_strength"], 0.18)

    def test_ace_preflight_hidden_controls_override_near_identical_copy_pressure(self):
        analysis = {
            "reference_similarity_level": "near-identical",
            "bpm": 126.0,
            "bpm_confidence": 0.8,
            "key": "C minor",
            "genre": {"primary": "electro house", "tags": ["electro house", "club"], "confidence": 0.75},
            "vocals": {"available": True, "present": True, "role": "lead vocal hook", "confidence": 0.82},
        }
        transform = build_reference_transform("very close but do not copy the original singer", analysis)
        preflight = build_ace_preflight(analysis, transform, "very close but do not copy the original singer")
        transform["ace_preflight"] = preflight
        conditioning = _source_conditioning(transform, transform["groove_similarity"], is_cover=True)

        self.assertEqual(preflight["hidden_controls"]["recommended_profile"], "very_high_reference_locked")
        self.assertLess(float(conditioning["reference_strength"]), 0.72)
        self.assertLess(float(conditioning["cover_noise_strength"]), 0.48)

    def test_bass_rhythm_sound_lock_keeps_source_conditioning_stronger(self):
        analysis = {
            "reference_similarity_level": "near-identical",
            "bpm": 126.0,
            "bpm_confidence": 0.82,
            "key": "C minor",
            "genre": {"primary": "electro house", "tags": ["electro house", "club"], "confidence": 0.75},
            "chords": {"confidence": 0.8, "progression": ["Cm", "Ab", "Bb", "Gm", "Fm"]},
            "vocals": {"available": True, "present": True, "role": "lead vocal hook", "confidence": 0.8},
        }
        prompt = "same bass line rhythm and same bassline sound but different notes"
        transform = build_reference_transform(prompt, analysis)
        preflight = build_ace_preflight(analysis, transform, prompt)
        transform["ace_preflight"] = preflight
        conditioning = _source_conditioning(transform, transform["groove_similarity"], is_cover=True)
        conditioned = _condition_prompt(prompt, {}, transform)
        payload = _build_payload(
            reference_audio=__file__,
            prompt=conditioned,
            analysis={**analysis, "reference_transform": transform, "ace_preflight": preflight},
            duration_seconds=15,
            candidate_count=1,
            model="test-model",
        )

        self.assertTrue(transform["bass"]["preserve_sound_design"])
        self.assertTrue(transform["bass"]["vary_notes"])
        self.assertGreaterEqual(transform["bass"]["source_rhythm_lock"], 0.95)
        self.assertEqual(preflight["hidden_controls"]["route"], "source_conditioned_cover_bass_locked")
        self.assertEqual(preflight["hidden_controls"]["bass_lock_mode"], "same_rhythm_same_sound_different_notes")
        self.assertGreaterEqual(float(conditioning["reference_strength"]), 0.46)
        self.assertGreaterEqual(float(conditioning["cover_noise_strength"]), 0.18)
        self.assertIn("same bassline rhythm", conditioned)
        self.assertIn("avoid glitchy bass", payload["prompt"])
        self.assertIn("glitchy bass", payload["lm_negative_prompt"])
        self.assertAlmostEqual(payload["reference_similarity"], preflight["hidden_controls"]["recommended_similarity"])
        self.assertFalse(_should_use_control_scaffold(transform, prompt))

    def test_control_scaffold_is_explicit_only(self):
        previous = os.environ.get("PROMPT2MIDI_ACE_STEP_CONTROL_SCAFFOLD")
        try:
            os.environ["PROMPT2MIDI_ACE_STEP_CONTROL_SCAFFOLD"] = "1"
            self.assertTrue(_should_use_control_scaffold({}, "same bassline rhythm"))
        finally:
            if previous is None:
                os.environ.pop("PROMPT2MIDI_ACE_STEP_CONTROL_SCAFFOLD", None)
            else:
                os.environ["PROMPT2MIDI_ACE_STEP_CONTROL_SCAFFOLD"] = previous

    def test_safe_reference_groove_extracts_bass_grid_for_fast_lane(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = os.path.join(temp_dir, "running-bass.wav")
            self._write_running_bass_wav(wav_path, bpm=120)

            groove = _analyze_reference_groove_safe(wav_path, 120.0, {"path": wav_path, "start_seconds": 0.0})
            transform = build_reference_transform(
                "same bass line rhythm and same bassline sound but different notes",
                {
                    "reference_similarity_level": "high",
                    "bpm": 120.0,
                    "key": "C minor",
                    "genre": {"primary": "electro house", "tags": ["electro house", "club"]},
                    "vocals": {"present": False},
                },
            )
            conditioned = _condition_prompt(
                "same bass line rhythm and same bassline sound but different notes",
                groove,
                transform,
            )

        self.assertEqual(groove["method"], "safe_fft_band_groove_fingerprint")
        self.assertTrue(groove["bass_accent_pattern_16th"])
        self.assertIn("bass accents", groove["prompt"])
        self.assertIn("bass rhythm accents", conditioned)
        self.assertIn("same bassline rhythm", conditioned)

    def test_chord_root_can_correct_wrong_detected_key_for_ace_payload(self):
        analysis = {
            "reference_similarity_level": "high",
            "bpm": 126.0,
            "key": "C minor",
            "genre": {"primary": "electro house", "tags": ["electro house", "club"], "confidence": 0.75},
            "chords": {
                "confidence": 0.82,
                "progression": ["C#", "G#", "C#", "F#", "C#", "A", "C#", "G#", "C#", "D#"],
            },
            "vocals": {"present": False},
        }
        transform = build_reference_transform("same bass line rhythm and same bassline sound but different notes", analysis)
        analysis["reference_transform"] = transform
        payload = _build_payload(
            reference_audio=__file__,
            prompt="same bass line rhythm and same bassline sound but different notes",
            analysis=analysis,
            duration_seconds=15,
            candidate_count=1,
            model="test-model",
        )

        self.assertEqual(transform["harmonic"]["key"], "C# minor")
        self.assertEqual(payload["key_scale"], "C# Minor")

    def test_medium_high_uses_previous_accepted_medium_low_anchor(self):
        medium_high = build_reference_transform("", {"reference_similarity_level": "medium-high"})
        task = _task_type(medium_high, medium_high["groove_similarity"])
        conditioning = _source_conditioning(medium_high, medium_high["groove_similarity"], is_cover=task == "cover")

        self.assertEqual(task, "cover")
        self.assertAlmostEqual(medium_high["groove_similarity"], 0.4)
        self.assertAlmostEqual(float(conditioning["reference_strength"]), 0.2)
        self.assertAlmostEqual(float(conditioning["cover_noise_strength"]), 0.1)
        self.assertGreaterEqual(medium_high["bass"]["variation_amount"], 0.55)
        self.assertIn("calibrated medium-high anchor", medium_high["prompt"])

    def test_low_and_medium_low_similarity_prompts_stay_musical(self):
        low = build_reference_transform("", {"reference_similarity_level": "low"})
        medium_low = build_reference_transform("", {"reference_similarity_level": "medium-low"})

        self.assertIn("staying tonal", low["prompt"])
        self.assertIn("style-usable", low["prompt"])
        self.assertIn("producer-clean", low["prompt"])
        self.assertIn("robotic", low["prompt"])
        self.assertIn("club-focused", medium_low["prompt"])
        self.assertIn("same genre", medium_low["prompt"])

    def test_vocal_reference_preserves_new_vocal_hook_role(self):
        analysis = {
            "reference_similarity_level": "low",
            "bpm": 126.0,
            "key": "C minor",
            "genre": {"primary": "electro house", "tags": ["electro house", "club"], "confidence": 0.7},
            "vocals": {"available": True, "present": True, "role": "lead vocal hook", "confidence": 0.82},
        }
        transform = build_reference_transform("electronic house club track", analysis)
        analysis["reference_transform"] = transform

        conditioned = _condition_prompt("electronic house club track", {}, transform)
        caption = _caption("electronic house club track", analysis)
        payload = _build_payload(
            reference_audio=__file__,
            prompt="electronic house club track",
            analysis=analysis,
            duration_seconds=15,
            candidate_count=1,
            model="test-model",
        )

        self.assertTrue(transform["vocals"]["preserve_role"])
        self.assertTrue(transform["harmonic"]["strict_scale"])
        self.assertIn("inside C minor", transform["prompt"])
        self.assertIn("lead vocal hook", transform["prompt"])
        self.assertIn("original words", conditioned)
        self.assertIn("inside C minor", conditioned)
        self.assertIn("new lead vocal hook", caption)
        self.assertIn("inside C minor", caption)
        self.assertFalse(payload["instrumental"])
        self.assertNotEqual(payload["lyrics"], "[Instrumental]")
        self.assertNotIn("lead vocals, lyrical singing", payload["lm_negative_prompt"])
        self.assertIn("copied lyrics", payload["lm_negative_prompt"])
        self.assertIn("out-of-scale lead notes", payload["lm_negative_prompt"])

    def test_reconstruction_diagnostic_payload_bypasses_anti_copy_guards(self):
        previous = {
            key: os.environ.get(key)
            for key in (
                "PROMPT2MIDI_ACE_STEP_RECONSTRUCTION_DIAGNOSTIC",
                "PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH",
                "PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH",
            )
        }
        try:
            os.environ["PROMPT2MIDI_ACE_STEP_RECONSTRUCTION_DIAGNOSTIC"] = "1"
            os.environ.pop("PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH", None)
            os.environ.pop("PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH", None)
            analysis = {
                "reference_similarity_level": "near-identical",
                "bpm": 120.0,
                "key": "F major",
                "genre": {"primary": "dance-pop", "tags": ["dance-pop", "club"], "confidence": 0.7},
                "vocals": {"present": False},
            }
            analysis["reference_transform"] = build_reference_transform("near identical", analysis)

            payload = _build_payload(
                reference_audio=__file__,
                prompt="Add loud tribal percussion",
                analysis=analysis,
                duration_seconds=15,
                candidate_count=1,
                model="test-model",
            )

            self.assertTrue(payload["reconstruction_diagnostic"])
            self.assertEqual(payload["task_type"], "cover")
            self.assertEqual(payload["audio_cover_strength"], 1.0)
            self.assertEqual(payload["cover_noise_strength"], 1.0)
            self.assertEqual(payload["reference_similarity"], 1.0)
            self.assertIn("local diagnostic reconstruction", payload["prompt"])
            self.assertIn("tribal percussion", payload["prompt"])
            self.assertNotIn("copied hook", payload["lm_negative_prompt"])
            self.assertNotIn("exact original bass pitch sequence", payload["lm_negative_prompt"])
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_reconstruction_diagnostic_respects_closeness_sliders(self):
        previous = {
            key: os.environ.get(key)
            for key in (
                "PROMPT2MIDI_ACE_STEP_RECONSTRUCTION_DIAGNOSTIC",
                "PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH",
                "PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH",
            )
        }
        try:
            os.environ["PROMPT2MIDI_ACE_STEP_RECONSTRUCTION_DIAGNOSTIC"] = "1"
            os.environ["PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH"] = "0.7"
            os.environ["PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH"] = "0.5"
            analysis = {
                "reference_similarity_level": "near-identical",
                "bpm": 120.0,
                "key": "F major",
                "genre": {"primary": "dance-pop", "tags": ["dance-pop", "club"], "confidence": 0.7},
                "vocals": {"present": False},
            }
            analysis["reference_transform"] = build_reference_transform("near identical", analysis)

            payload = _build_payload(
                reference_audio=__file__,
                prompt="same tempo and key area as the reference.",
                analysis=analysis,
                duration_seconds=15,
                candidate_count=1,
                model="test-model",
            )

            self.assertTrue(payload["reconstruction_diagnostic"])
            self.assertEqual(payload["audio_cover_strength"], 0.7)
            self.assertEqual(payload["cover_noise_strength"], 0.5)
            self.assertEqual(payload["reference_similarity"], 0.7)
            self.assertIn("strong source-guided diagnostic variation", payload["prompt"])
            self.assertIn("do not make a literal reconstruction", payload["prompt"])
            self.assertNotIn("match its groove, timing, arrangement shape, instrument balance, timbre family, dynamics, and mix energy as closely as ACE can", payload["prompt"])
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_fast_lane_conditional_vocal_wording_does_not_force_vocal_resynthesis(self):
        vocal_hint = _prompt_vocal_hint("new synth or vocal hook if reference has vocals")
        self.assertFalse(vocal_hint["present"])

        analysis = {
            "reference_similarity_level": "low",
            "bpm": 120.0,
            "key": "F major",
            "genre": {"primary": "Electronic (120-135 BPM)", "tags": ["electronic", "4/4", "club"], "confidence": 0.2},
            "genre_deep": {"primary": "breakbeat", "tags": ["breakbeat", "classic rock"], "confidence": 0.02},
            "groove": {"description": "minimal steady groove"},
            "vocals": vocal_hint,
        }
        transform = build_reference_transform("new synth or vocal hook if reference has vocals", analysis)
        analysis["reference_transform"] = transform
        payload = _build_payload(
            reference_audio=__file__,
            prompt="new synth or vocal hook if reference has vocals",
            analysis=analysis,
            duration_seconds=15,
            candidate_count=1,
            model="test-model",
        )

        self.assertEqual(transform["style"]["primary"], "Electronic (120-135 BPM)")
        self.assertNotIn("breakbeat", transform["style_brief"])
        self.assertFalse(transform["vocals"]["preserve_role"])
        self.assertTrue(payload["instrumental"])
        self.assertEqual(payload["lyrics"], "[Instrumental]")

    def test_explicit_added_layers_are_promoted_in_ace_caption(self):
        analysis = {
            "reference_similarity_level": "medium-high",
            "bpm": 129.2,
            "key": "G# major",
            "genre": {"primary": "Electronic (120-135 BPM)", "tags": ["electronic", "4/4", "club"], "confidence": 0.7},
            "groove": {"feel": "balanced"},
            "vocals": {"available": True, "present": True, "role": "lead vocal hook", "confidence": 0.8},
        }
        prompt = "same tempo and key area as the reference. add vocal chops and a cow bell"
        transform = build_reference_transform(prompt, analysis)
        analysis["reference_transform"] = transform
        caption = _caption(prompt, analysis)

        self.assertIn("requested added layers", caption)
        self.assertIn("cowbell percussion layer", caption)
        self.assertIn("short non-lyrical vocal chops", caption)
        self.assertIn("clearly audible", caption)

    def test_explicit_added_layers_survive_long_user_prompt(self):
        analysis = {
            "reference_similarity_level": "low",
            "bpm": 129.2,
            "key": "G# major",
            "genre": {"primary": "Electronic (120-135 BPM)", "tags": ["electronic", "4/4", "club"], "confidence": 0.7},
            "groove": {"feel": "balanced"},
            "vocals": {"available": True, "present": True, "role": "lead vocal hook", "confidence": 0.8},
        }
        prompt = (
            "Keep the same BPM, key area, 4/4 club pulse, bass weight, and underground house energy as the reference. "
            + "Make this version percussion-led with a syncopated 16th-note groove. " * 20
            + "Add a bright dry cowbell and short non-lyrical vocal chops as rhythmic percussion stabs."
        )
        transform = build_reference_transform(prompt, analysis)
        analysis["reference_transform"] = transform
        caption = _caption(prompt, analysis)

        self.assertLessEqual(len(caption), 1300)
        self.assertLess(caption.index("cowbell percussion layer"), caption.index("user direction:"))
        self.assertIn("short non-lyrical vocal chops", caption)

    def test_unreliable_low_vocal_reference_uses_text_only_instrumental_hook_proxy(self):
        analysis = {
            "reference_similarity_level": "low",
            "bpm": 126.0,
            "key": "C minor",
            "genre": {"primary": "electro house", "tags": ["electro house", "club"], "confidence": 0.7},
            "vocals": {"available": False, "present": True, "role": "lead vocal hook", "confidence": 0.55, "method": "user_direction_hint"},
        }
        prompt = "electronic house club track with hook character, no lead vocal resynthesis"
        transform = build_reference_transform(prompt, analysis)
        analysis["reference_transform"] = transform
        conditioned = _condition_prompt(prompt, {}, transform)
        caption = _caption(prompt, analysis)
        payload = _build_payload(
            reference_audio=__file__,
            prompt=prompt,
            analysis=analysis,
            duration_seconds=15,
            candidate_count=1,
            model="test-model",
        )

        self.assertEqual(transform["vocals"]["render_mode"], "instrumental_hook_proxy")
        self.assertTrue(transform["rich_reference"]["enabled"])
        self.assertIn("rich-reference safety", transform["prompt"])
        self.assertIn("instrumental hook proxy", caption)
        self.assertIn("do not attempt lead vocal resynthesis", conditioned)
        self.assertTrue(payload["instrumental"])
        self.assertEqual(payload["lyrics"], "[Instrumental]")
        self.assertEqual(payload["task_type"], "text2music")
        self.assertEqual(payload["reference_audio_path"], None)
        self.assertEqual(payload["src_audio_path"], None)
        self.assertEqual(payload["audio_cover_strength"], 0.0)
        self.assertEqual(payload["cover_noise_strength"], 0.0)
        self.assertIn("stretched vocal chops", payload["lm_negative_prompt"])

    def test_negative_vocal_prompt_does_not_infer_fast_lane_vocals(self):
        vocal_hint = _prompt_vocal_hint("clean synth hook, no lead vocal resynthesis, no stretched vocal chops")

        self.assertFalse(vocal_hint["present"])
        self.assertEqual(vocal_hint["role"], "none")

    def test_low_dense_harmonic_reference_uses_text_only_rich_reference_mode(self):
        analysis = {
            "reference_similarity_level": "low",
            "bpm": 120.0,
            "key": "F major",
            "genre": {"primary": "Electronic (120-135 BPM)", "tags": ["electronic", "4/4", "club"], "confidence": 0.2},
            "chords": {"confidence": 0.8, "progression": ["F", "G#", "C#", "F#", "C", "D#"]},
            "vocals": {"available": False, "present": False, "role": "none", "confidence": 0.0},
        }
        transform = build_reference_transform("clean synth hook, no lead vocal resynthesis", analysis)
        analysis["reference_transform"] = transform
        payload = _build_payload(
            reference_audio=__file__,
            prompt="clean synth hook, no lead vocal resynthesis",
            analysis=analysis,
            duration_seconds=15,
            candidate_count=1,
            model="test-model",
        )

        self.assertTrue(transform["rich_reference"]["enabled"])
        self.assertIn("rich harmonic movement", transform["rich_reference"]["reason"])
        self.assertEqual(transform["similarity_profile"]["reference_mode"], "analysis_text_only")
        self.assertTrue(payload["instrumental"])
        self.assertEqual(payload["task_type"], "text2music")
        self.assertEqual(payload["reference_audio_path"], None)
        self.assertEqual(payload["src_audio_path"], None)
        self.assertEqual(payload["audio_cover_strength"], 0.0)
        self.assertEqual(payload["cover_noise_strength"], 0.0)

    def test_instrumental_reference_still_bans_lead_vocals(self):
        analysis = {
            "reference_similarity_level": "low",
            "vocals": {"present": False, "role": "none"},
        }
        transform = build_reference_transform("", analysis)
        analysis["reference_transform"] = transform
        payload = _build_payload(
            reference_audio=__file__,
            prompt="",
            analysis=analysis,
            duration_seconds=15,
            candidate_count=1,
            model="test-model",
        )

        self.assertFalse(transform["vocals"]["preserve_role"])
        self.assertTrue(payload["instrumental"])
        self.assertEqual(payload["lyrics"], "[Instrumental]")
        self.assertIn("lead vocals, lyrical singing", payload["lm_negative_prompt"])

    def test_vocal_stem_activity_detects_lead_hook_role(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            stem_dir = os.path.join(temp_dir, "stems")
            os.makedirs(stem_dir)
            vocal_path = os.path.join(stem_dir, "vocals.wav")
            bass_path = os.path.join(stem_dir, "bass.wav")
            drums_path = os.path.join(stem_dir, "drums.wav")
            other_path = os.path.join(stem_dir, "other.wav")
            self._write_constant_sine_wav(vocal_path, amplitude=0.22, frequency=440)
            self._write_constant_sine_wav(bass_path, amplitude=0.12, frequency=80)
            self._write_constant_sine_wav(drums_path, amplitude=0.12, frequency=160)
            self._write_constant_sine_wav(other_path, amplitude=0.04, frequency=330)

            result = analyze_vocal_role(
                {"stems": {"vocals": vocal_path, "bass": bass_path, "drums": drums_path, "other": other_path}}
            )

        self.assertTrue(result["available"])
        self.assertTrue(result["present"])
        self.assertEqual(result["role"], "lead vocal hook")
        self.assertGreater(result["confidence"], 0.5)

    def test_explicit_house_direction_overrides_noisy_reference_genre(self):
        transform = build_reference_transform(
            "underground minimal deep tech house, rolling bassline, no cheesy pop",
            {
                "genre_deep": {
                    "primary": "breakbeat",
                    "tags": ["breakbeat", "classic rock"],
                    "confidence": 0.42,
                },
                "bpm": 126,
                "key": "F minor",
            },
        )

        self.assertEqual(transform["style"]["primary"], "underground minimal / deep tech house")
        self.assertIn("deep tech house", transform["style_brief"])
        self.assertNotIn("breakbeat", transform["style_brief"])

    def test_reference_sample_duration_can_use_full_source_length(self):
        previous = os.environ.get("PROMPT2MIDI_REFERENCE_SAMPLE_DURATION")
        try:
            os.environ["PROMPT2MIDI_REFERENCE_SAMPLE_DURATION"] = "full"
            self.assertEqual(_reference_sample_duration({"duration_seconds": 211.5}), 211.5)
            os.environ["PROMPT2MIDI_REFERENCE_SAMPLE_DURATION"] = "45"
            self.assertEqual(_reference_sample_duration({"duration_seconds": 211.5}), 45.0)
            os.environ["PROMPT2MIDI_REFERENCE_SAMPLE_DURATION"] = "999"
            self.assertEqual(_reference_sample_duration({"duration_seconds": 211.5}), 211.5)
        finally:
            if previous is None:
                os.environ.pop("PROMPT2MIDI_REFERENCE_SAMPLE_DURATION", None)
            else:
                os.environ["PROMPT2MIDI_REFERENCE_SAMPLE_DURATION"] = previous

    def test_low_similarity_candidate_selection_prefers_originality(self):
        close_copy = _selection_score(quality_score=0.82, exact_similarity_score=0.72, target_similarity=0.2)
        more_original = _selection_score(quality_score=0.80, exact_similarity_score=0.34, target_similarity=0.2)
        high_similarity_copy = _selection_score(quality_score=0.82, exact_similarity_score=0.72, target_similarity=0.8)
        high_similarity_loose = _selection_score(quality_score=0.80, exact_similarity_score=0.34, target_similarity=0.8)

        self.assertGreater(more_original, close_copy)
        self.assertGreater(high_similarity_copy, high_similarity_loose)

    def test_low_similarity_candidate_gate_prefers_accepted_house_pulse(self):
        accepted = {
            "path": "candidate-1.wav",
            "quality": {"score": 0.73, "selection_score": 0.806, "pulse_score": 0.557, "timbre_score": 0.671},
        }
        rejected_timbre_artifact = {
            "path": "candidate-2.wav",
            "quality": {"score": 0.463, "selection_score": 0.613, "pulse_score": 0.425, "timbre_score": 0.446},
        }
        rejected_weak_pulse = {
            "path": "candidate-3.wav",
            "quality": {"score": 0.685, "selection_score": 0.773, "pulse_score": 0.414, "timbre_score": 0.694},
        }

        for candidate in (accepted, rejected_timbre_artifact, rejected_weak_pulse):
            _apply_level_quality_gate(candidate["quality"], target_similarity=0.3)

        suggested = _suggest_candidate([rejected_timbre_artifact, rejected_weak_pulse, accepted])

        self.assertEqual(suggested["path"], "candidate-1.wav")
        self.assertTrue(accepted["quality"]["level_gate"]["passed"])
        self.assertFalse(rejected_timbre_artifact["quality"]["level_gate"]["passed"])
        self.assertFalse(rejected_weak_pulse["quality"]["level_gate"]["passed"])
        self.assertIn("club pulse", rejected_weak_pulse["quality"]["warnings"][0])

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
    def _write_running_bass_wav(path: str, bpm: int):
        sample_rate = 8000
        seconds = 8
        eighth = 60.0 / bpm / 2.0
        samples = []
        for index in range(sample_rate * seconds):
            time = index / sample_rate
            phase = time % eighth
            envelope = 0.95 if phase < 0.12 else 0.05
            tone = math.sin(2 * math.pi * 65.406 * time)
            click = math.sin(2 * math.pi * 95.0 * time) * 0.18
            samples.append(int(max(-1.0, min(1.0, envelope * (tone + click))) * 32767))

        with wave.open(path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b"".join(struct.pack("<h", sample) for sample in samples))

    @staticmethod
    def _write_constant_sine_wav(path: str, amplitude: float, frequency: float):
        sample_rate = 8000
        seconds = 2
        samples = []
        for index in range(sample_rate * seconds):
            time = index / sample_rate
            tone = math.sin(2 * math.pi * frequency * time)
            samples.append(int(max(-1.0, min(1.0, amplitude * tone)) * 32767))

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
