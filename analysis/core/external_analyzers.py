#!/usr/bin/env python3
"""Optional external MIR analyzer adapters.

These adapters are intentionally capability-gated. The core pipeline must keep
working when All-In-One or Essentia are not installed.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


def analyze_allin1_structure(audio_path: str, output_dir: str) -> dict:
    """Run All-In-One Music Structure Analyzer when available."""
    if os.environ.get("PROMPT2MIDI_DISABLE_ALLIN1") == "1":
        return _unavailable("allin1", "disabled by PROMPT2MIDI_DISABLE_ALLIN1")
    if os.environ.get("PROMPT2MIDI_ENABLE_ALLIN1_DOCKER") == "1":
        return _run_allin1_docker(audio_path, output_dir)
    if os.environ.get("PROMPT2MIDI_ENABLE_ALLIN1") != "1" and not os.environ.get("PROMPT2MIDI_ALLIN1"):
        return _unavailable("allin1", "All-In-One analyzer is disabled by default; set PROMPT2MIDI_ENABLE_ALLIN1=1 to run it.")
    executable = _find_executable("PROMPT2MIDI_ALLIN1", "allin1")
    if not executable:
        return _unavailable("allin1", "All-In-One analyzer is not installed")

    out_dir = Path(output_dir) / "external" / "allin1"
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = out_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    timeout = float(os.environ.get("PROMPT2MIDI_ALLIN1_TIMEOUT_SECONDS") or "900")
    command = [
        executable,
        audio_path,
        "--out-dir",
        str(out_dir),
        "--demix-dir",
        str(out_dir / "demix"),
        "--spec-dir",
        str(out_dir / "spec"),
        "--overwrite",
        "--no-multiprocess",
    ]
    env = os.environ.copy()
    env.setdefault("TORCH_HOME", str(cache_dir / "torch"))
    env.setdefault("MPLCONFIGDIR", str(cache_dir / "matplotlib"))
    env.setdefault("NUMBA_CACHE_DIR", str(cache_dir / "numba"))
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=env)
    except Exception as exc:
        return _unavailable("allin1", f"All-In-One failed to start: {exc}")
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        return _unavailable("allin1", f"All-In-One exited with code {completed.returncode}: {detail[:500]}")

    result_path = _latest_json(out_dir)
    if not result_path:
        return _unavailable("allin1", "All-In-One finished without a JSON result")
    return _read_allin1_result(result_path, "allin1")


def _run_allin1_docker(audio_path: str, output_dir: str) -> dict:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "pipelines" / "run-allin1-docker.sh"
    if not script.exists():
        return _unavailable("allin1_docker", "Docker All-In-One wrapper is missing")
    if not os.access(script, os.X_OK):
        return _unavailable("allin1_docker", "Docker All-In-One wrapper is not executable")

    timeout = float(os.environ.get("PROMPT2MIDI_ALLIN1_DOCKER_TIMEOUT_SECONDS") or "300")
    audio = Path(audio_path).resolve()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    command = [str(script), str(audio), str(output), str(timeout)]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout + 120,
            cwd=str(repo_root),
        )
    except Exception as exc:
        return _unavailable("allin1_docker", f"Docker All-In-One failed to start: {exc}")

    envelope = _json_from_stdout(completed.stdout)
    if completed.returncode != 0:
        detail = _docker_failure_detail(envelope, completed)
        return _unavailable("allin1_docker", f"Docker All-In-One exited with code {completed.returncode}: {detail[:700]}")
    if not envelope.get("ok"):
        detail = _docker_failure_detail(envelope, completed)
        return _unavailable("allin1_docker", f"Docker All-In-One did not return a usable result: {detail[:700]}")

    result_value = envelope.get("result_path")
    result_path = _host_path_from_docker(result_value, repo_root, output) if result_value else None
    if not result_path or not result_path.exists():
        result_path = _latest_json(output / "external" / "allin1-docker")
    if not result_path:
        return _unavailable("allin1_docker", "Docker All-In-One finished without a JSON result")
    return _read_allin1_result(result_path, "allin1_docker")


def _read_allin1_result(result_path: Path, method: str) -> dict:
    try:
        raw = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _unavailable(method, f"Could not parse All-In-One JSON: {exc}")

    structure = _structure_from_allin1(raw)
    return {
        "available": True,
        "method": method,
        "path": str(result_path.resolve()),
        "bpm": raw.get("bpm"),
        "beats": raw.get("beats") or [],
        "downbeats": raw.get("downbeats") or [],
        "beat_positions": raw.get("beat_positions") or [],
        "structure": structure,
        "warnings": [],
    }


def analyze_essentia_descriptors(audio_path: str, output_dir: str) -> dict:
    """Run Essentia MusicExtractor CLI when available."""
    if os.environ.get("PROMPT2MIDI_DISABLE_ESSENTIA") == "1":
        return _unavailable("essentia", "disabled by PROMPT2MIDI_DISABLE_ESSENTIA")
    executable = _find_executable("PROMPT2MIDI_ESSENTIA_EXTRACTOR", "essentia_streaming_extractor_music")
    if not executable:
        return _unavailable("essentia", "Essentia MusicExtractor is not installed")

    out_dir = Path(output_dir) / "external" / "essentia"
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / "music-extractor.json"
    timeout = float(os.environ.get("PROMPT2MIDI_ESSENTIA_TIMEOUT_SECONDS") or "600")
    command = [executable, audio_path, str(result_path)]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        return _unavailable("essentia", f"Essentia failed to start: {exc}")
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        return _unavailable("essentia", f"Essentia exited with code {completed.returncode}: {detail[:500]}")

    try:
        raw = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _unavailable("essentia", f"Could not parse Essentia JSON: {exc}")

    descriptors = _compact_essentia(raw)
    return {
        "available": True,
        "method": "essentia_streaming_extractor_music",
        "path": str(result_path.resolve()),
        "descriptors": descriptors,
        "warnings": [],
    }


def _structure_from_allin1(raw: dict) -> dict:
    beats = raw.get("beats") or []
    downbeats = raw.get("downbeats") or []
    segments = raw.get("segments") or []
    sections = []
    for index, segment in enumerate(segments):
        start = _number(segment.get("start"), 0.0)
        end = _number(segment.get("end"), start)
        if end <= start:
            continue
        sections.append(
            {
                "start": round(start, 3),
                "end": round(end, 3),
                "label": str(segment.get("label") or f"section_{index + 1}"),
                "energy": _energy_for_functional_label(str(segment.get("label") or "")),
                "source": "allin1",
            }
        )
    return {
        "sections": sections,
        "section_count": len(sections),
        "estimated_bars": len(downbeats) if downbeats else max(0, len(beats) // 4),
        "arrangement_arc": "functional sections from All-In-One",
        "energy_profile": "derived from functional labels",
        "method": "allin1_functional_segmentation",
        "beats": beats,
        "downbeats": downbeats,
        "beat_positions": raw.get("beat_positions") or [],
    }


def _compact_essentia(raw: dict) -> dict:
    low = raw.get("lowlevel") or {}
    rhythm = raw.get("rhythm") or {}
    tonal = raw.get("tonal") or {}
    highlevel = raw.get("highlevel") or {}
    return {
        "rhythm": {
            "bpm": rhythm.get("bpm"),
            "danceability": rhythm.get("danceability"),
            "onset_rate": rhythm.get("onset_rate"),
        },
        "tonal": {
            "key_key": tonal.get("key_key"),
            "key_scale": tonal.get("key_scale"),
            "key_strength": tonal.get("key_strength"),
            "chords_key": tonal.get("chords_key"),
            "chords_scale": tonal.get("chords_scale"),
            "chords_changes_rate": tonal.get("chords_changes_rate"),
        },
        "mix": {
            "average_loudness": low.get("average_loudness"),
            "dynamic_complexity": low.get("dynamic_complexity"),
            "spectral_centroid": low.get("spectral_centroid", {}).get("mean") if isinstance(low.get("spectral_centroid"), dict) else None,
            "silence_rate_60dB": low.get("silence_rate_60dB", {}).get("mean") if isinstance(low.get("silence_rate_60dB"), dict) else None,
        },
        "highlevel": _compact_highlevel(highlevel),
        "producer_descriptors": _producer_descriptors(low, rhythm, tonal, highlevel),
    }


def _compact_highlevel(highlevel: dict) -> dict:
    compact = {}
    for key, value in highlevel.items():
        if not isinstance(value, dict):
            continue
        if "value" in value:
            compact[key] = {"value": value.get("value"), "probability": value.get("probability")}
    return compact


def _producer_descriptors(low: dict, rhythm: dict, tonal: dict, highlevel: dict) -> dict:
    centroid = low.get("spectral_centroid", {}).get("mean") if isinstance(low.get("spectral_centroid"), dict) else None
    danceability = rhythm.get("danceability")
    dynamic = low.get("dynamic_complexity")
    return {
        "brightness": _brightness(centroid),
        "dancefloor_read": "danceable" if _number(danceability, 0.0) >= 1.0 else "uncertain",
        "dynamic_shape": "compressed/steady" if _number(dynamic, 0.0) < 3.0 else "dynamic",
        "tonal_strength": "strong" if _number(tonal.get("key_strength"), 0.0) >= 0.6 else "moderate/uncertain",
        "electronicness": _highlevel_value(highlevel, "electronic"),
        "acousticness": _highlevel_value(highlevel, "acoustic"),
    }


def _highlevel_value(highlevel: dict, needle: str) -> str | None:
    for key, value in highlevel.items():
        if needle in key.lower() and isinstance(value, dict):
            return str(value.get("value"))
    return None


def _brightness(centroid) -> str:
    value = _number(centroid, 0.0)
    if value <= 0:
        return "unknown"
    if value >= 2500:
        return "bright"
    if value <= 1200:
        return "dark/warm"
    return "balanced"


def _energy_for_functional_label(label: str) -> float:
    text = label.lower()
    if any(word in text for word in ("drop", "chorus", "hook")):
        return 0.95
    if any(word in text for word in ("break", "bridge")):
        return 0.25
    if "intro" in text or "outro" in text or "start" in text or "end" in text:
        return 0.35
    if "verse" in text or "groove" in text:
        return 0.7
    return 0.6


def _find_executable(env_name: str, fallback_name: str) -> str | None:
    configured = os.environ.get(env_name)
    candidates = [configured] if configured else []
    candidates.append(shutil.which(fallback_name))
    repo_root = Path(__file__).resolve().parents[2]
    candidates.append(str(repo_root / f".venv-{fallback_name}" / "bin" / fallback_name))
    for candidate in candidates:
        if candidate and os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _latest_json(directory: Path) -> Path | None:
    if not directory.exists():
        return None
    matches = sorted(directory.rglob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _json_from_stdout(stdout: str | None) -> dict:
    for line in reversed((stdout or "").splitlines()):
        text = line.strip()
        if not text.startswith("{"):
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _docker_failure_detail(envelope: dict, completed: subprocess.CompletedProcess) -> str:
    parts = [
        str(envelope.get("error") or ""),
        str(envelope.get("stderr_tail") or ""),
        str(envelope.get("stdout_tail") or ""),
        completed.stderr or "",
        completed.stdout or "",
    ]
    return " ".join(part.strip() for part in parts if part and part.strip()) or "no diagnostic output"


def _host_path_from_docker(path_value: str | None, repo_root: Path, output_root: Path | None = None) -> Path | None:
    if not path_value:
        return None
    if path_value == "/workspace":
        return repo_root
    if path_value.startswith("/workspace/"):
        return repo_root / path_value[len("/workspace/") :]
    if output_root and path_value == "/job":
        return output_root
    if output_root and path_value.startswith("/job/"):
        return output_root / path_value[len("/job/") :]
    return Path(path_value)


def _unavailable(method: str, reason: str) -> dict:
    return {"available": False, "method": method, "warnings": [reason]}


def _number(value, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
