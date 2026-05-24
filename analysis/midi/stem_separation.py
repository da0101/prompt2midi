#!/usr/bin/env python3
"""Optional local source separation using a Demucs engine."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

KNOWN_DEMUCS_STEMS = ("bass", "drums", "other", "vocals", "guitar", "piano")


def separate_for_transcription(audio_path: str, output_dir: str, source_stage: str = "analysis_input") -> dict:
    if os.environ.get("PROMPT2MIDI_DISABLE_STEMS") == "1":
        _progress("stem separation: disabled by environment")
        return {
            "available": False,
            "method": "disabled",
            "source_audio": os.path.abspath(audio_path),
            "source_stage": source_stage,
            "stems": {},
            "warnings": ["Stem separation disabled by PROMPT2MIDI_DISABLE_STEMS."],
        }

    engine = _find_demucs()
    if engine is None:
        _progress("stem separation: Demucs not installed")
        return {
            "available": False,
            "method": _method_name(),
            "source_audio": os.path.abspath(audio_path),
            "source_stage": source_stage,
            "stems": {},
            "warnings": ["Stem separation engine not installed. Run npm run setup:stems."],
        }

    output_path = Path(output_dir)
    demucs_root = output_path / "demucs"
    stable_root = output_path / "stems"
    demucs_root.mkdir(parents=True, exist_ok=True)
    stable_root.mkdir(parents=True, exist_ok=True)

    timeout = _timeout_seconds()
    stem_mode = os.environ.get("PROMPT2MIDI_STEM_MODE") or "full"
    model = _demucs_model()
    _progress(f"stem separation: running Demucs {model} {stem_mode} split")
    command = [engine, "-n", model, "-o", str(demucs_root), audio_path]
    if stem_mode == "bass":
        command.insert(1, "--two-stems=bass")
    env = os.environ.copy()
    cache_root = output_path.parent / "_model-cache"
    env["TMPDIR"] = str(output_path / "demucs-runtime")
    env["TORCH_HOME"] = str(cache_root / "torch")
    env["XDG_CACHE_HOME"] = str(cache_root / "xdg")
    env.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

    try:
        completed = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        _progress("stem separation: Demucs timed out")
        return {
            "available": False,
            "method": _method_name(model),
            "source_audio": os.path.abspath(audio_path),
            "source_stage": source_stage,
            "stems": {},
            "warnings": [f"Stem separation timed out after {timeout} seconds."],
        }

    if completed.returncode != 0:
        _progress("stem separation: Demucs failed")
        return {
            "available": False,
            "method": _method_name(model),
            "source_audio": os.path.abspath(audio_path),
            "source_stage": source_stage,
            "stems": {},
            "warnings": ["Stem separation failed: " + _last_error(completed.stderr or completed.stdout)],
        }

    stems = {}
    for name in KNOWN_DEMUCS_STEMS:
        source = _find_stem(demucs_root, f"{name}.wav")
        if source is not None:
            stable = stable_root / f"{name}.wav"
            shutil.copyfile(source, stable)
            stems[name] = os.path.abspath(stable)

    if not stems:
        _progress("stem separation: Demucs finished but no recognized stems were found")
        return {
            "available": False,
            "method": _method_name(model),
            "source_audio": os.path.abspath(audio_path),
            "source_stage": source_stage,
            "stems": {},
            "warnings": ["Stem separation completed but did not produce recognized stem files."],
        }

    _progress(f"stem separation: produced stems {', '.join(sorted(stems))}")
    return {
        "available": True,
        "method": _method_name(model),
        "source_audio": os.path.abspath(audio_path),
        "source_stage": source_stage,
        "stems": stems,
        "warnings": [
            "Stems are source-separated by Demucs and can still contain bleed, artifacts, or missing energy between instruments."
        ],
    }


def _find_demucs() -> str | None:
    configured = os.environ.get("PROMPT2MIDI_DEMUCS") or os.environ.get("PROMPT2MIDI_STEM_ENGINE")
    if configured:
        return configured if os.path.exists(configured) and os.access(configured, os.X_OK) else None
    candidates = []
    repo_engine = Path(__file__).resolve().parents[2] / ".venv-stems" / "bin" / "demucs"
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


def _demucs_model() -> str:
    return os.environ.get("PROMPT2MIDI_DEMUCS_MODEL") or os.environ.get("PROMPT2MIDI_STEM_MODEL") or "htdemucs"


def _method_name(model: str | None = None) -> str:
    return f"demucs_{model or _demucs_model()}"


def _find_stem(directory: Path, filename: str) -> str | None:
    matches = sorted(directory.glob(f"**/{filename}"), key=lambda path: path.stat().st_mtime, reverse=True)
    return str(matches[0]) if matches else None


def _last_error(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-1] if lines else "unknown error"


def _progress(message: str) -> None:
    print(f"progress: {message}", file=sys.stderr, flush=True)
