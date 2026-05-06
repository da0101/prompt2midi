#!/usr/bin/env python3
"""Provider orchestration for reference-inspired audio samples."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from analysis.core.audio_quality import score_audio_candidate
from analysis.generation.providers.ace_step_generation import generate_with_ace_step
from analysis.reference.reference_groove import analyze_reference_groove
from analysis.reference.reference_selection import prepare_reference_section


DEFAULT_DURATION_SECONDS = 30.0


def generate_reference_sample(
    reference_audio: str,
    output_dir: str,
    prompt: str,
    analysis: dict | None = None,
    duration_seconds: float = DEFAULT_DURATION_SECONDS,
) -> dict:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    if not _has_enabled_provider():
        return {
            "status": "disabled",
            "sample": None,
            "duration_seconds": duration_seconds,
            "provider": "audio_generation",
            "model": None,
            "attempts": [],
            "limitations": [
                "No local audio generation provider is enabled.",
                "Enable ACE-Step with PROMPT2MIDI_ENABLE_ACE_STEP=1 after starting its local API.",
            ],
        }

    attempts: list[dict] = []
    transform = (analysis or {}).get("reference_transform") or {}
    section = prepare_reference_section(
        reference_audio,
        output_dir,
        duration_seconds=duration_seconds,
        strategy=_reference_section_strategy(transform),
    )
    reference_groove = analyze_reference_groove(
        reference_audio,
        (analysis or {}).get("bpm"),
        section=section,
    )
    analysis_with_groove = dict(analysis or {})
    analysis_with_groove["reference_groove"] = reference_groove
    conditioned_prompt = _condition_prompt(prompt, reference_groove, analysis_with_groove.get("reference_transform"))
    ace_reference_audio = section["path"]
    control_scaffold = None
    if _should_use_bass_proxy_reference(transform, prompt):
        if _should_skip_bass_proxy_reference(transform):
            attempts.append(
                {
                    "provider": "bass_proxy_reference",
                    "status": "skipped",
                    "message": (
                        "Bass-proxy conditioning is disabled for rich/vocal references because the generated "
                        "bass scaffold can contaminate ACE with unstable timing or unmusical pitch movement. "
                        "Set PROMPT2MIDI_ALLOW_EXPERIMENTAL_RICH_BASS_PROXY=1 to force this diagnostic route."
                    ),
                }
            )
        else:
            try:
                from analysis.generation.rendering.structured_render import render_control_scaffold

                internal_dir = os.path.join(output_dir, "_internal")
                control_scaffold = render_control_scaffold(
                    reference_path=section["path"],
                    output_dir=internal_dir,
                    prompt=prompt,
                    analysis=analysis_with_groove,
                    reference_groove=reference_groove,
                    duration_seconds=duration_seconds,
                )
                ace_reference_audio = _build_bass_proxy_reference(
                    section_path=section["path"],
                    scaffold_path=control_scaffold["path"],
                    output_dir=internal_dir,
                )
                analysis_with_groove["control_scaffold"] = control_scaffold
                analysis_with_groove["bass_proxy_reference"] = {
                    "path": ace_reference_audio,
                    "method": "highpassed_real_reference_plus_generated_in_key_bass_guide",
                    "purpose": "Preserve percussion/energy while removing original bass pitch notes from ACE conditioning.",
                    "diagnostic_only": True,
                }
                conditioned_prompt = _bass_proxy_reference_direction() + " " + conditioned_prompt
            except Exception as exc:
                attempts.append({"provider": "bass_proxy_reference", "status": "failed", "message": str(exc)})
    elif _should_use_control_scaffold(transform, prompt):
        try:
            from analysis.generation.rendering.structured_render import render_control_scaffold

            control_scaffold = render_control_scaffold(
                reference_path=section["path"],
                output_dir=output_dir,
                prompt=prompt,
                analysis=analysis_with_groove,
                reference_groove=reference_groove,
                duration_seconds=duration_seconds,
            )
            ace_reference_audio = control_scaffold["path"]
            analysis_with_groove["control_scaffold"] = control_scaffold
            conditioned_prompt = _control_scaffold_direction() + " " + conditioned_prompt
        except Exception as exc:
            attempts.append({"provider": "control_scaffold", "status": "failed", "message": str(exc)})

    ace = generate_with_ace_step(
        reference_audio=ace_reference_audio,
        output_dir=output_dir,
        prompt=conditioned_prompt,
        analysis=analysis_with_groove,
        duration_seconds=duration_seconds,
    )
    attempts.append(_attempt_summary(ace))
    if ace.get("status") == "succeeded":
        ace["reference_section"] = section
        ace["reference_groove"] = reference_groove
        if control_scaffold:
            ace["control_scaffold"] = control_scaffold
        ace["attempts"] = attempts
        return ace

    if os.environ.get("PROMPT2MIDI_ENABLE_AUDIOCRAFT") == "1":
        try:
            from analysis.generation.providers.audiocraft_musicgen import generate_sample as generate_audiocraft_sample

            mode = os.environ.get("PROMPT2MIDI_AUDIOCRAFT_MODE") or "text"
            fallback = generate_audiocraft_sample(
                reference_audio=section["path"],
                output_dir=output_dir,
                prompt=conditioned_prompt,
                duration_seconds=duration_seconds,
                mode=mode,
            )
            if fallback.get("sample"):
                fallback["quality"] = score_audio_candidate(fallback["sample"], target_duration=duration_seconds)
            fallback["reference_section"] = section
            fallback["reference_groove"] = reference_groove
            attempts.append(_attempt_summary(fallback))
            fallback["attempts"] = attempts
            return fallback
        except Exception as exc:
            attempts.append({"provider": "audiocraft_musicgen", "status": "failed", "message": str(exc)})

    try:
        from analysis.generation.providers.musicgen_generation import generate_reference_sample as generate_transformers_sample

        legacy = generate_transformers_sample(
            reference_audio=section["path"],
            output_dir=output_dir,
            prompt=conditioned_prompt,
            duration_seconds=duration_seconds,
        )
        legacy["reference_section"] = section
        legacy["reference_groove"] = reference_groove
        attempts.append(_attempt_summary(legacy))
        legacy["attempts"] = attempts
        return legacy
    except Exception as exc:
        attempts.append({"provider": "musicgen_melody", "status": "failed", "message": str(exc)})

    return {
        "status": "disabled",
        "sample": None,
        "duration_seconds": duration_seconds,
        "provider": "audio_generation",
        "model": None,
        "reference_section": section,
        "reference_groove": reference_groove,
        "attempts": attempts,
        "limitations": [
            "No enabled local audio generation provider succeeded.",
            "Enable ACE-Step with PROMPT2MIDI_ENABLE_ACE_STEP=1 after starting its local API.",
        ],
    }


def _has_enabled_provider() -> bool:
    return any(
        os.environ.get(name) == "1"
        for name in (
            "PROMPT2MIDI_ENABLE_ACE_STEP",
            "PROMPT2MIDI_ENABLE_AUDIOCRAFT",
            "PROMPT2MIDI_ENABLE_MUSICGEN",
        )
    )


def _reference_section_strategy(reference_transform: dict) -> str:
    configured = os.environ.get("PROMPT2MIDI_REFERENCE_SECTION_STRATEGY")
    if configured:
        return configured
    rich_reference = (reference_transform or {}).get("rich_reference") or {}
    vocal = (reference_transform or {}).get("vocals") or {}
    if rich_reference.get("enabled") or vocal.get("preserve_role"):
        return "early_character"
    return "stable_energy"


def _should_use_control_scaffold(reference_transform: dict, prompt: str) -> bool:
    if os.environ.get("PROMPT2MIDI_DISABLE_CONTROL_SCAFFOLD") == "1":
        return False
    if os.environ.get("PROMPT2MIDI_ACE_STEP_CONTROL_SCAFFOLD") == "1":
        return True
    return False


def _should_use_bass_proxy_reference(reference_transform: dict, prompt: str) -> bool:
    return os.environ.get("PROMPT2MIDI_ACE_STEP_BASS_PROXY_REFERENCE") == "1"


def _should_skip_bass_proxy_reference(reference_transform: dict) -> bool:
    if os.environ.get("PROMPT2MIDI_ALLOW_EXPERIMENTAL_RICH_BASS_PROXY") == "1":
        return False
    vocal = (reference_transform or {}).get("vocals") or {}
    rich = (reference_transform or {}).get("rich_reference") or {}
    return bool(vocal.get("preserve_role") or rich.get("enabled"))


def _build_bass_proxy_reference(section_path: str, scaffold_path: str, output_dir: str) -> str:
    """Make diagnostic ACE conditioning audio with real percussion but without original bass pitches."""
    ffmpeg = os.environ.get("PROMPT2MIDI_FFMPEG") or shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to build the bass-proxy ACE reference.")
    output_path = os.path.abspath(os.path.join(output_dir, "ace-bass-proxy-reference.wav"))
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            section_path,
            "-i",
            scaffold_path,
            "-filter_complex",
            (
                "[0:a]highpass=f=205,volume=0.9[real_hi];"
                "[1:a]lowpass=f=190,volume=0.52[bass_guide];"
                "[real_hi][bass_guide]amix=inputs=2:duration=first:normalize=0,"
                "alimiter=limit=0.92"
            ),
            "-ac",
            "2",
            "-ar",
            "48000",
            output_path,
        ],
        check=True,
    )
    return output_path


def _bass_proxy_reference_direction() -> str:
    return (
        "ACE source note: the attached cover source is an experimental diagnostic bass-proxy guide, not the original recording; "
        "its upper percussion/energy comes from the reference while the low bass guide uses new in-key notes. "
        "Follow the bass rhythm, envelope, punch, rests, and low-end role from this proxy, not the original bass melody; "
        "do not recreate the original bass pitch sequence. Use a clean, rounded, professional funk bass tone; "
        "no sick/gurgling/growling/wobbling bass artifacts. "
    )


def _control_scaffold_direction() -> str:
    return (
        "Use the attached generated control scaffold as the hard rhythm and bass reference: "
        "preserve its bass rhythm, bass note lengths, rests, steady bass envelope, kick pocket, and key area; "
        "you may replace the exact synth texture with professional production, but do not turn the bass into glitches, chops, jumps, breaks, or off-scale notes."
    )


def _condition_prompt(prompt: str, reference_groove: dict, reference_transform: dict | None = None) -> str:
    parts = []
    bass_lock = _bass_lock_direction(reference_transform or {})
    if bass_lock:
        parts.append(bass_lock)
    harmonic = _harmonic_transform(reference_transform or {})
    harmonic_prompt = _harmonic_direction(harmonic).strip()
    if harmonic_prompt:
        parts.append(harmonic_prompt)
    base = _model_prompt_for_transform(prompt, reference_transform or {})
    if base:
        parts.append(base)
    groove_prompt = _groove_prompt_for_transform(reference_groove or {}, reference_transform or {})
    if groove_prompt:
        parts.append(groove_prompt)
    character_prompt = _reference_character_prompt(reference_transform or {})
    if character_prompt:
        parts.append(character_prompt)
    transform_prompt = _compact_transform_prompt(reference_transform or {})
    if transform_prompt:
        parts.append(transform_prompt)
    style_brief = (reference_transform or {}).get("style_brief") or "the detected reference style"
    style_target = "the requested style direction and reference groove pocket" if (prompt or "").strip() else style_brief
    vocal = _vocal_transform(reference_transform or {})
    direct_vocal = _uses_direct_vocal(vocal)
    track_kind = "track" if direct_vocal else "instrumental guide track"
    vocal_direction = ""
    if direct_vocal:
        vocal_direction = (
        f"include a clear new {vocal.get('role', 'vocal hook')} with original words, new voice, and new melody contour; "
        "do not copy the reference singer, lyrics, or exact hook; "
        )
    elif vocal.get("preserve_role"):
        vocal_direction = (
            f"translate the reference {vocal.get('role', 'vocal hook')} role into a clean synth, keyboard, or short non-lyrical vocal-chop hook; "
            "avoid lead singing, warped formants, stretched chops, and squeezed transition artifacts; "
        )
    parts.append(
        f"make a producer-grade original {track_kind} in {style_target}; "
        f"{vocal_direction}"
        "keep the reference energy, timing pocket, rhythmic confidence, and mix clarity; "
        "use conventional professional drums, bass, stabs, guitars, keys, and synths for the detected style; "
        "avoid random glitches, alien sci-fi sounds, cartoon timbres, atonal artifacts, weak drums, thin bass, "
        "copied lead hooks, and copied vocal identity"
    )
    return _sentence_limited(". ".join(parts), 900)


def _compact_transform_prompt(reference_transform: dict) -> str:
    if not reference_transform:
        return ""
    bass = reference_transform.get("bass") or {}
    profile = reference_transform.get("similarity_profile") or {}
    similarity = float(reference_transform.get("groove_similarity") or 0.0)
    if similarity < 0.4:
        controls = [
            profile.get("label") or "fresh original track, not a cover",
            "same tempo, key area, rhythmic attitude, tension, and role balance",
            "new bass pitch sequence",
            "new percussion accents",
            "new stab/effect timbre",
        ]
    elif similarity < 0.75:
        controls = [
            profile.get("label") or "reference-inspired original",
            "same tempo, key area, groove pocket, and mood",
            "noticeably new bass notes and secondary percussion",
        ]
    else:
        controls = [
            profile.get("label") or "strong reference groove anchor",
            "same tempo, key area, timing pocket, and energy",
            "new generated performance with different samples",
        ]
    if bass.get("vary_notes"):
        if bass.get("preserve_sound_design"):
            controls.append("keep bass rhythm and steady bass sound; change only pitch notes")
            controls.append("no glitchy, choppy, stuttered, or jumpy bass behavior")
        else:
            controls.append("keep bass rhythm but change notes")
    harmonic = _harmonic_transform(reference_transform)
    if harmonic.get("strict_scale"):
        controls.append(f"scale-aware inside {harmonic.get('key')} with no clashing off-scale notes")
    vocal = _vocal_transform(reference_transform)
    if vocal.get("preserve_role"):
        if _uses_direct_vocal(vocal):
            controls.append(f"new {vocal.get('role', 'vocal hook')} role, not copied")
        else:
            controls.append(f"clean instrumental proxy for the {vocal.get('role', 'vocal hook')} role")
    rich_reference = (reference_transform or {}).get("rich_reference") or {}
    if rich_reference.get("enabled"):
        controls.append("simplify dense hooks and transitions into stable intentional parts")
    return "control brief: " + "; ".join(controls)


def _model_prompt_for_transform(prompt: str, reference_transform: dict) -> str:
    base = _sanitize_user_prompt_for_model(prompt)
    style_brief = reference_transform.get("style_brief") or "the reference's detected genre, BPM, key area, groove, mood, and instrumentation"
    try:
        similarity = float(reference_transform.get("groove_similarity") or 0.0)
    except (TypeError, ValueError):
        similarity = 0.0

    if not reference_transform or similarity >= 0.75:
        return base
    vocal = _vocal_transform(reference_transform)
    if _uses_direct_vocal(vocal):
        vocal_context = (
        f"preserve the reference's {vocal.get('role', 'vocal hook')} function with original words, new voice, and changed melody contour; "
        )
    elif vocal.get("preserve_role"):
        vocal_context = (
            f"preserve the reference's {vocal.get('role', 'vocal hook')} function as a clean synth/keyboard/non-lyrical chop hook; "
            "do not attempt lead vocal resynthesis; "
        )
    else:
        vocal_context = ""
    if base:
        style_context = "" if _has_explicit_style_direction(base) else f"detected reference style: {style_brief}; "
        bass_context = _bass_lock_direction(reference_transform)
        if similarity < 0.4:
            return (
                f"{base}; {style_context}use the reference as a producer brief for tempo, key area, groove attitude, mood, "
                f"and broad arrangement roles; {vocal_context}{bass_context}"
                "change the bassline notes, percussion accents, and sound palette clearly"
            )
        return (
            f"{base}; {style_context}keep the same tempo, key area, groove pocket, and mood from the reference; "
            f"{vocal_context}{bass_context}"
            "make the bass notes and secondary percussion noticeably different"
        )
    if similarity < 0.4:
        return (
            f"create a new original track using the reference as a producer brief: {style_brief}; "
            "keep the same tempo, key area, groove attitude, mood, and broad arrangement roles; "
            f"{vocal_context}"
            "change the bassline notes, percussion accents, and sound palette clearly while staying musical and tonal"
        )
    return (
        f"create a reference-inspired original track using this detected style: {style_brief}; "
        f"keep the same tempo, key area, groove pocket, and mood; {vocal_context}"
        "make the bass notes and secondary percussion noticeably different"
    )


def _vocal_transform(reference_transform: dict) -> dict:
    vocal = (reference_transform or {}).get("vocals") or {}
    if vocal.get("preserve_role"):
        return vocal
    return {}


def _bass_lock_direction(reference_transform: dict) -> str:
    bass = (reference_transform or {}).get("bass") or {}
    if not bass.get("preserve_sound_design"):
        return ""
    return (
        "bass lock: same bassline rhythm, same note lengths, same rests, same steady bass tone and envelope, "
        "same bass rhythm accents, different bass pitch notes only; avoid glitchy bass, choppy bass, stutter bass, jumpy edits, and broken breakbeat bass behavior; "
    )


def _uses_direct_vocal(vocal: dict) -> bool:
    return bool(vocal.get("preserve_role")) and vocal.get("render_mode") != "instrumental_hook_proxy"


def _harmonic_transform(reference_transform: dict) -> dict:
    harmonic = (reference_transform or {}).get("harmonic") or {}
    return harmonic if isinstance(harmonic, dict) else {}


def _harmonic_direction(harmonic: dict) -> str:
    key = harmonic.get("key")
    if harmonic.get("strict_scale") and key:
        return (
            f"global harmonic rule: keep bassline, hook, synth melody, chord stabs, fills, risers, and effects tuned inside {key}; "
            "allow only resolved borrowed or chromatic tones that are musically supported by the key area; "
            "no out-of-tune instruments, clashing off-key notes, random chromatic wrong notes, or unresolved atonal artifacts; "
        )
    return (
        "global harmonic rule: keep all bass, hooks, synth melodies, chord stabs, fills, risers, and effects tonal, "
        "resolved, and scale-aware; no out-of-tune instruments, clashing off-key notes, random chromatic wrong notes, "
        "or unresolved atonal artifacts; "
    )


def _reference_character_prompt(reference_transform: dict) -> str:
    character = (reference_transform or {}).get("reference_character") or {}
    prompt = str(character.get("prompt") or "").strip()
    if not prompt:
        return ""
    return f"{prompt}; preserve this mood and energy while changing the composition details"


def _sanitize_user_prompt_for_model(prompt: str) -> str:
    text = " ".join((prompt or "").replace("\n", " ").split())
    if not text:
        return ""
    text = re.sub(
        r"\bbetween\s+(?:low|medium[-\s]?low|medium|medium[-\s]?high|high|very[-\s]?high|near[-\s]?identical|identical)"
        r"(?:\s+similarity)?\s+and\s+(?:low|medium[-\s]?low|medium|medium[-\s]?high|high|very[-\s]?high|near[-\s]?identical|identical)"
        r"(?:\s+similarity)?\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b([1-9][0-9]?|100)\s*%?\s*(identical|same|similar|close|similarity)\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(variation|different|difference)\b.{0,20}\b([1-9][0-9]?|100)\s*%",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(low|medium[-\s]?low|medium|medium[-\s]?high|high|very[-\s]?high)\s+similarity\b|"
        r"\bsimilarity\s+(low|medium[-\s]?low|medium|medium[-\s]?high|high|very[-\s]?high)\b|"
        r"\b(near[-\s]?identical|identical)\s+(?:similarity\s+)?(?:with\s+)?twist\b|"
        r"\b(?:near[-\s]?identical|identical)\s+similarity\b|"
        r"\bnear[-\s]?identical\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b([1-9][0-9]?|100)\s*%\s*(variation|different|difference)\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s+([,;.])", r"\1", text)
    text = re.sub(r"\bsomething,\s+(?=very close|close|same|new|different)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*([,;.])\s*:\s*", r"\1 ", text)
    text = re.sub(r"^[,;:.\s]+", "", text)
    text = re.sub(r"^(with|and)\b\s*[,;.]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" ;,.")
    return text


def _has_explicit_style_direction(text: str) -> bool:
    return bool(
        re.search(
            r"\b(house|tech house|deep house|minimal|techno|breakbeat|disco|funk|dance[-\s]?pop|synth[-\s]?pop|"
            r"hip[-\s]?hop|trap|r&b|rnb|rock|ambient|downtempo|drum and bass|dnb|garage|trance)\b",
            text or "",
            flags=re.IGNORECASE,
        )
    )


def _groove_prompt_for_transform(reference_groove: dict, reference_transform: dict) -> str:
    bass = reference_transform.get("bass") or {}
    similarity = float(reference_transform.get("groove_similarity") or 0.0)
    groove_available = reference_groove.get("method") not in (None, "", "unavailable")
    if not bass.get("vary_notes") and similarity >= 0.92:
        return reference_groove.get("prompt") or ""

    if similarity < 0.4:
        grid_intro = (
            "reference style fingerprint: keep the same BPM, key area, detected genre, "
            "mood, low-end role, swing or timing attitude, and energy; "
            "use the grids as a stylistic pocket reference, not as an exact copy"
        )
        grid_label = "style-reference"
    elif similarity < 0.75:
        grid_intro = (
            "reference groove fingerprint: keep the club attitude, low-end weight, and timing pocket, "
            "while making a noticeably new bassline and some new secondary percussion accents"
        )
        grid_label = "pocket-reference"
    else:
        grid_intro = (
            "reference rhythm fingerprint: preserve the club attitude, low-end weight, and timing feel without copying bass pitches"
        )
        grid_label = "accent"

    parts = [
        grid_intro,
    ]
    bass_lock = _bass_lock_direction(reference_transform)
    if bass_lock:
        parts.append(bass_lock.rstrip(" ;"))
    for key, label in (
        ("kick_pattern_16th", "kick accents"),
        ("bass_accent_pattern_16th", "bass rhythm accents"),
        ("hat_pattern_16th", "hat/percussion accents"),
    ):
        if groove_available and reference_groove.get(key):
            parts.append(f"{label} {grid_label} over two bars on 16th-grid positions {reference_groove[key]}")
    if groove_available and reference_groove.get("drum_feel"):
        parts.append(reference_groove["drum_feel"])
    if groove_available and reference_groove.get("bass_feel"):
        parts.append(reference_groove["bass_feel"])
    if groove_available and reference_groove.get("low_end_weight"):
        parts.append(f"{reference_groove['low_end_weight']} low-end weight")
    if groove_available and reference_groove.get("club_energy"):
        parts.append(f"{reference_groove['club_energy']} underground club energy")
    parts.append("choose a new bass note sequence in the same key area")
    return "; ".join(parts)


def _sentence_limited(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    clipped = text[:limit]
    for separator in (". ", "; "):
        index = clipped.rfind(separator)
        if index >= int(limit * 0.65):
            return clipped[: index + 1].strip()
    return clipped.rsplit(" ", 1)[0].strip()


def _attempt_summary(payload: dict) -> dict:
    return {
        "provider": payload.get("provider"),
        "status": payload.get("status"),
        "model": payload.get("model"),
        "sample": payload.get("sample"),
        "message": "; ".join(str(item) for item in payload.get("limitations", [])[:2]),
    }
