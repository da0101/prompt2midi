#!/usr/bin/env python3
"""Extend a generated proxy track with ACE-Step repaint continuation chunks."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from analysis.generation.providers import ace_step_generation as ace


def extend_track(
    source_audio: str,
    output_dir: str,
    prompt: str,
    target_duration: float,
    analysis: dict | None = None,
    chunk_seconds: float = 60.0,
    overlap_seconds: float = 8.0,
) -> dict:
    source = Path(source_audio)
    if not source.is_file():
        raise FileNotFoundError(f"Source audio not found: {source_audio}")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    current = out / "extended-full-track-seed.wav"
    shutil.copyfile(source, current)
    current_duration = _duration(current)
    target_duration = max(current_duration, float(target_duration))
    chunk_seconds = max(3.0, min(90.0, float(chunk_seconds)))
    overlap_seconds = max(0.5, min(20.0, float(overlap_seconds)))

    chunks: list[dict] = []
    if target_duration <= current_duration + 1.0:
        final_path = out / "extended-full-track.wav"
        shutil.copyfile(current, final_path)
        return _result(final_path, current_duration, target_duration, chunks, "already_long_enough")

    base_url = (os.environ.get("PROMPT2MIDI_ACE_STEP_URL") or ace.DEFAULT_BASE_URL).rstrip("/")
    model = os.environ.get("PROMPT2MIDI_ACE_STEP_MODEL") or ace.DEFAULT_MODEL
    ace._health_check(base_url)

    index = 1
    while current_duration < target_duration - 1.0:
        extend_by = min(chunk_seconds, target_duration - current_duration)
        canvas = out / f"extend-canvas-{index}.wav"
        _append_silence(current, canvas, extend_by)
        canvas_duration = _duration(canvas)
        repaint_start = max(0.0, current_duration - overlap_seconds)
        chunk_dir = out / f"extend-chunk-{index}"
        chunk_dir.mkdir(parents=True, exist_ok=True)

        payload = ace._build_payload(
            reference_audio=str(canvas),
            prompt=_continuation_prompt(prompt, current_duration, target_duration),
            analysis=analysis or {},
            duration_seconds=canvas_duration,
            candidate_count=1,
            model=model,
        )
        payload["task_type"] = "repaint"
        payload["reference_audio_path"] = None
        payload["src_audio_path"] = str(canvas)
        payload["repainting_start"] = repaint_start
        payload["repainting_end"] = -1
        payload["audio_duration"] = canvas_duration
        payload["duration"] = canvas_duration
        payload["batch_size"] = 1
        payload["thinking"] = False
        payload["instruction"] = "Continue the track naturally from the existing ending and keep the same groove, kit, bass tone, mix identity, and club energy."

        ace._progress(
            f"full-track extension: repaint chunk {index} "
            f"from {repaint_start:.1f}s to {canvas_duration:.1f}s"
        )
        task_id = ace._submit_task(base_url, payload)
        results = ace._poll_task(base_url, task_id)
        candidates = ace._download_candidates(base_url, results, str(chunk_dir), canvas_duration, analysis or {})
        if not candidates:
            raise RuntimeError(f"ACE-Step repaint extension chunk {index} returned no audio.")
        chosen = candidates[0]["path"]
        next_current = out / f"extended-full-track-pass-{index}.wav"
        shutil.copyfile(chosen, next_current)
        current = next_current
        current_duration = _duration(current)
        chunks.append(
            {
                "index": index,
                "task_id": task_id,
                "path": str(Path(chosen).resolve()),
                "duration_seconds": current_duration,
                "repainting_start": repaint_start,
                "repainting_end": -1,
            }
        )
        index += 1

    final_path = out / "extended-full-track.wav"
    shutil.copyfile(current, final_path)
    return _result(final_path, _duration(final_path), target_duration, chunks, "extended")


def _continuation_prompt(prompt: str, current_duration: float, target_duration: float) -> str:
    base = " ".join(str(prompt or "").split())
    continuation = (
        f"Continue this same track from {current_duration:.1f}s toward a {target_duration:.1f}s full club arrangement. "
        "Do not change genre, drum kit, bass tone, key area, tempo, or mix identity. "
        "Keep the hypnotic groove continuous with subtle fills, filter movement, breakdown/build/re-entry logic, and DJ-friendly flow."
    )
    return f"{base}. {continuation}" if base else continuation


def _append_silence(source: Path, output: Path, seconds: float) -> None:
    ffmpeg = os.environ.get("PROMPT2MIDI_FFMPEG") or "ffmpeg"
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-f",
        "lavfi",
        "-t",
        f"{seconds:.3f}",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-filter_complex",
        "[0:a][1:a]concat=n=2:v=0:a=1[a]",
        "-map",
        "[a]",
        "-ac",
        "2",
        "-ar",
        "44100",
        str(output),
    ]
    subprocess.run(command, check=True)


def _duration(path: Path) -> float:
    ffprobe = os.environ.get("PROMPT2MIDI_FFPROBE") or "ffprobe"
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nokey=1:noprint_wrappers=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(completed.stdout.strip())


def _result(path: Path, duration: float, target_duration: float, chunks: list[dict], status: str) -> dict:
    payload = {
        "ok": True,
        "status": status,
        "path": str(path.resolve()),
        "duration_seconds": duration,
        "target_duration_seconds": target_duration,
        "chunks": chunks,
        "method": "ace_repaint_continuation_v1",
    }
    manifest = path.with_suffix(".json")
    manifest.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    payload["manifest"] = str(manifest.resolve())
    return payload


def _load_analysis(path: str | None) -> dict:
    if not path:
        return {}
    candidate = Path(path)
    if not candidate.is_file():
        return {}
    return json.loads(candidate.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Extend an ACE proxy track using repaint continuation chunks.")
    parser.add_argument("--source-audio", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--prompt", default="")
    parser.add_argument("--target-duration", required=True, type=float)
    parser.add_argument("--analysis-json")
    parser.add_argument("--chunk-seconds", type=float, default=float(os.environ.get("PROMPT2MIDI_FULL_TRACK_CHUNK_SECONDS") or 60))
    parser.add_argument("--overlap-seconds", type=float, default=float(os.environ.get("PROMPT2MIDI_FULL_TRACK_OVERLAP_SECONDS") or 8))
    args = parser.parse_args()
    result = extend_track(
        source_audio=args.source_audio,
        output_dir=args.output_dir,
        prompt=args.prompt,
        target_duration=args.target_duration,
        analysis=_load_analysis(args.analysis_json),
        chunk_seconds=args.chunk_seconds,
        overlap_seconds=args.overlap_seconds,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
