#!/usr/bin/env python3
"""Provider orchestration for reference-inspired audio samples."""
from __future__ import annotations

import os
import re
from pathlib import Path

from ace_step_generation import generate_with_ace_step
from audio_quality import score_audio_candidate
from reference_groove import analyze_reference_groove
from reference_selection import prepare_reference_section


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
    section = prepare_reference_section(reference_audio, output_dir, duration_seconds=duration_seconds)
    reference_groove = analyze_reference_groove(
        reference_audio,
        (analysis or {}).get("bpm"),
        section=section,
    )
    analysis_with_groove = dict(analysis or {})
    analysis_with_groove["reference_groove"] = reference_groove
    conditioned_prompt = _condition_prompt(prompt, reference_groove, analysis_with_groove.get("reference_transform"))

    ace = generate_with_ace_step(
        reference_audio=section["path"],
        output_dir=output_dir,
        prompt=conditioned_prompt,
        analysis=analysis_with_groove,
        duration_seconds=duration_seconds,
    )
    attempts.append(_attempt_summary(ace))
    if ace.get("status") == "succeeded":
        ace["reference_section"] = section
        ace["reference_groove"] = reference_groove
        ace["attempts"] = attempts
        return ace

    if os.environ.get("PROMPT2MIDI_ENABLE_AUDIOCRAFT") == "1":
        try:
            from audiocraft_musicgen import generate_sample as generate_audiocraft_sample

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
        from musicgen_generation import generate_reference_sample as generate_transformers_sample

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


def _condition_prompt(prompt: str, reference_groove: dict, reference_transform: dict | None = None) -> str:
    parts = []
    base = _model_prompt_for_transform(prompt, reference_transform or {})
    if base:
        parts.append(base)
    groove_prompt = _groove_prompt_for_transform(reference_groove or {}, reference_transform or {})
    if groove_prompt:
        parts.append(groove_prompt)
    transform_prompt = _compact_transform_prompt(reference_transform or {})
    if transform_prompt:
        parts.append(transform_prompt)
    style_brief = (reference_transform or {}).get("style_brief") or "the detected reference style"
    style_target = "the requested style direction and reference groove pocket" if (prompt or "").strip() else style_brief
    parts.append(
        f"make a producer-grade original instrumental in {style_target}; "
        "keep the reference energy, timing pocket, rhythmic confidence, and mix clarity; "
        "use conventional professional drums, bass, stabs, guitars, keys, and synths for the detected style; "
        "avoid random glitches, alien sci-fi sounds, cartoon timbres, atonal artifacts, weak drums, thin bass, "
        "copied lead hooks, and copied vocal identity"
    )
    return _sentence_limited(". ".join(parts), 1100)


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
        controls.append("keep bass rhythm but change notes")
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
    if base:
        style_context = "" if _has_explicit_style_direction(base) else f"detected reference style: {style_brief}; "
        if similarity < 0.4:
            return (
                f"{base}; {style_context}use the reference as a producer brief for tempo, key area, groove attitude, mood, "
                "and broad arrangement roles; change the bassline notes, percussion accents, and sound palette clearly"
            )
        return (
            f"{base}; {style_context}keep the same tempo, key area, groove pocket, and mood from the reference; "
            "make the bass notes and secondary percussion noticeably different"
        )
    if similarity < 0.4:
        return (
            f"create a new original instrumental using the reference as a producer brief: {style_brief}; "
            "keep the same tempo, key area, groove attitude, mood, and broad arrangement roles; "
            "change the bassline notes, percussion accents, and sound palette clearly while staying musical and tonal"
        )
    return (
        f"create a reference-inspired original instrumental using this detected style: {style_brief}; "
        "keep the same tempo, key area, groove pocket, and mood; make the bass notes and secondary percussion noticeably different"
    )


def _sanitize_user_prompt_for_model(prompt: str) -> str:
    text = " ".join((prompt or "").replace("\n", " ").split())
    if not text:
        return ""
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
        r"\b(low|medium[-\s]?low|medium|medium[-\s]?high|high)\s+similarity\b|\bsimilarity\s+(low|medium[-\s]?low|medium|medium[-\s]?high|high)\b|\b(near[-\s]?identical|identical)\s+(?:similarity\s+)?(?:with\s+)?twist\b|\bidentical\s+similarity\b",
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
