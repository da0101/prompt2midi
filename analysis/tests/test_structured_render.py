#!/usr/bin/env python3
from __future__ import annotations

import os
import random
import tempfile
import unittest

import numpy as np
from scipy.io import wavfile

from analysis.generation.rendering.structured_render import KEY_NOTE, _compose_control_scaffold, _scale, render_control_scaffold, render_reference_sample


class StructuredRenderTest(unittest.TestCase):
    def test_render_reference_sample_writes_candidates_and_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            reference = os.path.join(tmp, "reference.wav")
            sr = 44100
            t = np.arange(int(sr * 4.0)) / sr
            kick = (np.sin(2 * np.pi * 55 * t) * (np.sin(2 * np.pi * 2 * t) > 0.92)).astype(np.float32)
            tone = (0.18 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
            wavfile.write(reference, sr, np.asarray((kick * 0.25 + tone) * 32767, dtype=np.int16))

            out = os.path.join(tmp, "out")
            payload = render_reference_sample(
                reference_path=reference,
                output_dir=out,
                similarity_level="low",
                duration_seconds=1.5,
                candidates=1,
                prompt="instrumental house test",
                seed=7,
            )

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["engine"], "structured_render_v1")
            self.assertEqual(len(payload["candidates"]), 1)
            self.assertTrue(os.path.exists(payload["candidates"][0]["path"]))
            self.assertTrue(os.path.exists(os.path.join(out, "structured-render.json")))
            self.assertTrue(os.path.exists(os.path.join(out, "suno-prompt.txt")))
            self.assertGreater(payload["candidates"][0]["quality"]["score"], 0.0)

    def test_render_control_scaffold_writes_in_key_bass_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            reference = os.path.join(tmp, "reference.wav")
            sr = 44100
            t = np.arange(int(sr * 2.0)) / sr
            tone = (0.2 * np.sin(2 * np.pi * 73.42 * t)).astype(np.float32)
            wavfile.write(reference, sr, np.asarray(tone * 32767, dtype=np.int16))

            analysis = {
                "bpm": 124,
                "key": "C minor",
                "reference_transform": {"harmonic": {"key": "C# minor", "strict_scale": True}},
                "genre": {"primary": "electro house", "tags": ["electro house"]},
                "energy": {"lane": "high"},
            }
            groove = {
                "kick_pattern_16th": [0, 4, 8, 12, 16, 20, 24, 28],
                "bass_accent_pattern_16th": [0, 2, 4, 6, 8, 10, 12, 14],
                "hat_pattern_16th": [2, 6, 10, 14],
            }

            payload = render_control_scaffold(
                reference_path=reference,
                output_dir=os.path.join(tmp, "out"),
                prompt="same bassline rhythm and sound but different notes",
                analysis=analysis,
                reference_groove=groove,
                duration_seconds=1.5,
            )
            composition = _compose_control_scaffold(payload["analysis"], 1.5, random.Random(1))
            scale = set(_scale(KEY_NOTE["C#"], "minor"))
            bass_notes = [event[2] % 12 for event in composition["events"]["bass"]]

            self.assertTrue(os.path.exists(payload["path"]))
            self.assertTrue(os.path.exists(os.path.join(tmp, "out", "ace-control-scaffold.json")))
            self.assertEqual(payload["analysis"]["key"], "C# minor")
            self.assertGreater(len(bass_notes), 0)
            self.assertTrue(all(note in scale for note in bass_notes))


if __name__ == "__main__":
    unittest.main()
