#!/usr/bin/env python3
"""CLAP-based zero-shot genre detection for prompt2midi.

Primary path: laion/larger_clap_music via transformers.
Fallback: unavailable stub when torch/transformers are absent or disabled.
"""
from __future__ import annotations

import os

_GENRE_LABELS = [
    # Electronic / dance
    "techno", "house", "deep house", "minimal techno", "tech house", "trance",
    "drum and bass", "dubstep", "ambient", "synth pop", "new wave", "synth wave",
    "retrowave", "vapor wave", "industrial", "EBM", "lo-fi hip hop", "chillout",
    "progressive house", "electro", "breakbeat",
    # Hip-hop / R&B
    "hip hop", "trap", "R&B", "soul", "funk",
    # Rock / guitar
    "rock", "alternative rock", "indie rock", "grunge", "punk rock", "hard rock",
    "heavy metal", "metal", "classic rock", "pop rock",
    # Pop / mainstream
    "pop", "disco", "dance pop",
    # Jazz / acoustic
    "jazz", "blues", "classical", "folk", "acoustic",
    # World
    "reggae", "afrobeat", "latin", "country",
]

_FALLBACK = {
    "primary": "Unknown (genre classifier unavailable)",
    "confidence": 0.0,
    "method": "unavailable",
    "tags": [],
}

_CLAP_MODEL_ID = "laion/larger_clap_music"
_SAMPLE_RATE = 48000
_WINDOW_SECONDS = 30


def detect_genre(audio_path: str) -> dict:
    """Detect the genre/style of a music track.

    Returns a dict with keys: primary, top3, confidence, method, tags.
    Falls back to the unavailable stub when CLAP is disabled or unloadable.
    """
    if os.environ.get("PROMPT2MIDI_DISABLE_GENRE") == "1":
        return _FALLBACK.copy()

    try:
        import numpy as np
        import librosa
        import torch
        from transformers import ClapModel, ClapProcessor
    except ImportError:
        return _FALLBACK.copy()

    try:
        audio_array, _ = librosa.load(audio_path, sr=_SAMPLE_RATE, mono=True)
    except Exception:
        return _FALLBACK.copy()

    if audio_array is None or len(audio_array) == 0:
        return _FALLBACK.copy()

    audio_array = _extract_window(audio_array, _SAMPLE_RATE, _WINDOW_SECONDS)

    try:
        processor = ClapProcessor.from_pretrained(_CLAP_MODEL_ID)
        model = ClapModel.from_pretrained(_CLAP_MODEL_ID)
        model.eval()
    except Exception:
        return _FALLBACK.copy()

    try:
        inputs = processor(
            text=_GENRE_LABELS,
            audio=audio_array,
            return_tensors="pt",
            sampling_rate=_SAMPLE_RATE,
            padding=True,
        )

        with torch.no_grad():
            outputs = model(**inputs)

        logits = outputs.logits_per_audio
        probs = torch.softmax(logits, dim=-1).squeeze(0)
        scores = probs.tolist()

        ranked = sorted(
            zip(_GENRE_LABELS, scores),
            key=lambda pair: pair[1],
            reverse=True,
        )
        top3 = [
            {"label": label, "confidence": round(score, 4)}
            for label, score in ranked[:3]
        ]
        primary_label = top3[0]["label"]
        primary_confidence = top3[0]["confidence"]

        return {
            "primary": primary_label,
            "top3": top3,
            "confidence": primary_confidence,
            "method": "clap_zero_shot",
            "tags": [entry["label"] for entry in top3],
        }

    except Exception:
        return _FALLBACK.copy()


def _extract_window(
    audio: "np.ndarray",
    sample_rate: int,
    window_seconds: float,
) -> "np.ndarray":
    """Return a representative centre window of the audio, or the full array if shorter."""
    target_samples = int(sample_rate * window_seconds)
    if len(audio) <= target_samples:
        return audio
    start = (len(audio) - target_samples) // 2
    return audio[start : start + target_samples]
