#!/usr/bin/env python3
"""Section-by-section full arrangement guide audio generation."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from analysis.generation.providers.ace_step_generation import generate_with_ace_step
from analysis.reference.ace_preflight import build_ace_preflight
from analysis.reference.reference_transform import build_reference_transform


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
    lock = full_arrangement.get("arrangement_lock") or {}
    if lock.get("review_required") and os.environ.get("PROMPT2MIDI_ALLOW_UNREVIEWED_FULL_ACE_GUIDE") != "1":
        return _disabled(
            "Arrangement Lock confidence is below the review threshold. Review arrangement-lock-report.json before full ACE rendering."
        )
    max_sections = int(os.environ.get("PROMPT2MIDI_FULL_GUIDE_MAX_SECTIONS") or "12")
    if len(sections) > max_sections:
        return _disabled(f"Arrangement has {len(sections)} sections; max enabled sections is {max_sections}.")

    output = Path(output_dir)
    work_dir = output / "full-guide-sections"
    work_dir.mkdir(parents=True, exist_ok=True)

    rendered = []
    degraded_sections = []
    guide_similarity = _guide_similarity_level(full_arrangement)
    candidate_count = int(os.environ.get("PROMPT2MIDI_FULL_GUIDE_CANDIDATES") or "3")
    retry_batches = max(1, int(os.environ.get("PROMPT2MIDI_FULL_GUIDE_RETRY_BATCHES") or "2"))
    for index, section in enumerate(sections, start=1):
        duration = max(4.0, float(section.get("end_seconds") or 0.0) - float(section.get("start_seconds") or 0.0))
        _progress(
            "full arrangement guide: rendering section "
            f"{index}/{len(sections)} {section.get('role', 'section')} duration={duration:.1f}s"
        )
        reference_section = work_dir / f"reference-section-{index:02d}.wav"
        _extract_wav(
            source=reference_audio,
            output=str(reference_section),
            start_seconds=float(section.get("start_seconds") or 0.0),
            duration_seconds=duration,
        )
        prompt = _section_prompt(section, full_arrangement, user_prompt)
        section_analysis = dict(analysis)
        _apply_full_guide_style_lock(section_analysis)
        section_analysis["arrangement_section"] = section
        section_analysis["reference_similarity_level"] = guide_similarity
        generation_context = {
            "mode": "section_inspired_stitch",
            "similarity_level": guide_similarity,
            "policy": (
                "Preserve section timing, role balance, BPM/key area, energy arc, and detected instrument roles; "
                "generate new musical content and avoid a near-identical audio copy."
            ),
        }
        section_analysis["full_arrangement_generation"] = generation_context
        section_analysis["reference_transform"] = build_reference_transform(prompt, section_analysis)
        section_analysis["reference_transform"]["full_arrangement_generation"] = generation_context
        section_analysis["ace_preflight"] = build_ace_preflight(section_analysis, section_analysis["reference_transform"], prompt)
        _force_section_source_conditioning(section_analysis["ace_preflight"], guide_similarity)
        section_analysis["reference_transform"]["ace_preflight"] = section_analysis["ace_preflight"]
        result, selected_section_candidate, attempt_results = _generate_section_with_retries(
            reference_section=reference_section,
            work_dir=work_dir,
            section_index=index,
            prompt=prompt,
            section_analysis=section_analysis,
            duration=duration,
            candidate_count=candidate_count,
            retry_batches=retry_batches,
        )
        audio_path = selected_section_candidate.get("path") if selected_section_candidate else None
        if not audio_path:
            return {
                "status": "failed",
                "provider": "ace_step",
                "reason": f"ACE-Step did not return section audio for section {index}.",
                "sections": rendered,
            }
        selected_quality = selected_section_candidate.get("quality") or result.get("quality") or {}
        gate = (selected_quality.get("level_gate") or {})
        section_degraded = gate.get("passed") is False
        if section_degraded and os.environ.get("PROMPT2MIDI_FULL_GUIDE_REQUIRE_PASSING_SECTIONS") == "1":
            return {
                "status": "failed",
                "provider": "ace_step",
                "reason": f"Section {index} failed the quality gate in strict mode and was not stitched.",
                "failed_section": {
                    "index": index,
                    "role": section.get("role"),
                    "audio": os.path.abspath(audio_path),
                    "quality": selected_quality,
                    "candidate": _candidate_summary(selected_section_candidate),
                    "candidate_count": sum(len(item.get("candidates") or []) for item in attempt_results),
                    "attempt_count": len(attempt_results),
                },
                "sections": rendered,
            }
        if section_degraded:
            degraded = {
                "index": index,
                "role": section.get("role"),
                "audio": os.path.abspath(audio_path),
                "quality": selected_quality,
                "candidate": _candidate_summary(selected_section_candidate),
                "candidate_count": sum(len(item.get("candidates") or []) for item in attempt_results),
                "attempt_count": len(attempt_results),
            }
            degraded_sections.append(degraded)
            _progress(f"full arrangement guide: section {index}/{len(sections)} using best degraded candidate")
        rendered.append(
            {
                "index": index,
                "role": section.get("role"),
                "start_seconds": section.get("start_seconds"),
                "duration_seconds": round(duration, 3),
                "reference_section": str(reference_section.resolve()),
                "audio": os.path.abspath(audio_path),
                "selected_candidate": _candidate_summary(selected_section_candidate),
                "quality_status": "degraded" if section_degraded else "passed",
                "attempt_count": len(attempt_results),
                "ace": result,
            }
        )
        _progress(f"full arrangement guide: selected section {index}/{len(sections)} candidate")

    guide_path = output / "full-arrangement-guide.wav"
    _progress("full arrangement guide: stitching sections into full-arrangement-guide.wav")
    _concat_wavs([item["audio"] for item in rendered], str(guide_path))
    return {
        "status": "succeeded",
        "provider": "ace_step",
        "path": str(guide_path.resolve()),
        "section_count": len(rendered),
        "mode": "section_inspired_stitch",
        "similarity_level": guide_similarity,
        "quality_status": "degraded" if degraded_sections else "passed",
        "degraded_sections": degraded_sections,
        "warnings": _guide_warnings(degraded_sections),
        "policy": "Full-length Arrangement Lock guide; section audio is inspired by the reference structure, not a one-shot copy.",
        "sections": rendered,
    }


def _generate_section_with_retries(
    reference_section: Path,
    work_dir: Path,
    section_index: int,
    prompt: str,
    section_analysis: dict,
    duration: float,
    candidate_count: int,
    retry_batches: int,
) -> tuple[dict, dict | None, list[dict]]:
    attempt_results = []
    selected_result = {}
    selected_candidate = None
    for attempt in range(1, retry_batches + 1):
        section_dir = work_dir / f"generated-section-{section_index:02d}"
        if attempt > 1:
            section_dir = work_dir / f"generated-section-{section_index:02d}-retry-{attempt:02d}"
            _progress(f"full arrangement guide: retrying section {section_index} batch {attempt}/{retry_batches}")
        result = generate_with_ace_step(
            reference_audio=str(reference_section),
            output_dir=str(section_dir),
            prompt=prompt,
            analysis=section_analysis,
            duration_seconds=duration,
            candidates=candidate_count,
        )
        attempt_results.append(result)
        candidate = _select_section_candidate(result)
        if candidate:
            candidate["attempt"] = attempt
        if candidate and (selected_candidate is None or _candidate_rank_key(candidate) > _candidate_rank_key(selected_candidate)):
            selected_result = result
            selected_candidate = candidate
        gate = ((candidate or {}).get("quality") or {}).get("level_gate") or {}
        if gate.get("passed") is not False:
            break
    return selected_result, selected_candidate, attempt_results


def _select_section_candidate(result: dict) -> dict | None:
    candidates = result.get("candidates") or []
    candidates = [dict(item, quality=(item.get("quality") or result.get("quality") or {})) for item in candidates if item.get("path")]
    if candidates:
        return max(candidates, key=_candidate_rank_key)
    for key in ("sample", "selected_candidate", "suggested_candidate"):
        value = result.get(key)
        if value:
            return {
                "path": str(value),
                "quality": result.get("quality") or {},
                "source": key,
            }
    return None


def _candidate_rank_key(item: dict) -> tuple[int, float]:
    quality = item.get("quality") or {}
    gate = quality.get("level_gate") or {}
    gate_passed = 0 if gate.get("passed") is False else 1
    return gate_passed, float(quality.get("selection_score", quality.get("score", 0.0)) or 0.0)


def _candidate_summary(candidate: dict | None) -> dict | None:
    if not candidate:
        return None
    quality = candidate.get("quality") or {}
    gate = quality.get("level_gate") or {}
    return {
        "path": os.path.abspath(str(candidate.get("path"))),
        "score": quality.get("score"),
        "selection_score": quality.get("selection_score"),
        "gate_passed": gate.get("passed"),
        "attempt": candidate.get("attempt"),
    }


def _guide_warnings(degraded_sections: list[dict]) -> list[str]:
    if not degraded_sections:
        return []
    sections = ", ".join(str(item.get("index")) for item in degraded_sections)
    return [
        f"Full guide was stitched with degraded section candidate(s): {sections}. Review these sections before using the guide as final audio.",
    ]


def _section_prompt(section: dict, full_arrangement: dict, user_prompt: str) -> str:
    roles = ", ".join(section.get("active_roles") or [])
    parts = [
        f"Render this full-song guide section: {section.get('role', 'section')}.",
        "Style hard lock: underground tribal/deep-tech house, dark rolling club groove, 129 BPM dancefloor pressure; no holiday, Christmas, jingle-bell, orchestral, choir, cinematic, nursery, or cheerful pop elements.",
        f"Bars {section.get('start_bar')}-{section.get('end_bar')}, {section.get('energy_level', 'medium')} energy.",
        f"Active roles: {roles}.",
        str(section.get("description") or ""),
        f"Arrangement policy: keep the locked section length, bar timing, role balance, energy level, and transition feel from {full_arrangement.get('similarity_level')}.",
        "Inspiration policy: do not recreate the source recording, samples, bass pitch sequence, vocal identity, or exact hook; write new musical content inside this role.",
    ]
    if user_prompt.strip():
        parts.append(f"User direction: {user_prompt.strip()}")
    return " ".join(part for part in parts if part).strip()


def _guide_similarity_level(full_arrangement: dict) -> str:
    configured = str(os.environ.get("PROMPT2MIDI_FULL_GUIDE_SIMILARITY_LEVEL") or "").strip().lower()
    if configured:
        return configured.replace("_", "-")
    return "medium-low"


def _apply_full_guide_style_lock(analysis: dict) -> None:
    drums = (analysis or {}).get("drums") or {}
    if drums.get("percussion_character") != "tribal_percussion":
        return
    analysis["genre"] = {
        "primary": "underground tribal / deep tech house",
        "tags": ["underground house", "tribal house", "deep tech", "club"],
        "confidence": max(0.72, float(((analysis or {}).get("genre") or {}).get("confidence") or 0.0)),
        "method": "full_guide_style_lock",
    }
    analysis["genre_deep"] = {
        "primary": "underground tribal / deep tech house",
        "tags": ["underground house", "tribal house", "deep tech", "club"],
        "confidence": 0.72,
        "method": "full_guide_style_lock",
    }
    analysis["vocals"] = {
        "available": False,
        "present": False,
        "role": "none",
        "confidence": 0.0,
        "method": "full_guide_instrumental_lock",
        "warnings": ["Full Arrangement guide audio is rendered instrumental to avoid vocal/style drift in ACE section generation."],
    }


def _force_section_source_conditioning(preflight: dict, similarity_level: str) -> None:
    controls = (preflight or {}).setdefault("hidden_controls", {})
    controls["route"] = "source_conditioned_cover_section_inspired"
    controls["selected_profile"] = str(similarity_level or "medium-low").replace("-", "_")
    controls["recommended_profile"] = controls["selected_profile"]
    controls["recommended_similarity"] = max(0.34, float(controls.get("recommended_similarity") or 0.0))
    controls["reference_strength"] = max(0.18, float(controls.get("reference_strength") or 0.0))
    controls["cover_noise_strength"] = max(0.08, float(controls.get("cover_noise_strength") or 0.0))
    controls["vocal_mode"] = "instrumental_or_hook_proxy"
    preflight["recommended_generator"] = "ace_step"
    preflight["recommended_mode"] = "source_conditioned_cover_section_inspired"
    preflight["message"] = (
        "Full Arrangement section mode uses light source conditioning to preserve tempo, groove, energy, and section role "
        "while avoiding a near-copy."
    )


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


def _progress(message: str) -> None:
    print(f"progress: {message}", file=sys.stderr, flush=True)
