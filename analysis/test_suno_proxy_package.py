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

import suno_proxy_package


class SunoProxyPackageTest(unittest.TestCase):
    def test_prepare_suno_proxy_package_uses_proxy_audio_not_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            reference = os.path.join(tmp, "reference.wav")
            proxy = os.path.join(tmp, "proxy.wav")
            self._write_wav(reference, duration=8.0, frequency=220)
            self._write_wav(proxy, duration=7.0, frequency=330)
            out = os.path.join(tmp, "out")

            with patch.object(suno_proxy_package, "_analyze_for_suno", return_value=self._analysis()), \
                 patch.object(suno_proxy_package, "_cut_audio", side_effect=self._fake_cut_audio):
                payload = suno_proxy_package.prepare_suno_proxy_package(
                    reference_audio=reference,
                    proxy_audio=proxy,
                    output_dir=out,
                    user_prompt="Michael Jackson inspired but new vocal identity",
                    upload_duration=6.0,
                )

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["engine"], "suno_proxy_package_v1")
            self.assertEqual(payload["proxy_audio"], os.path.realpath(proxy))
            self.assertEqual(payload["reference_audio_local_only"], os.path.realpath(reference))
            self.assertTrue(os.path.exists(payload["files"]["upload_wav"]))
            self.assertTrue(os.path.exists(payload["files"]["upload_mp3"]))
            self.assertTrue(os.path.exists(payload["files"]["prompt"]))

            with open(payload["files"]["prompt"], encoding="utf-8") as handle:
                prompt = handle.read()

            self.assertIn("generated proxy demo", prompt)
            self.assertIn("Do not imitate any famous artist", prompt)
            self.assertNotIn("Michael Jackson", prompt)
            self.assertLessEqual(len(prompt), 2000)
            self.assertIn("Preserve the proxy's arrangement", prompt)
            self.assertIn("Avoid unrelated layers", prompt)

    def test_prepare_suno_proxy_package_rejects_original_reference_as_proxy(self):
        with tempfile.TemporaryDirectory() as tmp:
            reference = os.path.join(tmp, "reference.wav")
            self._write_wav(reference, duration=6.0, frequency=220)

            with self.assertRaises(ValueError):
                suno_proxy_package.prepare_suno_proxy_package(
                    reference_audio=reference,
                    proxy_audio=reference,
                    output_dir=os.path.join(tmp, "out"),
                    user_prompt="new track",
                    upload_duration=6.0,
                )

    def test_full_upload_duration_uses_entire_proxy_track(self):
        section = suno_proxy_package._choose_proxy_section(360.12, "full", 42.0)

        self.assertEqual(section["start_seconds"], 0.0)
        self.assertEqual(section["end_seconds"], 360.12)
        self.assertEqual(section["duration_seconds"], 360.12)
        self.assertEqual(section["method"], "proxy_full_track")

    def _analysis(self):
        return {
            "duration_seconds": 8.0,
            "bpm": 120.0,
            "bpm_confidence": 0.7,
            "key": "E minor",
            "key_confidence": 0.6,
            "genre": {"primary": "electro funk", "tags": ["dance pop", "post disco"]},
            "groove": {"description": "tight syncopated pocket"},
            "vocal_role": {"present": True, "summary": "strong lead-hook role with new vocal identity"},
            "reference_groove": {
                "kick_pattern_16th": [0, 4, 8, 12],
                "bass_accent_pattern_16th": [0, 3, 6, 10],
                "hat_pattern_16th": [2, 6, 10, 14],
                "low_end_weight": "heavy",
            },
        }

    def _fake_cut_audio(self, _reference, output, _start, duration, codec):
        if codec == "mp3":
            output.write_bytes(b"ID3 prompt2midi proxy test")
        else:
            self._write_wav(str(output), duration=duration, frequency=440)

    def _write_wav(self, path, duration=2.0, frequency=220, sample_rate=8000):
        frames = int(sample_rate * duration)
        with wave.open(path, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            for index in range(frames):
                value = int(9000 * math.sin(2 * math.pi * frequency * index / sample_rate))
                handle.writeframes(struct.pack("<h", value))


if __name__ == "__main__":
    unittest.main()
