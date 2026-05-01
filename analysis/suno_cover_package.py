#!/usr/bin/env python3
"""Prepare a reference-track package for Suno Cover / Audio Input workflows."""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import wave
from pathlib import Path

from chord_detection import detect_chords
from enhanced_analysis import better_bpm, better_key, estimate_groove, infer_genre
from feature_extraction import analyze_wav
from genre_detection import detect_genre
from reference_groove import analyze_reference_groove
from structure_analysis import analyze_structure


def prepare_suno_cover_package(
    reference_audio: str,
    output_dir: str,
    user_prompt: str = "",
    upload_duration: float = 30.0,
    start_seconds: float | None = None,
) -> dict:
    """Analyze a reference and write Suno-ready prompt/upload artifacts."""
    reference = Path(reference_audio)
    if not reference.exists():
        raise FileNotFoundError(f"Reference audio not found: {reference_audio}")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    _progress("decoding reference for analysis")
    analysis_wav = _ensure_wav(reference, out / "analysis-input.wav")
    _progress("analyzing reference identity, groove, harmony, and structure")
    analysis = _analyze_for_suno(str(analysis_wav), user_prompt)
    analysis["reference_audio"] = str(reference.resolve())
    analysis.pop("source_path", None)
    duration = float(analysis.get("duration_seconds") or _duration_seconds(analysis_wav) or upload_duration)
    section = _choose_upload_section(analysis, duration, upload_duration, start_seconds)

    upload_wav = out / "suno-upload-reference.wav"
    upload_mp3 = out / "suno-upload-reference.mp3"
    _progress(f"cutting Suno upload section at {section['start_seconds']:.2f}s")
    _cut_audio(reference, upload_wav, section["start_seconds"], section["duration_seconds"], codec="wav")
    try:
        _cut_audio(reference, upload_mp3, section["start_seconds"], section["duration_seconds"], codec="mp3")
    except Exception as exc:
        section.setdefault("warnings", []).append(f"MP3 upload copy was not created: {exc}")

    prompt = render_suno_cover_prompt(analysis, section, user_prompt)
    report = render_suno_cover_report(analysis, section, user_prompt)
    instructions = render_usage_instructions(section)

    payload = {
        "ok": True,
        "engine": "suno_cover_package_v1",
        "reference_audio": str(reference.resolve()),
        "output_dir": str(out.resolve()),
        "analysis": analysis,
        "upload_section": section,
        "files": {
            "upload_wav": str(upload_wav.resolve()),
            "upload_mp3": str(upload_mp3.resolve()) if upload_mp3.exists() else None,
            "prompt": str((out / "suno-cover-prompt.md").resolve()),
            "report": str((out / "suno-cover-analysis.md").resolve()),
            "instructions": str((out / "suno-usage-steps.md").resolve()),
            "manifest": str((out / "suno-cover-package.json").resolve()),
        },
        "suno_prompt": prompt,
        "warnings": [
            "This package does not generate audio locally. It prepares a high-signal Suno Cover/Audio Input job.",
            "Use only audio you have rights to upload or transform.",
            "For famous vocal-rich references, direct Suno Cover/Audio Input is expected to outperform local open models.",
        ],
    }

    (out / "suno-cover-prompt.md").write_text(prompt, encoding="utf-8")
    (out / "suno-cover-analysis.md").write_text(report, encoding="utf-8")
    (out / "suno-usage-steps.md").write_text(instructions, encoding="utf-8")
    (out / "suno-cover-package.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _remove_intermediate(analysis_wav, reference, out)
    return payload


def _analyze_for_suno(audio_path: str, user_prompt: str) -> dict:
    analysis = analyze_wav(audio_path)
    bpm_result = better_bpm(audio_path, analysis.get("bpm"), analysis.get("bpm_confidence"))
    if bpm_result.get("bpm") is not None:
        analysis["bpm"] = bpm_result["bpm"]
        analysis["bpm_confidence"] = bpm_result.get("confidence") or analysis.get("bpm_confidence")
        analysis["bpm_method"] = bpm_result.get("method")
    key_result = better_key(audio_path, analysis.get("key"), analysis.get("key_confidence"))
    if key_result.get("key") is not None:
        analysis["key"] = key_result["key"]
        analysis["key_confidence"] = key_result.get("confidence") or analysis.get("key_confidence")
        analysis["key_method"] = key_result.get("method")

    analysis["genre"] = infer_genre(analysis)
    deep_genre = detect_genre(audio_path)
    analysis["genre_deep"] = deep_genre
    if deep_genre.get("confidence", 0.0) > 0.12:
        analysis["genre"] = {
            "primary": deep_genre.get("primary"),
            "tags": deep_genre.get("tags") or [],
            "confidence": deep_genre.get("confidence"),
        }
    analysis["groove"] = estimate_groove(analysis)
    analysis["chords"] = detect_chords(audio_path, analysis.get("bpm") or 120.0)
    analysis["structure"] = analyze_structure(audio_path, analysis.get("bpm") or 120.0)
    analysis["reference_groove"] = analyze_reference_groove(audio_path, analysis.get("bpm"))
    analysis["vocal_role"] = _infer_vocal_role(analysis, user_prompt)
    if user_prompt:
        analysis["user_direction"] = user_prompt
    return analysis


def render_suno_cover_prompt(analysis: dict, section: dict, user_prompt: str = "") -> str:
    bpm = _fmt_number(analysis.get("bpm"), "unknown")
    key = analysis.get("key") or "same key area as reference"
    genre = _genre_text(analysis.get("genre") or {})
    groove = _groove_text(analysis)
    vocal = analysis.get("vocal_role") or {}
    chords = analysis.get("chords") or {}
    chord_line = ", ".join((chords.get("progression") or [])[:8]) or "follow the reference harmonic tension"
    upload = f"{section['start_seconds']:.1f}s-{section['end_seconds']:.1f}s"
    extra = f"\n\nUser direction:\n{user_prompt.strip()}\n" if user_prompt.strip() else ""
    return (
        "# Suno Cover / Audio Input Prompt\n\n"
        f"Use the uploaded reference section ({upload}) as the audio seed. Create a new original song inspired by its "
        "groove, rhythm, energy, section feel, and production attitude, not a direct copy.\n\n"
        f"Target style: {genre}.\n"
        f"Tempo: {bpm} BPM. Keep the same tempo/pulse unless Suno must adapt slightly.\n"
        f"Key area: {key}. Keep harmonic material tonal and resolved.\n"
        f"Groove: {groove}.\n"
        f"Harmony cue: {chord_line}.\n"
        f"Vocal role: {vocal.get('summary', 'preserve the role only if useful, with a new voice and new melody')}.\n\n"
        "Transformation rules:\n"
        "- Keep the reference pocket, swing/straight feel, bass movement attitude, drum drive, and energy contour.\n"
        "- Change the melody, lead hook, lyrics, vocal identity, and exact instrumental riffs.\n"
        "- Use a new vocal performance and original words if vocals are included.\n"
        "- Avoid cheesy additions, random glitches, weak drums, thin bass, and atonal notes.\n"
        "- Output should sound like a finished, professional demo suitable for further editing in Suno Studio.\n"
        f"{extra}"
    )


def render_suno_cover_report(analysis: dict, section: dict, user_prompt: str = "") -> str:
    reference_groove = analysis.get("reference_groove") or {}
    structure = (analysis.get("structure") or {}).get("sections") or []
    lines = [
        "# Suno Cover Prep Analysis",
        "",
        "## Upload Section",
        f"- Start: {section['start_seconds']:.2f}s",
        f"- End: {section['end_seconds']:.2f}s",
        f"- Duration: {section['duration_seconds']:.2f}s",
        f"- Selection method: {section['method']}",
        "",
        "## Detected Metadata",
        f"- BPM: {_fmt_number(analysis.get('bpm'), 'unknown')} confidence={_fmt_number(analysis.get('bpm_confidence'), 'unknown')}",
        f"- Key: {analysis.get('key') or 'unknown'} confidence={_fmt_number(analysis.get('key_confidence'), 'unknown')}",
        f"- Genre: {_genre_text(analysis.get('genre') or {})}",
        f"- Groove: {_groove_text(analysis)}",
        f"- Vocal role: {(analysis.get('vocal_role') or {}).get('summary')}",
        "",
        "## Reference Groove Fingerprint",
        f"- Kick grid: {reference_groove.get('kick_pattern_16th') or 'unknown'}",
        f"- Bass grid: {reference_groove.get('bass_accent_pattern_16th') or 'unknown'}",
        f"- Hat/percussion grid: {reference_groove.get('hat_pattern_16th') or 'unknown'}",
        f"- Low end: {reference_groove.get('low_end_weight') or 'unknown'}",
        f"- Club energy: {reference_groove.get('club_energy') or 'unknown'}",
        "",
        "## Structure Estimate",
    ]
    if structure:
        for item in structure[:12]:
            lines.append(f"- {_fmt_time(item.get('start', 0))}-{_fmt_time(item.get('end', 0))}: {item.get('label', 'section')} energy={item.get('energy', 'unknown')}")
    else:
        lines.append("- No structure sections detected; use the upload clip as the practical section cue.")
    lines.extend(["", "## User Direction", user_prompt.strip() or "(none)", ""])
    return "\n".join(lines)


def render_usage_instructions(section: dict) -> str:
    return (
        "# Suno Usage Steps\n\n"
        "1. Open Suno Create.\n"
        "2. Upload `suno-upload-reference.wav` or `suno-upload-reference.mp3`.\n"
        "3. Use Cover/Remix/Audio Input, depending on what your account exposes.\n"
        "4. Paste `suno-cover-prompt.md` into the prompt/style field.\n"
        "5. Generate several candidates and keep the one with the strongest groove and least copying.\n"
        "6. If Suno copies too closely, lower audio influence if available, or ask for a stronger genre transformation.\n\n"
        f"Prepared upload window: {section['start_seconds']:.1f}s to {section['end_seconds']:.1f}s.\n"
    )


def _choose_upload_section(analysis: dict, duration: float, upload_duration: float, start_seconds: float | None) -> dict:
    window = max(6.0, min(60.0, upload_duration, duration))
    if start_seconds is not None:
        start = max(0.0, min(float(start_seconds), max(0.0, duration - window)))
        return {
            "start_seconds": round(start, 3),
            "end_seconds": round(start + window, 3),
            "duration_seconds": round(window, 3),
            "method": "user_selected",
        }
    energy = analysis.get("energy_curve") or []
    if not energy:
        return {"start_seconds": 0.0, "end_seconds": round(window, 3), "duration_seconds": round(window, 3), "method": "start_fallback"}
    best = 0.0
    best_score = -1.0
    step = max(1.0, min(5.0, window / 6.0))
    search_end = max(0.0, duration - window)
    candidate = 0.0
    while candidate <= search_end + 1e-6:
        score = _mean_energy(energy, candidate, candidate + window)
        position_bonus = 0.04 if duration * 0.18 <= candidate <= duration * 0.75 else 0.0
        if score + position_bonus > best_score:
            best_score = score + position_bonus
            best = candidate
        candidate += step
    return {
        "start_seconds": round(best, 3),
        "end_seconds": round(best + window, 3),
        "duration_seconds": round(window, 3),
        "method": "highest_energy_window",
        "mean_energy": round(max(0.0, best_score), 4),
    }


def _mean_energy(curve: list[dict], start: float, end: float) -> float:
    values = [float(point.get("energy") or 0.0) for point in curve if start <= float(point.get("time") or 0.0) <= end]
    if not values:
        return 0.0
    return sum(values) / len(values)


def _infer_vocal_role(analysis: dict, user_prompt: str) -> dict:
    text = f"{user_prompt} {analysis.get('genre', {}).get('primary', '')}".lower()
    if any(term in text for term in ("instrumental", "no vocal", "no vocals")):
        return {"present": False, "summary": "keep instrumental unless Suno adds short non-lyrical texture"}
    mid_energy = _band_proxy(analysis, "mid")
    likely = any(term in text for term in ("vocal", "voice", "lyrics", "michael jackson", "pop")) or mid_energy > 0.4
    if likely:
        return {
            "present": True,
            "summary": "reference has a strong vocal/lead-hook role; use new lyrics, new melody contour, and new vocal identity",
        }
    return {"present": False, "summary": "no confident vocal role; prioritize groove and instrumental production"}


def _band_proxy(analysis: dict, key: str) -> float:
    spectral = analysis.get("spectral") or {}
    try:
        return float(spectral.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _ensure_wav(reference: Path, decoded_path: Path) -> Path:
    if reference.suffix.lower() in {".wav", ".wave"} and _is_wav(reference):
        return reference
    _run_ffmpeg(["-y", "-hide_banner", "-loglevel", "error", "-i", str(reference), "-vn", "-ac", "2", "-ar", "44100", str(decoded_path)])
    return decoded_path


def _cut_audio(reference: Path, output: Path, start: float, duration: float, codec: str) -> None:
    args = ["-y", "-hide_banner", "-loglevel", "error", "-ss", str(start), "-i", str(reference), "-t", str(duration), "-vn", "-ac", "2", "-ar", "44100"]
    if codec == "mp3":
        args.extend(["-codec:a", "libmp3lame", "-b:a", "192k"])
    else:
        args.extend(["-acodec", "pcm_s16le"])
    args.append(str(output))
    _run_ffmpeg(args)


def _run_ffmpeg(args: list[str]) -> None:
    ffmpeg = os.environ.get("PROMPT2MIDI_FFMPEG") or shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for Suno cover prep.")
    subprocess.run([ffmpeg, *args], check=True)


def _is_wav(path: Path) -> bool:
    try:
        with wave.open(str(path), "rb") as handle:
            return handle.getnframes() > 0
    except wave.Error:
        return False


def _duration_seconds(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as handle:
            return handle.getnframes() / float(handle.getframerate())
    except Exception:
        return 0.0


def _remove_intermediate(path: Path, reference: Path, output_dir: Path) -> None:
    if path.resolve() == reference.resolve():
        return
    try:
        if path.parent.resolve() == output_dir.resolve() and path.name == "analysis-input.wav":
            path.unlink(missing_ok=True)
    except Exception:
        pass


def _genre_text(genre: dict) -> str:
    primary = genre.get("primary") or "reference-inspired pop/electronic"
    tags = genre.get("tags") or []
    return f"{primary} ({', '.join(str(tag) for tag in tags[:5])})" if tags else str(primary)


def _groove_text(analysis: dict) -> str:
    reference_groove = analysis.get("reference_groove") or {}
    groove = analysis.get("groove") or {}
    parts = [
        groove.get("description"),
        reference_groove.get("drum_feel"),
        reference_groove.get("bass_feel"),
        reference_groove.get("low_end_weight"),
    ]
    return "; ".join(str(part) for part in parts if part) or "preserve the reference rhythmic pocket"


def _fmt_number(value: object, fallback: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if not math.isfinite(number):
        return fallback
    return f"{number:.2f}".rstrip("0").rstrip(".")


def _fmt_time(value: object) -> str:
    seconds = float(value or 0.0)
    minutes = int(seconds // 60)
    return f"{minutes}:{seconds - minutes * 60:04.1f}"


def _progress(message: str) -> None:
    print(f"progress: suno-cover: {message}", file=sys.stderr, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a Suno Cover / Audio Input package from a reference track.")
    parser.add_argument("--reference", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--prompt", default="")
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--start", type=float)
    args = parser.parse_args()
    try:
        payload = prepare_suno_cover_package(
            reference_audio=args.reference,
            output_dir=args.output_dir,
            user_prompt=args.prompt,
            upload_duration=args.duration,
            start_seconds=args.start,
        )
        cli_payload = _cli_summary(payload)
    except Exception as exc:
        payload = {"ok": False, "error": {"code": "suno_cover_prep_failed", "message": str(exc)}}
        cli_payload = payload
    sys.stdout.write(json.dumps(cli_payload, indent=2, sort_keys=True))
    sys.stdout.write("\n")
    return 0 if payload.get("ok") else 2


def _cli_summary(payload: dict) -> dict:
    analysis = payload.get("analysis") or {}
    return {
        "ok": payload.get("ok"),
        "engine": payload.get("engine"),
        "output_dir": payload.get("output_dir"),
        "upload_section": payload.get("upload_section"),
        "detected": {
            "bpm": analysis.get("bpm"),
            "key": analysis.get("key"),
            "genre": analysis.get("genre"),
            "groove": analysis.get("groove"),
            "vocal_role": analysis.get("vocal_role"),
        },
        "files": payload.get("files"),
        "warnings": payload.get("warnings"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
