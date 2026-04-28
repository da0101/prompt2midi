import math
import os
import struct
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(__file__))

from feature_extraction import analyze_wav
from midi_extraction import write_bassline_midi


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
        self.assertIn("key", result)
        self.assertGreater(len(result["energy_curve"]), 2)
        self.assertIn("loudness", result)

    def test_write_bassline_midi_creates_standard_midi_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            midi_path = os.path.join(temp_dir, "bassline.mid")
            written = write_bassline_midi(midi_path, key="A major", bpm=124)

            with open(written, "rb") as midi_file:
                header = midi_file.read(4)

        self.assertEqual(header, b"MThd")

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


if __name__ == "__main__":
    unittest.main()
