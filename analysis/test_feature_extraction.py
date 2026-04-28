import math
import os
import struct
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(__file__))

from feature_extraction import analyze_wav
from bass_transcription import transcribe_bassline
from midi_extraction import write_note_events_midi, write_reference_sketch_midi


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


if __name__ == "__main__":
    unittest.main()
