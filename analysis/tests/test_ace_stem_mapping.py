#!/usr/bin/env python3
from __future__ import annotations

import math
import os
import struct
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from analysis.detectors.drum_analysis import analyze_drums, drum_pattern_to_midi_events
from analysis.midi.ace_stem_mapping import build_ace_stem_mapping, detect_stem_roles
from analysis.midi.stem_separation import separate_for_transcription
from analysis.midi.source_transcription import _extract_bassline


class AceStemMappingTest(unittest.TestCase):
    def test_detects_only_available_active_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            drums = os.path.join(tmp, "drums.wav")
            other = os.path.join(tmp, "other.wav")
            self._write_pulsed_wav(drums, frequency=120, amplitude=0.7)
            self._write_sine_wav(other, frequency=440, amplitude=0.24)

            mapping = detect_stem_roles(
                {
                    "available": True,
                    "method": "demucs_htdemucs",
                    "source_audio": os.path.join(tmp, "candidate.wav"),
                    "source_stage": "ace_generated_output",
                    "stems": {"drums": drums, "other": other},
                    "warnings": [],
                }
            )

        self.assertTrue(mapping["available"])
        self.assertEqual(mapping["source_stage"], "ace_generated_output")
        self.assertIn("drums", mapping["detected_roles"])
        self.assertIn("other_sustained_harmonic", mapping["detected_roles"])
        self.assertNotIn("bass", mapping["detected_roles"])
        self.assertNotIn("vocals", mapping["detected_roles"])

    def test_detects_bass_and_guitar_without_drums_or_vocals(self):
        with tempfile.TemporaryDirectory() as tmp:
            bass = os.path.join(tmp, "bass.wav")
            guitar = os.path.join(tmp, "guitar.wav")
            quiet_drums = os.path.join(tmp, "drums.wav")
            self._write_sine_wav(bass, frequency=70, amplitude=0.35)
            self._write_pulsed_wav(guitar, frequency=330, amplitude=0.32)
            self._write_sine_wav(quiet_drums, frequency=120, amplitude=0.001)

            mapping = detect_stem_roles(
                {
                    "available": True,
                    "method": "demucs_htdemucs_6s",
                    "source_stage": "ace_generated_output",
                    "stems": {"bass": bass, "guitar": guitar, "drums": quiet_drums},
                    "warnings": [],
                }
            )

        self.assertEqual(mapping["detected_roles"], ["bass", "guitar"])
        self.assertEqual(mapping["roles"]["bass"]["source_stem"], "bass")
        self.assertEqual(mapping["roles"]["guitar"]["family"], "pitched_harmonic")
        self.assertTrue(any(item.get("stem") == "drums" for item in mapping["omitted_roles"]))

    def test_build_mapping_writes_ace_source_plan_without_fake_midi(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = os.path.join(tmp, "candidate.wav")
            bass = os.path.join(tmp, "bass.wav")
            self._write_sine_wav(candidate, frequency=220, amplitude=0.2)
            self._write_sine_wav(bass, frequency=82, amplitude=0.3)

            mapping = build_ace_stem_mapping(
                candidate,
                os.path.join(tmp, "out"),
                bpm=122,
                stem_result={
                    "available": True,
                    "method": "demucs_htdemucs",
                    "source_audio": candidate,
                    "source_stage": "ace_generated_output",
                    "stems": {"bass": bass},
                    "warnings": [],
                },
            )

            self.assertTrue(os.path.exists(mapping["path"]))
            self.assertEqual(mapping["source_audio"], os.path.abspath(candidate))
            self.assertEqual(mapping["source_stage"], "ace_generated_output")
            self.assertEqual(mapping["midi_plan"][0]["status"], "planned")
            self.assertFalse(os.path.exists(mapping["midi_plan"][0]["target_path"]))

    def test_build_mapping_rejects_missing_ace_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                build_ace_stem_mapping(os.path.join(tmp, "missing.wav"), os.path.join(tmp, "out"))

    def test_separation_succeeds_when_demucs_outputs_drums_and_other_without_bass(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_audio = os.path.join(tmp, "candidate.wav")
            self._write_sine_wav(input_audio, frequency=220, amplitude=0.2)

            def fake_run(command, cwd, env, text, capture_output, timeout):
                out_index = command.index("-o") + 1
                demucs_root = Path(command[out_index])
                stem_dir = demucs_root / "htdemucs" / "candidate"
                stem_dir.mkdir(parents=True, exist_ok=True)
                self._write_pulsed_wav(str(stem_dir / "drums.wav"), frequency=120, amplitude=0.7)
                self._write_sine_wav(str(stem_dir / "other.wav"), frequency=440, amplitude=0.2)
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch("analysis.midi.stem_separation._find_demucs", return_value="/bin/echo"), patch(
                "analysis.midi.stem_separation.subprocess.run", side_effect=fake_run
            ):
                result = separate_for_transcription(
                    input_audio,
                    os.path.join(tmp, "out"),
                    source_stage="ace_generated_output",
                )

        self.assertTrue(result["available"])
        self.assertEqual(sorted(result["stems"]), ["drums", "other"])
        self.assertEqual(result["source_stage"], "ace_generated_output")

    def test_drum_analysis_has_dependency_free_onset_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            drum_path = os.path.join(tmp, "drums.wav")
            self._write_pulsed_wav(drum_path, frequency=90, amplitude=0.8, duration=4.0)

            with patch.dict("sys.modules", {"librosa": None, "scipy.signal": None}):
                drums = analyze_drums(drum_path, bpm=120)

        events = drum_pattern_to_midi_events(drums, bpm=120)
        self.assertIn(drums["method"], {"onset_detection_fallback", "house_four_on_floor_fallback"})
        self.assertTrue(events)
        self.assertLessEqual(len(drums["kick"]) + len(drums["snare"]) + len(drums["hat"]), 12)

    def test_stem_bass_extraction_keeps_sub_notes_and_cleans_house_grid(self):
        raw = []
        sixteenth = 60.0 / 128.0 / 4.0
        for bar in range(4):
            for position in (2, 6, 10, 14):
                start = (bar * 16 + position) * sixteenth
                raw.append({"start": start + 0.018, "duration": 0.16, "midi_note": 32, "velocity": 76})
                raw.append({"start": start + 0.021, "duration": 0.14, "midi_note": 44, "velocity": 70})
            for position in (1, 5, 9):
                raw.append({"start": (bar * 16 + position) * sixteenth, "duration": 0.08, "midi_note": 51, "velocity": 38})

        cleaned = _extract_bassline(
            raw,
            bpm=128,
            minimum_note=28,
            maximum_note=60,
            velocity_floor=35,
            house_cleanup=True,
        )

        self.assertTrue(cleaned)
        self.assertTrue(all(28 <= event["midi_note"] <= 60 for event in cleaned))
        self.assertIn(32, {event["midi_note"] for event in cleaned})
        self.assertLessEqual(len(cleaned), 16)
        self.assertEqual({round((event["start"] / sixteenth) % 16) for event in cleaned}, {2, 6, 10, 14})

    def _write_sine_wav(self, path, frequency=220, amplitude=0.25, duration=1.0, sample_rate=8000):
        frames = int(sample_rate * duration)
        with wave.open(path, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            for index in range(frames):
                value = int(32767 * amplitude * math.sin(2 * math.pi * frequency * index / sample_rate))
                handle.writeframes(struct.pack("<h", value))

    def _write_pulsed_wav(self, path, frequency=220, amplitude=0.35, duration=1.0, sample_rate=8000):
        frames = int(sample_rate * duration)
        with wave.open(path, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            for index in range(frames):
                beat = int(index / (sample_rate * 0.125)) % 2 == 0
                env = amplitude if beat else amplitude * 0.05
                value = int(32767 * env * math.sin(2 * math.pi * frequency * index / sample_rate))
                handle.writeframes(struct.pack("<h", value))


if __name__ == "__main__":
    unittest.main()
