#!/usr/bin/env python3
"""Run the Hugging Face DrumSep ONNX model locally.

The published model expects two inputs:
- waveform: stereo 44.1 kHz audio, exactly 1,764,000 samples (40 seconds)
- magnitude: STFT complex channels for the same audio

It returns a time-domain tensor with four drum elements. We chunk longer drum
stems into 40-second windows and write kick/snare/cymbals/toms WAV files.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import soundfile as sf
from huggingface_hub import hf_hub_download
from onnx import TensorProto, helper
from scipy import signal


MODEL_ID = "splitzo/drumsep"
MODEL_FILE = "drumsep.onnx"
MODEL_SAMPLE_RATE = 44100
SEGMENT_SAMPLES = 1_764_000
N_FFT = 4096
HOP_LENGTH = 1024
STEM_NAMES = ("kick", "snare", "cymbals", "toms")


def main() -> int:
    parser = argparse.ArgumentParser(description="Separate a drum stem into kick/snare/cymbals/toms with DrumSep ONNX.")
    parser.add_argument("--input", required=True, help="Input drum stem WAV/AIFF/FLAC/etc.")
    parser.add_argument("--output-dir", required=True, help="Output directory for separated WAV files.")
    parser.add_argument("--model-path", default=None, help="Optional local drumsep.onnx path.")
    args = parser.parse_args()

    payload = run_drumsep(args.input, args.output_dir, model_path=args.model_path)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def run_drumsep(input_path: str, output_dir: str, model_path: str | None = None) -> dict:
    source = Path(input_path)
    if not source.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    model = Path(model_path) if model_path else resolve_model_path()
    patched_model = ensure_cpu_compatible_model(model, out / "drumsep-patched.onnx")
    session = ort.InferenceSession(str(patched_model), providers=["CPUExecutionProvider"])

    audio, source_rate = sf.read(str(source), always_2d=True, dtype="float32")
    audio = audio[:, :2]
    if audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)
    original_length = len(audio)
    if source_rate != MODEL_SAMPLE_RATE:
        audio_441 = resample_audio(audio, source_rate, MODEL_SAMPLE_RATE)
    else:
        audio_441 = audio

    separated_441 = separate_audio_441(session, audio_441)
    if source_rate != MODEL_SAMPLE_RATE:
        separated = np.stack(
            [resample_audio(stem, MODEL_SAMPLE_RATE, source_rate)[:original_length] for stem in separated_441],
            axis=0,
        )
    else:
        separated = separated_441[:, :original_length]

    stem_paths: dict[str, str] = {}
    for index, name in enumerate(STEM_NAMES):
        stem_audio = np.asarray(np.clip(separated[index], -1.0, 1.0), dtype=np.float32)
        path = out / f"{name}.wav"
        sf.write(str(path), stem_audio, source_rate, subtype="PCM_16")
        stem_paths[name] = str(path.resolve())

    return {
        "available": True,
        "method": "drumsep_onnx",
        "model": str(model.resolve()),
        "patched_model": str(patched_model.resolve()),
        "source_audio": str(source.resolve()),
        "sample_rate": int(source_rate),
        "duration_seconds": round(original_length / float(source_rate), 3),
        "stems": stem_paths,
        "warnings": [
            "Drum element stems are AI-separated and can contain bleed or missing transients; review in Ableton."
        ],
    }


def separate_audio_441(session: ort.InferenceSession, audio: np.ndarray) -> np.ndarray:
    total = len(audio)
    output = np.zeros((len(STEM_NAMES), max(total, 1), 2), dtype=np.float32)
    cursor = 0
    while cursor < total:
        chunk = audio[cursor : cursor + SEGMENT_SAMPLES]
        valid = len(chunk)
        if valid < SEGMENT_SAMPLES:
            chunk = np.pad(chunk, ((0, SEGMENT_SAMPLES - valid), (0, 0)), mode="constant")
        waveform = np.transpose(chunk, (1, 0))[None, :, :].astype(np.float32)
        magnitude = complex_stft_channels(chunk)[None, :, :, :].astype(np.float32)
        result = session.run(None, {"waveform": waveform, "magnitude": magnitude})
        time_output = np.asarray(result[1], dtype=np.float32)[0]
        time_output = np.transpose(time_output, (0, 2, 1))
        output[:, cursor : cursor + valid, :] = time_output[:, :valid, :]
        cursor += SEGMENT_SAMPLES
    return output


def complex_stft_channels(audio: np.ndarray) -> np.ndarray:
    if audio.shape != (SEGMENT_SAMPLES, 2):
        raise ValueError(f"Expected chunk shape {(SEGMENT_SAMPLES, 2)}, got {audio.shape}")
    window = signal.get_window("hann", N_FFT, fftbins=True).astype(np.float32)
    channels = []
    for channel in range(2):
        padded = np.pad(audio[:, channel], (N_FFT // 2, N_FFT // 2), mode="reflect")
        frame_count = 1 + (len(padded) - N_FFT) // HOP_LENGTH
        strides = (padded.strides[0] * HOP_LENGTH, padded.strides[0])
        frames = np.lib.stride_tricks.as_strided(padded, shape=(frame_count, N_FFT), strides=strides)
        spec = np.fft.rfft(frames * window[None, :], n=N_FFT, axis=1).T[:2048]
        channels.extend([spec.real, spec.imag])
    return np.asarray(channels, dtype=np.float32)


def resample_audio(audio: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    gcd = int(np.gcd(source_rate, target_rate))
    up = target_rate // gcd
    down = source_rate // gcd
    return signal.resample_poly(audio, up, down, axis=0).astype(np.float32)


def resolve_model_path() -> Path:
    repo_patched = Path(__file__).resolve().parents[2] / ".cache" / "drumsep" / "drumsep-patched.onnx"
    if repo_patched.exists():
        return repo_patched
    cached = cached_model_path()
    if cached:
        return cached
    try:
        return Path(hf_hub_download(MODEL_ID, MODEL_FILE, local_files_only=True))
    except Exception:
        return Path(hf_hub_download(MODEL_ID, MODEL_FILE))


def cached_model_path() -> Path | None:
    cache_home = Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface")
    root = cache_home / "hub" / "models--splitzo--drumsep"
    candidates = sorted(root.glob(f"snapshots/*/{MODEL_FILE}"), key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def ensure_cpu_compatible_model(model_path: Path, patched_path: Path) -> Path:
    if model_path.name == "drumsep-patched.onnx":
        return model_path
    patched_path.parent.mkdir(parents=True, exist_ok=True)
    if patched_path.exists() and patched_path.stat().st_mtime >= model_path.stat().st_mtime:
        return patched_path
    try:
        ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        shutil.copyfile(model_path, patched_path)
        return patched_path
    except Exception:
        patch_eyelike_nodes(model_path, patched_path)
        return patched_path


def patch_eyelike_nodes(source_path: Path, target_path: Path) -> None:
    model = onnx.load(str(source_path))
    new_nodes = []
    patched = 0
    for node in model.graph.node:
        if node.op_type != "EyeLike":
            new_nodes.append(node)
            continue
        patched += 1
        prefix = node.name or f"EyeLikePatch_{patched}"
        input_name = node.input[0]
        output_name = node.output[0]
        shape = f"{prefix}/Shape"
        idx0 = f"{prefix}/idx0"
        idx1 = f"{prefix}/idx1"
        zero = f"{prefix}/zero"
        one = f"{prefix}/one"
        dim0 = f"{prefix}/dim0"
        dim1 = f"{prefix}/dim1"
        range0 = f"{prefix}/range0"
        range1 = f"{prefix}/range1"
        axes1 = f"{prefix}/axes1"
        axes0 = f"{prefix}/axes0"
        unsq0 = f"{prefix}/unsq0"
        unsq1 = f"{prefix}/unsq1"
        new_nodes.extend(
            [
                helper.make_node("Shape", [input_name], [shape], name=f"{prefix}/Shape"),
                _const_i64(idx0, [], [0]),
                _const_i64(idx1, [], [1]),
                _const_i64(zero, [], [0]),
                _const_i64(one, [], [1]),
                helper.make_node("Gather", [shape, idx0], [dim0], name=f"{prefix}/Gather0", axis=0),
                helper.make_node("Gather", [shape, idx1], [dim1], name=f"{prefix}/Gather1", axis=0),
                helper.make_node("Range", [zero, dim0, one], [range0], name=f"{prefix}/Range0"),
                helper.make_node("Range", [zero, dim1, one], [range1], name=f"{prefix}/Range1"),
                _const_i64(axes1, [1], [1]),
                _const_i64(axes0, [1], [0]),
                helper.make_node("Unsqueeze", [range0, axes1], [unsq0], name=f"{prefix}/Unsqueeze0"),
                helper.make_node("Unsqueeze", [range1, axes0], [unsq1], name=f"{prefix}/Unsqueeze1"),
                helper.make_node("Equal", [unsq0, unsq1], [output_name], name=f"{prefix}/Equal"),
            ]
        )
    model.graph.ClearField("node")
    model.graph.node.extend(new_nodes)
    onnx.save(model, str(target_path))


def _const_i64(name: str, dims: list[int], values: list[int]):
    return helper.make_node(
        "Constant",
        [],
        [name],
        name=f"{name}/Constant",
        value=helper.make_tensor(f"{name}_value", TensorProto.INT64, dims, values),
    )


if __name__ == "__main__":
    raise SystemExit(main())
