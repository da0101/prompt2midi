#!/usr/bin/env python3
"""MusicGen Melody reference-conditioned sample generation."""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_MODEL = "facebook/musicgen-melody"
DEFAULT_DURATION_SECONDS = 30.0
DEFAULT_REFERENCE_SECONDS = 15.0
DEFAULT_CHUNK_SECONDS = 5.0
MUSICGEN_TOKENS_PER_SECOND = 50


def generate_reference_sample(
    reference_audio: str,
    output_dir: str,
    prompt: str,
    duration_seconds: float = DEFAULT_DURATION_SECONDS,
) -> dict:
    """Generate a MusicGen Melody WAV sample from text + reference audio."""
    if os.environ.get("PROMPT2MIDI_ENABLE_MUSICGEN") != "1":
        return {
            "status": "disabled",
            "sample": None,
            "duration_seconds": duration_seconds,
            "provider": "musicgen_melody",
            "model": os.environ.get("PROMPT2MIDI_MUSICGEN_MODEL") or DEFAULT_MODEL,
            "limitations": ["Set PROMPT2MIDI_ENABLE_MUSICGEN=1 to run real audio generation."],
        }

    _require_file(reference_audio)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    model_id = os.environ.get("PROMPT2MIDI_MUSICGEN_MODEL") or DEFAULT_MODEL
    cache_dir = os.environ.get("PROMPT2MIDI_MUSICGEN_CACHE") or str(
        Path(__file__).resolve().parents[3] / ".cache" / "musicgen"
    )
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    output_path = os.path.abspath(os.path.join(output_dir, "sample.wav"))
    seed = int(os.environ.get("PROMPT2MIDI_MUSICGEN_SEED") or "42")
    guidance_scale = float(os.environ.get("PROMPT2MIDI_MUSICGEN_GUIDANCE") or "3.0")
    temperature = float(os.environ.get("PROMPT2MIDI_MUSICGEN_TEMPERATURE") or "1.0")
    chunk_seconds = max(
        1.0,
        min(
            duration_seconds,
            float(os.environ.get("PROMPT2MIDI_MUSICGEN_CHUNK_SECONDS") or DEFAULT_CHUNK_SECONDS),
        ),
    )

    try:
        import numpy as np
        import soundfile as sf
        import torch
        from transformers import AutoProcessor, MusicgenMelodyForConditionalGeneration
    except Exception as exc:
        raise RuntimeError(
            "MusicGen generation requires torch, transformers, numpy, and soundfile."
        ) from exc

    device = _select_device(torch)
    _progress(f"musicgen: loading {model_id} on {device}")
    _progress(f"musicgen: using model cache {cache_dir}")
    processor = AutoProcessor.from_pretrained(model_id, cache_dir=cache_dir)
    model = MusicgenMelodyForConditionalGeneration.from_pretrained(model_id, cache_dir=cache_dir)
    model.to(device)
    model.eval()

    sample_rate = int(getattr(processor.feature_extractor, "sampling_rate", 32000) or 32000)
    reference = _decode_reference(reference_audio, sample_rate, DEFAULT_REFERENCE_SECONDS)
    text = _style_prompt(prompt)

    _progress("musicgen: conditioning on reference audio + prompt")
    inputs = processor(
        audio=[reference],
        sampling_rate=sample_rate,
        text=[text],
        padding=True,
        return_tensors="pt",
    )
    inputs = {key: value.to(device) if hasattr(value, "to") else value for key, value in inputs.items()}

    chunks = []
    generated_seconds = 0.0
    chunk_index = 0
    while generated_seconds < duration_seconds - 0.001:
        current_seconds = min(chunk_seconds, duration_seconds - generated_seconds)
        max_new_tokens = min(1503, max(1, math.ceil(current_seconds * MUSICGEN_TOKENS_PER_SECOND)))
        _progress(
            f"musicgen: generating chunk {chunk_index + 1} "
            f"({current_seconds:.1f}s, {max_new_tokens} tokens)"
        )
        torch.manual_seed(seed + chunk_index)
        with torch.no_grad():
            audio_values = model.generate(
                **inputs,
                do_sample=True,
                guidance_scale=guidance_scale,
                temperature=temperature,
                max_new_tokens=max_new_tokens,
            )
        chunk = audio_values[0].detach().cpu().float().numpy()
        chunks.append(_fit_duration(chunk, sample_rate, current_seconds))
        generated_seconds += current_seconds
        chunk_index += 1

    generated = _join_chunks(chunks, sample_rate)
    generated = _fit_duration(generated, sample_rate, duration_seconds)
    sf.write(output_path, generated.T, sample_rate)
    return {
        "status": "succeeded",
        "sample": output_path,
        "duration_seconds": duration_seconds,
        "provider": "musicgen_melody",
        "model": model_id,
        "prompt": text,
        "reference_seconds": DEFAULT_REFERENCE_SECONDS,
        "seed": seed,
        "guidance_scale": guidance_scale,
        "temperature": temperature,
        "chunk_seconds": chunk_seconds,
        "chunk_count": len(chunks),
        "limitations": [
            "Reference-conditioned generation, not a copy or stem recreation of the source track.",
            "Quality depends on the local MusicGen checkpoint and available CPU/GPU performance.",
        ],
    }


def _decode_reference(path: str, sample_rate: int, seconds: float):
    import soundfile as sf

    ffmpeg = os.environ.get("PROMPT2MIDI_FFMPEG") or shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to decode the reference audio for MusicGen.")
    temp_path = str(Path("/tmp") / f"prompt2midi-musicgen-reference-{os.getpid()}.wav")
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        path,
        "-t",
        str(seconds),
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        temp_path,
    ]
    subprocess.run(command, check=True)
    try:
        audio, _ = sf.read(temp_path, dtype="float32", always_2d=False)
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass
    return audio


def _join_chunks(chunks: list, sample_rate: int):
    import numpy as np

    if not chunks:
        return np.zeros((1, 0), dtype="float32")
    crossfade = int(sample_rate * 0.08)
    output = chunks[0]
    for chunk in chunks[1:]:
        if output.shape[0] != chunk.shape[0]:
            channels = min(output.shape[0], chunk.shape[0])
            output = output[:channels]
            chunk = chunk[:channels]
        fade = min(crossfade, output.shape[-1], chunk.shape[-1])
        if fade > 0:
            out_tail = output[:, -fade:]
            chunk_head = chunk[:, :fade]
            ramp = np.linspace(0.0, 1.0, fade, dtype="float32").reshape(1, -1)
            blended = out_tail * (1.0 - ramp) + chunk_head * ramp
            output = np.concatenate([output[:, :-fade], blended, chunk[:, fade:]], axis=-1)
        else:
            output = np.concatenate([output, chunk], axis=-1)
    return output


def _fit_duration(audio, sample_rate: int, duration_seconds: float):
    import numpy as np

    if audio.ndim == 1:
        audio = audio.reshape(1, -1)
    target = int(sample_rate * duration_seconds)
    if audio.shape[-1] > target:
        return audio[:, :target]
    if audio.shape[-1] < target:
        pad = target - audio.shape[-1]
        audio = np.pad(audio, ((0, 0), (0, pad)))
    return audio


def _style_prompt(prompt: str) -> str:
    base = prompt.strip()
    if not base:
        base = "reference-inspired instrumental music"
    return (
        f"{base}. Generate a producer-grade original instrumental guide track with the same tempo and key area "
        "as the reference, clear drums, defined bassline, stable tonal harmony, recognizable hook role, clean mix, "
        "no copied lyrics, no copied singer identity, no warped vocals, no random glitches, no atonal artifacts, "
        "not a cover and not a copy of the reference."
    )


def _select_device(torch_module) -> str:
    configured = os.environ.get("PROMPT2MIDI_MUSICGEN_DEVICE")
    if configured:
        return configured
    if torch_module.cuda.is_available():
        return "cuda"
    if hasattr(torch_module.backends, "mps") and torch_module.backends.mps.is_available():
        return "mps"
    return "cpu"


def _require_file(path: str) -> None:
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(f"Reference audio file not found: {path}")


def _progress(message: str) -> None:
    print(f"progress: {message}", file=sys.stderr, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a 30-second MusicGen Melody sample.")
    parser.add_argument("--reference", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--prompt", default="")
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION_SECONDS)
    args = parser.parse_args()

    try:
        payload = {
            "ok": True,
            "audio": generate_reference_sample(
                reference_audio=args.reference,
                output_dir=args.output_dir,
                prompt=args.prompt,
                duration_seconds=args.duration,
            ),
        }
    except Exception as exc:
        payload = {"ok": False, "error": {"code": "musicgen_failed", "message": str(exc)}}

    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True))
    sys.stdout.write("\n")
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
