#!/usr/bin/env python3
"""Official AudioCraft MusicGen runner for reference-inspired samples."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_MODEL = "facebook/musicgen-melody"
DEFAULT_DURATION_SECONDS = 30.0
DEFAULT_EXTEND_STRIDE_SECONDS = 10.0


def generate_sample(
    reference_audio: str | None,
    output_dir: str,
    prompt: str,
    model_name: str = DEFAULT_MODEL,
    duration_seconds: float = DEFAULT_DURATION_SECONDS,
    mode: str = "melody",
) -> dict:
    """Generate one MusicGen sample with the official AudioCraft API."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    cache_dir = os.environ.get("PROMPT2MIDI_MUSICGEN_CACHE") or str(
        Path(__file__).resolve().parent.parent / ".cache" / "audiocraft"
    )
    os.environ.setdefault("HF_HOME", cache_dir)
    os.environ.setdefault("XDG_CACHE_HOME", str(Path(cache_dir).parent))
    os.environ.setdefault("TORCH_HOME", str(Path(cache_dir) / "torch"))

    try:
        import torch
        import torchaudio
        from audiocraft.models import MusicGen
        from audiocraft.data.audio import audio_write
    except Exception as exc:
        raise RuntimeError(
            "AudioCraft MusicGen is not installed. Run `npm run setup:musicgen` first."
        ) from exc

    device = _select_device(torch)
    _progress(f"audiocraft: loading {model_name} on {device}")
    model = MusicGen.get_pretrained(model_name, device=device)
    model.set_generation_params(
        duration=float(duration_seconds),
        extend_stride=float(os.environ.get("PROMPT2MIDI_MUSICGEN_EXTEND_STRIDE") or DEFAULT_EXTEND_STRIDE_SECONDS),
        use_sampling=True,
        top_k=int(os.environ.get("PROMPT2MIDI_MUSICGEN_TOP_K") or "250"),
        top_p=float(os.environ.get("PROMPT2MIDI_MUSICGEN_TOP_P") or "0.0"),
        temperature=float(os.environ.get("PROMPT2MIDI_MUSICGEN_TEMPERATURE") or "1.0"),
        cfg_coef=float(os.environ.get("PROMPT2MIDI_MUSICGEN_CFG") or "3.0"),
    )
    model.set_custom_progress_callback(_token_progress)

    description = _style_prompt(prompt)
    if mode == "melody":
        if not reference_audio:
            raise ValueError("melody mode requires --reference")
        _progress("audiocraft: loading reference for melody conditioning")
        wav, sample_rate = _load_audio(reference_audio, target_channels=1)
        _progress("audiocraft: generating with chroma melody conditioning")
        generated = model.generate_with_chroma([description], wav[None], sample_rate, progress=True)[0].cpu()
    elif mode == "continuation":
        if not reference_audio:
            raise ValueError("continuation mode requires --reference")
        _progress("audiocraft: loading reference for continuation")
        wav, sample_rate = _load_audio(reference_audio, target_channels=model.audio_channels)
        prompt_seconds = float(os.environ.get("PROMPT2MIDI_MUSICGEN_PROMPT_SECONDS") or "6.0")
        wav = wav[:, : int(sample_rate * prompt_seconds)]
        _progress("audiocraft: generating continuation from reference prompt")
        generated = model.generate_continuation(wav[None], sample_rate, [description], progress=True)[0].cpu()
    elif mode == "text":
        _progress("audiocraft: generating from text prompt")
        generated = model.generate([description], progress=True)[0].cpu()
    else:
        raise ValueError("mode must be one of: melody, continuation, text")

    output_stem = os.path.join(output_dir, "sample")
    audio_write(output_stem, generated, model.sample_rate, strategy="loudness", loudness_compressor=True)
    output_path = os.path.abspath(output_stem + ".wav")
    return {
        "status": "succeeded",
        "sample": output_path,
        "duration_seconds": duration_seconds,
        "provider": "audiocraft_musicgen",
        "model": model_name,
        "mode": mode,
        "prompt": description,
        "sample_rate": model.sample_rate,
        "limitations": [
            "MusicGen is guided by text and/or melody; it does not clone the full production mix.",
            "For exact reference-style groove, combine this with explicit drum/bass pattern extraction.",
        ],
    }


def _load_audio(path: str, target_channels: int):
    import torch
    import torchaudio

    _require_file(path)
    wav_path = path
    cleanup_path = None
    if Path(path).suffix.lower() != ".wav":
        cleanup_path = str(Path("/tmp") / f"prompt2midi-audiocraft-reference-{os.getpid()}.wav")
        ffmpeg = os.environ.get("PROMPT2MIDI_FFMPEG") or shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg is required to decode non-WAV references.")
        subprocess.run(
            [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", path, cleanup_path],
            check=True,
        )
        wav_path = cleanup_path
    try:
        wav, sample_rate = torchaudio.load(wav_path)
    finally:
        if cleanup_path:
            try:
                os.remove(cleanup_path)
            except OSError:
                pass

    if wav.shape[0] > target_channels:
        wav = wav[:target_channels]
    elif wav.shape[0] < target_channels:
        wav = wav.mean(dim=0, keepdim=True).repeat(target_channels, 1)
    if not torch.isfinite(wav).all():
        raise RuntimeError("Reference audio contains invalid samples.")
    return wav, sample_rate


def _style_prompt(prompt: str) -> str:
    base = prompt.strip()
    if not base:
        base = "reference-inspired instrumental music"
    return (
        f"{base}. Producer-grade original instrumental guide track, same tempo and key area as the reference, "
        "clear drums, defined bassline, stable tonal harmony, recognizable hook role, clean mix, "
        "no copied lyrics, no copied singer identity, no warped vocals, no random glitches, no atonal artifacts."
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


def _token_progress(done: int, total: int) -> None:
    if total <= 0:
        _progress(f"audiocraft: generated {done} tokens")
        return
    percent = min(100.0, max(0.0, done * 100.0 / total))
    _progress(f"audiocraft: {done}/{total} tokens ({percent:.1f}%)")


def _require_file(path: str) -> None:
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(f"Reference audio file not found: {path}")


def _progress(message: str) -> None:
    print(f"progress: {message}", file=sys.stderr, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a MusicGen sample using official AudioCraft.")
    parser.add_argument("--reference")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--prompt", default="")
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION_SECONDS)
    parser.add_argument("--model", default=os.environ.get("PROMPT2MIDI_AUDIOCRAFT_MODEL") or DEFAULT_MODEL)
    parser.add_argument("--mode", choices=("melody", "continuation", "text"), default="melody")
    args = parser.parse_args()

    try:
        payload = {
            "ok": True,
            "audio": generate_sample(
                reference_audio=args.reference,
                output_dir=args.output_dir,
                prompt=args.prompt,
                model_name=args.model,
                duration_seconds=args.duration,
                mode=args.mode,
            ),
        }
    except Exception as exc:
        payload = {"ok": False, "error": {"code": "audiocraft_musicgen_failed", "message": str(exc)}}

    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True))
    sys.stdout.write("\n")
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
