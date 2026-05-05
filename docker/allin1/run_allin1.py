#!/usr/bin/env python3
"""Run All-In-One inside the prompt2midi Docker worker."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--timeout", type=float, default=1800.0)
    args = parser.parse_args()

    audio_path = Path(args.audio)
    output_dir = Path(args.output_dir)
    run_dir = output_dir / "external" / "allin1-docker"
    run_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    cache_dir = Path("/workspace/.cache/docker/allin1")
    env.setdefault("TORCH_HOME", str(cache_dir / "torch"))
    env.setdefault("MPLCONFIGDIR", str(cache_dir / "matplotlib"))
    env.setdefault("NUMBA_CACHE_DIR", str(cache_dir / "numba"))
    env.setdefault("HF_HOME", str(cache_dir / "huggingface"))
    env.setdefault("XDG_CACHE_HOME", str(cache_dir / "xdg"))

    executable = env.get("PROMPT2MIDI_DOCKER_ALLIN1_COMMAND", "allin1fix")
    device = env.get("PROMPT2MIDI_DOCKER_ALLIN1_DEVICE", "cpu")
    stems_dir = _find_stems_dir(output_dir, audio_path, env)
    command = [
        executable,
        "--out-dir",
        str(run_dir),
        "--demix-dir",
        str(run_dir / "demix"),
        "--spec-dir",
        str(run_dir / "spec"),
        "--overwrite",
        "--no-multiprocess",
    ]
    if stems_dir:
        command.extend(["--stems-from-dir", str(stems_dir), "--stems-id", audio_path.stem, "--no-demucs"])
    else:
        command.insert(1, str(audio_path))
    if device:
        command.extend(["--device", device])
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout, env=env)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"All-In-One failed to start: {exc}"}))
        return 1

    if completed.returncode != 0:
        print(
            json.dumps(
                {
                    "ok": False,
                    "returncode": completed.returncode,
                    "stdout_tail": _tail(completed.stdout),
                    "stderr_tail": _tail(completed.stderr),
                }
            )
        )
        return completed.returncode or 1

    result_path = _latest_json(run_dir)
    if not result_path:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "All-In-One finished without a JSON result",
                    "stdout_tail": _tail(completed.stdout),
                    "stderr_tail": _tail(completed.stderr),
                }
            )
        )
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "result_path": str(result_path),
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
            }
        )
    )
    return 0


def _latest_json(directory: Path) -> str | None:
    matches = sorted(directory.rglob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return str(matches[0]) if matches else None


def _find_stems_dir(output_dir: Path, audio_path: Path, env: dict[str, str]) -> Path | None:
    candidates = []
    configured = env.get("PROMPT2MIDI_ALLIN1_DOCKER_STEMS_DIR")
    if configured:
        candidates.append(Path(configured))
    candidates.extend(
        [
            output_dir / "stems",
            output_dir / "demucs" / "htdemucs" / audio_path.stem,
        ]
    )
    for candidate in candidates:
        if _has_required_stems(candidate):
            return candidate
    return None


def _has_required_stems(directory: Path) -> bool:
    return all((directory / f"{name}.wav").exists() for name in ("bass", "drums", "other", "vocals"))


def _tail(text: str | None, limit: int = 1200) -> str:
    value = (text or "").strip()
    return value[-limit:]


if __name__ == "__main__":
    raise SystemExit(main())
