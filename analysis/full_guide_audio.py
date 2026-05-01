#!/usr/bin/env python3
"""Section-by-section full arrangement guide audio generation."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from ace_step_generation import generate_with_ace_step


def generate_full_arrangement_guide_audio(
    reference_audio: str,
    output_dir: str,
    analysis: dict,
    full_arrangement: dict,
    user_prompt: str = "",
) -> dict:
    """Generate and stitch section guide audio when explicitly enabled."""
    if os.environ.get("PROMPT2MIDI_ENABLE_FULL_ACE_GUIDE") != "1":
        return _disabled("Set PROMPT2MIDI_ENABLE_FULL_ACE_GUIDE=1 to render full-song ACE guide audio.")
    if os.environ.get("PROMPT2MIDI_ENABLE_ACE_STEP") != "1":
        return _disabled("Set PROMPT2MIDI_ENABLE_ACE_STEP=1 and start the local ACE-Step API.")

    sections = full_arrangement.get("sections") or []
    if not sections:
        return _disabled("No arrangement sections are available for full guide rendering.")
    max_sections = int(os.environ.get("PROMPT2MIDI_FULL_GUIDE_MAX_SECTIONS") or "12")
    if len(sections) > max_sections:
        return _disabled(f"Arrangement has {len(sections)} sections; max enabled sections is {max_sections}.")

    output = Path(output_dir)
    work_dir = output / "full-guide-sections"
    work_dir.mkdir(parents=True, exist_ok=True)

    rendered = []
    for index, section in enumerate(sections, start=1):
        duration = max(4.0, float(section.get("end_seconds") or 0.0) - float(section.get("start_seconds") or 0.0))
        reference_section = work_dir / f"reference-section-{index:02d}.wav"
        _extract_wav(
            source=reference_audio,
            output=str(reference_section),
            start_seconds=float(section.get("start_seconds") or 0.0),
            duration_seconds=duration,
        )
        section_dir = work_dir / f"generated-section-{index:02d}"
        prompt = _section_prompt(section, full_arrangement, user_prompt)
        section_analysis = dict(analysis)
        section_analysis["arrangement_section"] = section
        result = generate_with_ace_step(
            reference_audio=str(reference_section),
            output_dir=str(section_dir),
            prompt=prompt,
            analysis=section_analysis,
            duration_seconds=duration,
            candidates=int(os.environ.get("PROMPT2MIDI_FULL_GUIDE_CANDIDATES") or "1"),
        )
        audio_path = _guide_audio_path(result)
        if not audio_path:
            return {
                "status": "failed",
                "provider": "ace_step",
                "reason": f"ACE-Step did not return section audio for section {index}.",
                "sections": rendered,
            }
        rendered.append(
            {
                "index": index,
                "role": section.get("role"),
                "start_seconds": section.get("start_seconds"),
                "duration_seconds": round(duration, 3),
                "reference_section": str(reference_section.resolve()),
                "audio": os.path.abspath(audio_path),
                "ace": result,
            }
        )

    guide_path = output / "full-arrangement-guide.wav"
    _concat_wavs([item["audio"] for item in rendered], str(guide_path))
    return {
        "status": "succeeded",
        "provider": "ace_step",
        "path": str(guide_path.resolve()),
        "section_count": len(rendered),
        "sections": rendered,
    }


def _guide_audio_path(result: dict) -> str | None:
    for key in ("sample", "selected_candidate", "suggested_candidate"):
        value = result.get(key)
        if value:
            return str(value)
    candidates = result.get("candidates") or []
    if candidates and candidates[0].get("path"):
        return str(candidates[0]["path"])
    return None


def _section_prompt(section: dict, full_arrangement: dict, user_prompt: str) -> str:
    roles = ", ".join(section.get("active_roles") or [])
    parts = [
        f"Render this full-song guide section: {section.get('role', 'section')}.",
        f"Bars {section.get('start_bar')}-{section.get('end_bar')}, {section.get('energy_level', 'medium')} energy.",
        f"Active roles: {roles}.",
        str(section.get("description") or ""),
        f"Similarity policy: {full_arrangement.get('similarity_level')} - {full_arrangement.get('similarity_policy')}.",
        "Keep the section length, timing pocket, role balance, and transition feel; generate original musical content.",
    ]
    if user_prompt.strip():
        parts.append(f"User direction: {user_prompt.strip()}")
    return " ".join(part for part in parts if part).strip()


def _extract_wav(source: str, output: str, start_seconds: float, duration_seconds: float) -> None:
    ffmpeg = os.environ.get("PROMPT2MIDI_FFMPEG") or shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for full guide section extraction.")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{start_seconds:.3f}",
            "-t",
            f"{duration_seconds:.3f}",
            "-i",
            source,
            "-ac",
            "2",
            "-ar",
            "48000",
            output,
        ],
        check=True,
    )


def _concat_wavs(inputs: list[str], output: str) -> None:
    ffmpeg = os.environ.get("PROMPT2MIDI_FFMPEG") or shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for full guide audio stitching.")
    list_path = Path(output).with_suffix(".concat.txt")
    list_path.write_text(
        "".join(f"file '{Path(path).resolve().as_posix()}'\n" for path in inputs),
        encoding="utf-8",
    )
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-ac",
            "2",
            "-ar",
            "48000",
            output,
        ],
        check=True,
    )


def _disabled(reason: str) -> dict:
    return {
        "status": "not_generated",
        "provider": "ace_step",
        "reason": reason,
    }
