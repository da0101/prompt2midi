#!/usr/bin/env python3
from __future__ import annotations

import math
import os
import struct
import sys
import tempfile
import unittest
import wave
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

import suno_cover_package


class SunoCoverPackageTest(unittest.TestCase):
    def test_prepare_suno_cover_package_writes_prompt_upload_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            reference = os.path.join(tmp, "reference.wav")
            self._write_wav(reference, duration=8.0)
            out = os.path.join(tmp, "suno")

            with patch.object(suno_cover_package, "analyze_wav", return_value=self._analysis()), \
                 patch.object(suno_cover_package, "better_bpm", return_value={"bpm": 118.0, "confidence": 0.9, "method": "test"}), \
                 patch.object(suno_cover_package, "better_key", return_value={"key": "C minor", "confidence": 0.8, "method": "test"}), \
                 patch.object(suno_cover_package, "infer_genre", return_value={"primary": "electro funk", "tags": ["dance pop"]}), \
                 patch.object(suno_cover_package, "detect_genre", return_value={"primary": "electro funk", "tags": ["dance pop", "post disco"], "confidence": 0.5}), \
                 patch.object(suno_cover_package, "estimate_groove", return_value={"description": "tight syncopated pocket"}), \
                 patch.object(suno_cover_package, "detect_chords", return_value={"progression": ["Cm", "Ab", "Bb", "Gm"]}), \
                 patch.object(suno_cover_package, "analyze_structure", return_value={"sections": [{"start": 0, "end": 8, "label": "hook", "energy": 0.8}]}), \
                 patch.object(suno_cover_package, "analyze_reference_groove", return_value={
                     "kick_pattern_16th": [0, 4, 8, 12],
                     "bass_accent_pattern_16th": [0, 3, 6, 10],
                     "hat_pattern_16th": [2, 6, 10, 14],
                     "drum_feel": "straight punchy drums",
                     "bass_feel": "syncopated low-mid bass",
                     "low_end_weight": "heavy low end",
                     "club_energy": "high",
                 }), \
                 patch.object(suno_cover_package, "_cut_audio", side_effect=self._fake_cut_audio):
                payload = suno_cover_package.prepare_suno_cover_package(
                    reference_audio=reference,
                    output_dir=out,
                    user_prompt="new vocal identity, darker club pressure",
                    upload_duration=6.0,
                )

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["engine"], "suno_cover_package_v1")
            self.assertEqual(payload["upload_section"]["duration_seconds"], 6.0)
            self.assertTrue(os.path.exists(payload["files"]["upload_wav"]))
            self.assertTrue(os.path.exists(payload["files"]["upload_mp3"]))
            self.assertTrue(os.path.exists(payload["files"]["prompt"]))
            self.assertTrue(os.path.exists(payload["files"]["report"]))
            self.assertTrue(os.path.exists(payload["files"]["instructions"]))
            self.assertTrue(os.path.exists(payload["files"]["manifest"]))

            with open(payload["files"]["prompt"], encoding="utf-8") as handle:
                prompt = handle.read()
            with open(payload["files"]["report"], encoding="utf-8") as handle:
                report = handle.read()

            self.assertIn("Suno Cover / Audio Input Prompt", prompt)
            self.assertIn("118 BPM", prompt)
            self.assertIn("new vocal identity", prompt)
            self.assertIn("electro funk", prompt)
            self.assertIn("Reference Groove Fingerprint", report)

    def _analysis(self):
        return {
            "duration_seconds": 8.0,
            "bpm": 118.0,
            "bpm_confidence": 0.7,
            "key": "C minor",
            "key_confidence": 0.6,
            "energy_curve": [
                {"time": 0.0, "energy": 0.1},
                {"time": 2.0, "energy": 0.4},
                {"time": 4.0, "energy": 0.9},
                {"time": 6.0, "energy": 0.8},
                {"time": 8.0, "energy": 0.3},
            ],
        }

    def _fake_cut_audio(self, _reference, output, _start, duration, codec):
        if codec == "mp3":
            output.write_bytes(b"ID3 prompt2midi test")
        else:
            self._write_wav(str(output), duration=duration)

    def _write_wav(self, path, duration=2.0, sample_rate=8000):
        frames = int(sample_rate * duration)
        with wave.open(path, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            for index in range(frames):
                value = int(9000 * math.sin(2 * math.pi * 220 * index / sample_rate))
                handle.writeframes(struct.pack("<h", value))


if __name__ == "__main__":
    unittest.main()
