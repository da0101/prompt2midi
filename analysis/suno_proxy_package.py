#!/usr/bin/env python3
"""Prepare a generated proxy-demo package for Suno without uploading the source reference."""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

from suno_cover_package import _analyze_for_suno, _fmt_number, _genre_text, _groove_text


def prepare_suno_proxy_package(
    reference_audio: str,
    proxy_audio: str,
    output_dir: str,
    user_prompt: str = "",
    upload_duration: float | str = 30.0,
    start_seconds: float | None = None,
) -> dict:
    """Analyze a local reference but package only a generated proxy demo for Suno."""
    reference = Path(reference_audio)
    proxy = Path(proxy_audio)
    if not reference.exists():
        raise FileNotFoundError(f"Reference audio not found: {reference_audio}")
    if not proxy.exists():
        raise FileNotFoundError(f"Proxy audio not found: {proxy_audio}")
    if _same_file(reference, proxy):
        raise ValueError("Proxy audio must be a newly generated track, not the original reference.")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    _progress("decoding local reference for analysis only")
    analysis_wav = _ensure_wav(reference, out / "reference-analysis-input.wav")
    _progress("analyzing reference style, groove, harmony, and vocal role")
    analysis = _analyze_for_suno(str(analysis_wav), user_prompt)
    analysis["reference_audio"] = str(reference.resolve())
    analysis.pop("source_path", None)
    _remove_intermediate(analysis_wav, reference, out)

    _progress("preparing generated proxy upload")
    proxy_wav = _ensure_wav(proxy, out / "proxy-analysis-input.wav")
    proxy_duration = _duration_seconds(proxy_wav)
    section = _choose_proxy_section(proxy_duration, upload_duration, start_seconds)
    upload_wav = out / "suno-upload-proxy.wav"
    upload_mp3 = out / "suno-upload-proxy.mp3"
    _cut_audio(proxy, upload_wav, section["start_seconds"], section["duration_seconds"], codec="wav")
    try:
        _cut_audio(proxy, upload_mp3, section["start_seconds"], section["duration_seconds"], codec="mp3")
    except Exception as exc:
        section.setdefault("warnings", []).append(f"MP3 proxy upload was not created: {exc}")
    _remove_intermediate(proxy_wav, proxy, out)

    safe_prompt = _copyright_safe_prompt(user_prompt)
    prompt = render_suno_proxy_prompt(analysis, section, safe_prompt)
    report = render_suno_proxy_report(analysis, section, safe_prompt)
    instructions = render_proxy_usage_instructions(section)

    payload = {
        "ok": True,
        "engine": "suno_proxy_package_v1",
        "reference_audio_local_only": str(reference.resolve()),
        "proxy_audio": str(proxy.resolve()),
        "output_dir": str(out.resolve()),
        "analysis": analysis,
        "upload_section": section,
        "files": {
            "upload_wav": str(upload_wav.resolve()),
            "upload_mp3": str(upload_mp3.resolve()) if upload_mp3.exists() else None,
            "prompt": str((out / "suno-proxy-prompt.md").resolve()),
            "report": str((out / "suno-proxy-analysis.md").resolve()),
            "instructions": str((out / "suno-proxy-usage-steps.md").resolve()),
            "manifest": str((out / "suno-proxy-package.json").resolve()),
        },
        "suno_prompt": prompt,
        "warnings": [
            "The original reference is analyzed locally only and is not packaged for Suno upload.",
            "Upload only suno-upload-proxy.wav/mp3, which must be a generated proxy demo.",
            "The prompt avoids direct artist/title naming; review user direction for rights-sensitive wording.",
        ],
    }

    (out / "suno-proxy-prompt.md").write_text(prompt, encoding="utf-8")
    (out / "suno-proxy-analysis.md").write_text(report, encoding="utf-8")
    (out / "suno-proxy-usage-steps.md").write_text(instructions, encoding="utf-8")
    (out / "suno-proxy-package.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def render_suno_proxy_prompt(analysis: dict, section: dict, safe_user_prompt: str = "") -> str:
    bpm = _fmt_number(analysis.get("bpm"), "same tempo area as proxy")
    key = analysis.get("key") or "same key area as the proxy demo"
    genre = _genre_text(analysis.get("genre") or {})
    groove = _groove_text(analysis)
    vocal_role = (analysis.get("vocal_role") or {}).get("summary") or "instrumental or minimal hook role"
    reference_groove = analysis.get("reference_groove") or {}
    kick_grid = reference_groove.get("kick_pattern_16th") or "steady club kick pulse"
    bass_grid = reference_groove.get("bass_accent_pattern_16th") or "syncopated rolling bass accents"
    hat_grid = reference_groove.get("hat_pattern_16th") or "driving hats and percussion"
    low_end = reference_groove.get("low_end_weight") or "heavy but controlled"
    cleaned_user_prompt = safe_user_prompt.strip().rstrip(".")
    user_direction = f" User direction: {cleaned_user_prompt}." if cleaned_user_prompt else ""
    prompt = (
        "Use the uploaded generated proxy demo as the audio seed for a new original finished SUNO track, not as a cover and not as a request to copy the source reference. "
        "Do not imitate any famous artist, singer, recording, lyric, hook, melody, or exact sample. "
        "Avoid unrelated layers, sudden genre changes, novelty instruments, cheesy EDM supersaws, random cinematic layers, off-scale notes, glitch noise, thin bass, loose timing, over-bright harshness, and messy transitions. "
        f"{user_direction} "
        f"Preserve the proxy's arrangement, full-song shape, DJ-friendly continuity, extended intro-to-groove-to-outro flow, {bpm} BPM pulse, {key} key area, and {genre} identity. "
        f"The core feel is {groove}; keep that pocket while making the musical material more polished, finished, and release-ready. "
        "Build around a consistent underground club mix identity: one coherent drum kit, one coherent bass tone, one coherent percussion palette, stable ambience, and clean transitions across the whole track. "
        f"Keep the kick behavior close to this grid feel: {kick_grid}. Keep the bass pressure and accent behavior close to this feel: {bass_grid}. Keep the hat/percussion motion close to this feel: {hat_grid}. "
        f"The low end should remain {low_end}, tight, warm, rounded, and club-weighted without masking the kick. "
        "Preserve the proxy's rhythmic drive, bass pressure, energy arc, breakdown/build/re-entry logic, stereo space, and movement, but replace any weak, noisy, random, or unfinished details with cleaner production. "
        "Add tasteful variation over time: subtle drum fills, percussion call-and-response, filtered transitions, risers, drops, mutes, return hits, and evolving ambience, while keeping the groove hypnotic and continuous. "
        f"Vocal or hook role target: {vocal_role}. If vocals or vocal textures appear, use only the role and energy; create new lyrics, new voice, new melody, and new hook contour. "
        "Finish it as an original professional club track that sounds inspired by the uploaded proxy's structure and groove, with stronger mix polish and musical development."
    )
    return _limit_prompt(prompt, 2000)


def render_suno_proxy_report(analysis: dict, section: dict, safe_user_prompt: str = "") -> str:
    reference_groove = analysis.get("reference_groove") or {}
    lines = [
        "# Suno Proxy Prep Analysis",
        "",
        "## Important Boundary",
        "- Original reference: local analysis only, not for Suno upload.",
        "- Suno upload: generated proxy demo only.",
        "",
        "## Proxy Upload Section",
        f"- Start: {section['start_seconds']:.2f}s",
        f"- End: {section['end_seconds']:.2f}s",
        f"- Duration: {section['duration_seconds']:.2f}s",
        "",
        "## Reference-Derived Style Targets",
        f"- BPM: {_fmt_number(analysis.get('bpm'), 'unknown')} confidence={_fmt_number(analysis.get('bpm_confidence'), 'unknown')}",
        f"- Key: {analysis.get('key') or 'unknown'} confidence={_fmt_number(analysis.get('key_confidence'), 'unknown')}",
        f"- Genre: {_genre_text(analysis.get('genre') or {})}",
        f"- Groove: {_groove_text(analysis)}",
        f"- Vocal role: {(analysis.get('vocal_role') or {}).get('summary')}",
        "",
        "## Groove Fingerprint",
        f"- Kick grid: {reference_groove.get('kick_pattern_16th') or 'unknown'}",
        f"- Bass grid: {reference_groove.get('bass_accent_pattern_16th') or 'unknown'}",
        f"- Hat/percussion grid: {reference_groove.get('hat_pattern_16th') or 'unknown'}",
        f"- Low end: {reference_groove.get('low_end_weight') or 'unknown'}",
        "",
        "## Safe User Direction",
        safe_user_prompt.strip() or "(none)",
        "",
    ]
    return "\n".join(lines)


def render_proxy_usage_instructions(section: dict) -> str:
    return (
        "# Suno Proxy Usage Steps\n\n"
        "1. Upload `suno-upload-proxy.wav` or `suno-upload-proxy.mp3` to Suno.\n"
        "2. Do not upload the original reference track.\n"
        "3. Paste `suno-proxy-prompt.md` into the prompt/style field.\n"
        "4. Generate several candidates and keep the strongest original result.\n"
        "5. If Suno copies the proxy too tightly, ask for a stronger transformation while preserving groove/energy.\n\n"
        f"Prepared proxy upload window: {section['start_seconds']:.1f}s to {section['end_seconds']:.1f}s.\n"
    )


def _choose_proxy_section(duration: float, upload_duration: float | str, start_seconds: float | None) -> dict:
    full_upload = str(upload_duration).strip().lower() in {"full", "reference", "track", "source"}
    if full_upload:
        window = duration
    else:
        window = max(6.0, min(60.0, float(upload_duration), duration))
    start = 0.0 if start_seconds is None else max(0.0, min(float(start_seconds), max(0.0, duration - window)))
    return {
        "start_seconds": round(start, 3),
        "end_seconds": round(start + window, 3),
        "duration_seconds": round(window, 3),
        "method": "proxy_full_track" if full_upload else ("proxy_user_selected" if start_seconds is not None else "proxy_start"),
    }


def _copyright_safe_prompt(prompt: str) -> str:
    text = prompt or ""
    replacements = [
        (r"\bMichael\s+Jackson\b", "a high-energy 1980s electro-funk dance-pop reference"),
        (r"\bMJ\b", "the 1980s electro-funk dance-pop reference"),
        (r"\bSmooth\s+Criminal\b", "a dramatic syncopated electro-funk song"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return " ".join(text.split())


def _user_direction_block(prompt: str) -> str:
    if not prompt.strip():
        return ""
    return f"\nUser direction:\n{prompt.strip()}\n"


def _limit_prompt(prompt: str, limit: int) -> str:
    text = " ".join((prompt or "").split())
    if len(text) <= limit:
        return text
    clipped = text[:limit]
    sentence = clipped.rfind(". ")
    if sentence >= int(limit * 0.65):
        return clipped[: sentence + 1].strip()
    return clipped.rsplit(" ", 1)[0].strip()


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
        raise RuntimeError("ffmpeg is required for Suno proxy prep.")
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


def _same_file(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve() or os.path.samefile(left, right)
    except FileNotFoundError:
        return False


def _remove_intermediate(path: Path, source: Path, output_dir: Path) -> None:
    if path.resolve() == source.resolve():
        return
    try:
        if path.parent.resolve() == output_dir.resolve() and path.name.endswith("analysis-input.wav"):
            path.unlink(missing_ok=True)
    except Exception:
        pass


def _progress(message: str) -> None:
    print(f"progress: suno-proxy: {message}", file=sys.stderr, flush=True)


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a Suno package from a generated proxy demo, not the source reference.")
    parser.add_argument("--reference", required=True)
    parser.add_argument("--proxy-audio", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--prompt", default="")
    parser.add_argument("--duration", default="30")
    parser.add_argument("--start", type=float)
    args = parser.parse_args()
    try:
        payload = prepare_suno_proxy_package(
            reference_audio=args.reference,
            proxy_audio=args.proxy_audio,
            output_dir=args.output_dir,
            user_prompt=args.prompt,
            upload_duration=args.duration,
            start_seconds=args.start,
        )
        cli_payload = _cli_summary(payload)
    except Exception as exc:
        payload = {"ok": False, "error": {"code": "suno_proxy_prep_failed", "message": str(exc)}}
        cli_payload = payload
    sys.stdout.write(json.dumps(cli_payload, indent=2, sort_keys=True))
    sys.stdout.write("\n")
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
