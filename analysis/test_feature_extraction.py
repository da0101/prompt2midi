import math
import os
import struct
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(__file__))

from feature_extraction import analyze_wav
from analyze import run as run_analysis
from bass_transcription import transcribe_bassline
from midi_extraction import write_note_events_midi, write_reference_sketch_midi
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
