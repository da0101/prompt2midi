#!/usr/bin/env python3
"""Optional local source separation using a Demucs engine."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def separate_for_transcription(audio_path: str, output_dir: str) -> dict:
    if os.environ.get("PROMPT2MIDI_DISABLE_STEMS") == "1":
        return {
            "available": False,
            "method": "disabled",
            "stems": {},
            "warnings": ["Stem separation disabled by PROMPT2MIDI_DISABLE_STEMS."],
        }

    engine = _find_demucs()
    if engine is None:
        return {
            "available": False,
            "method": "demucs_htdemucs",
            "stems": {},
            "warnings": ["Stem separation engine not installed. Run npm run setup:stems."],
        }

    output_path = Path(output_dir)
    demucs_root = output_path / "demucs"
    stable_root = output_path / "stems"
    demucs_root.mkdir(parents=True, exist_ok=True)
    stable_root.mkdir(parents=True, exist_ok=True)

    timeout = _timeout_seconds()
    command = [
        engine,
        "--two-stems=bass",
        "-n",
        "htdemucs",
        "-o",
        str(demucs_root),
        audio_path,
    ]
    env = os.environ.copy()
    cache_root = output_path.parent / "_model-cache"
    env["TMPDIR"] = str(output_path / "demucs-runtime")
    env["TORCH_HOME"] = str(cache_root / "torch")
    env["XDG_CACHE_HOME"] = str(cache_root / "xdg")
    env.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

    try:
        completed = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parent.parent,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "available": False,
            "method": "demucs_htdemucs",
            "stems": {},
            "warnings": [f"Stem separation timed out after {timeout} seconds."],
        }

    if completed.returncode != 0:
        return {
            "available": False,
            "method": "demucs_htdemucs",
            "stems": {},
            "warnings": ["Stem separation failed: " + _last_error(completed.stderr or completed.stdout)],
        }

    bass_source = _find_stem(demucs_root, "bass.wav")
    if bass_source is None:
        return {
            "available": False,
            "method": "demucs_htdemucs",
            "stems": {},
            "warnings": ["Stem separation completed but did not produce bass.wav."],
        }

    stable_bass = stable_root / "bass.wav"
    shutil.copyfile(bass_source, stable_bass)
    return {
        "available": True,
        "method": "demucs_htdemucs",
        "stems": {"bass": os.path.abspath(stable_bass)},
        "warnings": [
            "Bass stem is source-separated by Demucs and can still contain kick, guitar, vocal, or synth bleed."
        ],
    }


def _find_demucs() -> str | None:
    configured = os.environ.get("PROMPT2MIDI_DEMUCS") or os.environ.get("PROMPT2MIDI_STEM_ENGINE")
    if configured:
        return configured if os.path.exists(configured) and os.access(configured, os.X_OK) else None
    candidates = []
    repo_engine = Path(__file__).resolve().parent.parent / ".venv-stems" / "bin" / "demucs"
    candidates.extend([str(repo_engine), shutil.which("demucs")])
    for candidate in candidates:
        if candidate and os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _timeout_seconds() -> int:
    configured = os.environ.get("PROMPT2MIDI_STEM_TIMEOUT_SECONDS")
    if not configured:
        return 360
    try:
        return max(30, int(configured))
    except ValueError:
        return 360


def _find_stem(directory: Path, filename: str) -> str | None:
    matches = sorted(directory.glob(f"**/{filename}"), key=lambda path: path.stat().st_mtime, reverse=True)
    return str(matches[0]) if matches else None


def _last_error(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-1] if lines else "unknown error"
