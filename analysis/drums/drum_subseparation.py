#!/usr/bin/env python3
"""Optional drum-element separation for kick/snare/cymbals/toms.

The preferred model target is DrumSep ONNX from Hugging Face:
https://huggingface.co/splitzo/drumsep

This module intentionally treats the separator as an optional local engine.
If the model runner is not installed, callers receive an unavailable result
and can fall back to frequency-band pseudo stems.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.io import wavfile


DRUMSEP_STEMS = ("kick", "snare", "cymbals", "toms")
DRUMSEP_MODEL_ID = "splitzo/drumsep"
DRUMSEP_MODEL_FILE = "drumsep.onnx"


def separate_drum_elements(drum_stem_path: str, output_dir: str) -> dict:
    source = Path(drum_stem_path)
    if not source.exists():
        return _unavailable("drum_stem_missing", f"Drum stem not found: {drum_stem_path}")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    engine = _find_engine()
    if not engine:
        return _unavailable(
            "engine_missing",
            "DrumSep engine is not installed. Configure PROMPT2MIDI_DRUMSEP_COMMAND or run setup once a runner is available.",
        )

    command = _build_command(engine, str(source.resolve()), str(out.resolve()))
    try:
        completed = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[2],
            env=os.environ.copy(),
            text=True,
            capture_output=True,
            timeout=_timeout_seconds(),
        )
    except subprocess.TimeoutExpired:
        return _unavailable("timeout", f"Drum sub-separation timed out after {_timeout_seconds()} seconds.")

    if completed.returncode != 0:
        return _unavailable("engine_failed", _last_error(completed.stderr or completed.stdout))

    stems = _collect_outputs(out)
    if not stems:
        return _unavailable("no_outputs", "DrumSep finished but no kick/snare/cymbals/toms WAV files were found.")
    quality = _quality_check(source, stems)
    if not quality["usable"]:
        result = _unavailable("quality_gate_failed", quality["message"])
        result["rejected_stems"] = stems
        result["quality"] = quality
        return result

    return {
        "available": True,
        "method": _method_name(engine),
        "source_audio": str(source.resolve()),
        "stems": stems,
        "quality": quality,
        "warnings": [
            "Drum element stems are AI-separated and can contain bleed or missing transients; review in Ableton."
        ],
    }


def _find_engine() -> str | None:
    configured = os.environ.get("PROMPT2MIDI_DRUMSEP_COMMAND")
    if configured:
        return configured
    repo_runner = Path(__file__).resolve().parents[2] / ".venv-drumsep" / "bin" / "prompt2midi-drumsep"
    if repo_runner.exists() and os.access(repo_runner, os.X_OK):
        return str(repo_runner)
    for name in ("prompt2midi-drumsep", "drumsep", "drumsep-onnx"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _build_command(engine: str, input_path: str, output_dir: str) -> list[str]:
    if "{input}" in engine or "{output}" in engine:
        return [part.format(input=input_path, output=output_dir) for part in engine.split()]
    return [engine, "--input", input_path, "--output-dir", output_dir]


def _collect_outputs(output_dir: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    for stem in DRUMSEP_STEMS:
        matches = sorted(
            list(output_dir.glob(f"**/{stem}.wav")) + list(output_dir.glob(f"**/*{stem}*.wav")),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if matches:
            stable = output_dir / f"{stem}.wav"
            if matches[0] != stable:
                shutil.copyfile(matches[0], stable)
            found[stem] = str(stable.resolve())
    return found


def _timeout_seconds() -> int:
    configured = os.environ.get("PROMPT2MIDI_DRUMSEP_TIMEOUT_SECONDS")
    if not configured:
        return 600
    try:
        return max(60, int(configured))
    except ValueError:
        return 600


def _method_name(engine: str) -> str:
    name = Path(engine.split()[0]).name
    if "drumsep" in name:
        return "drumsep_onnx"
    return f"external_{name}"


def _unavailable(reason: str, message: str) -> dict:
    return {
        "available": False,
        "method": "drumsep_onnx",
        "stems": {},
        "reason": reason,
        "warnings": [message],
        "model": {
            "id": DRUMSEP_MODEL_ID,
            "file": DRUMSEP_MODEL_FILE,
            "expected_stems": list(DRUMSEP_STEMS),
        },
    }


def _quality_check(source: Path, stems: dict[str, str]) -> dict:
    try:
        source_rate, source_data = wavfile.read(str(source))
        source_rms = _audio_rms(source_data)
        metrics = {}
        for role, path in stems.items():
            rate, data = wavfile.read(path)
            metrics[role] = {
                "sample_rate": int(rate),
                "rms": _audio_rms(data),
                "rms_ratio_to_drums": _audio_rms(data) / max(source_rms, 1e-9),
            }
    except Exception as exc:
        return {"usable": False, "message": f"Could not quality-check DrumSep outputs: {exc}", "metrics": {}}

    cymbals_ratio = metrics.get("cymbals", {}).get("rms_ratio_to_drums", 0.0)
    if cymbals_ratio < 0.01:
        return {
            "usable": False,
            "message": (
                "DrumSep output failed quality gate: cymbals/hats lane is effectively silent. "
                "Use the grid drum control split or another separator instead."
            ),
            "metrics": metrics,
        }
    return {"usable": True, "message": "DrumSep output passed basic energy checks.", "metrics": metrics}


def _audio_rms(data) -> float:
    samples = np.asarray(data)
    if samples.size == 0:
        return 0.0
    if np.issubdtype(samples.dtype, np.integer):
        info = np.iinfo(samples.dtype)
        samples = samples.astype(np.float32) / float(max(abs(info.min), abs(info.max)))
    else:
        samples = samples.astype(np.float32)
    if samples.ndim > 1:
        samples = np.mean(samples, axis=1)
    return float(np.sqrt(np.mean(np.square(samples.astype(np.float64)))))


def _last_error(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-1] if lines else "unknown error"


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run optional DrumSep drum-element separation.")
    parser.add_argument("--input", required=True, help="Input drum stem WAV.")
    parser.add_argument("--output-dir", required=True, help="Output directory for kick/snare/cymbals/toms WAVs.")
    args = parser.parse_args()
    result = separate_drum_elements(args.input, args.output_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("available") else 2


if __name__ == "__main__":
    raise SystemExit(main())
