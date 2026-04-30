#!/usr/bin/env python3
"""Turn producer direction into controllable reference-transformation settings."""
from __future__ import annotations

import re
import os

_SIMILARITY_PROFILES = {
    "low": {
        "id": "low",
        "label": "Low similarity",
        "target_similarity": 0.25,
        "ace_task_type": "text2music",
        "audio_cover_strength": 0.0,
        "cover_noise_strength": 0.0,
        "description": (
            "Fresh original track in the same genre, BPM, key area, mood, and production lane; "
            "use the reference as a style brief, not as a cover."
        ),
    },
    "medium": {
        "id": "medium",
        "label": "Medium similarity",
        "target_similarity": 0.58,
        "ace_task_type": "cover",
        "audio_cover_strength": 0.42,
        "cover_noise_strength": 0.12,
        "description": (
            "Clearly reference-inspired track with the same pocket and role balance, but new bass notes, "
            "secondary percussion, and sound palette."
        ),
    },
    "medium_low": {
        "id": "medium_low",
        "label": "Medium-low similarity",
        "target_similarity": 0.42,
        "ace_task_type": "cover",
        "audio_cover_strength": 0.22,
        "cover_noise_strength": 0.05,
        "description": (
            "Fresh new track that keeps more of the reference pocket than low similarity, while still changing "
            "bass notes, percussion accents, and sound palette clearly."
        ),
    },
    "medium_high": {
        "id": "medium_high",
        "label": "Medium-high similarity",
        "target_similarity": 0.69,
        "ace_task_type": "cover",
        "audio_cover_strength": 0.57,
        "cover_noise_strength": 0.22,
        "description": (
            "Close reference-inspired track with stronger groove anchoring than medium, while still allowing "
            "noticeable bass, percussion, and timbre variation."
        ),
    },
    "high": {
        "id": "high",
        "label": "High similarity",
        "target_similarity": 0.80,
        "ace_task_type": "cover",
        "audio_cover_strength": 0.72,
        "cover_noise_strength": 0.34,
        "description": (
            "Strong reference groove anchor with the same tempo, key area, timing pocket, and energy; "
            "change musical details and samples."
        ),
    },
    "near_identical_twist": {
        "id": "near_identical_twist",
        "label": "Near-identical with twist",
        "target_similarity": 0.92,
        "ace_task_type": "cover",
        "audio_cover_strength": 0.93,
        "cover_noise_strength": 0.68,
        "description": (
            "Very close reference transformation with a twist: keep the groove and arrangement roles, "
            "but avoid a literal duplicate of the bass pitch sequence, hook, vocal identity, or master recording."
        ),
    },
}


def build_reference_transform(user_prompt: str, analysis: dict) -> dict:
    text = " ".join((user_prompt or "").lower().split())
    reference_groove = analysis.get("reference_groove") or {}
    bass_transcription = analysis.get("bass_transcription") or {}
    drums = analysis.get("drums") or {}

    bass_mode = _bass_mode(text)
    similarity_profile = _similarity_profile(text, analysis)
    groove_similarity = _groove_similarity(text, analysis, bass_mode, similarity_profile)
    stab = _stab_replacement(text)
    style = _style_profile(analysis)
    prompt = _prompt(
        groove_similarity=groove_similarity,
        bass_mode=bass_mode,
        stab=stab,
        style=style,
        reference_groove=reference_groove,
        bass_transcription=bass_transcription,
        drums=drums,
    )
    bass_mode = _scale_bass_variation(bass_mode, groove_similarity)

    return {
        "version": 1,
        "intent": "reference_transformation",
        "groove_similarity": groove_similarity,
        "similarity_profile": similarity_profile or _custom_similarity_profile(groove_similarity),
        "difference_level": round((1.0 - groove_similarity) * 10, 2),
        "generation_mode": "style_conditioned" if (similarity_profile or {}).get("ace_task_type") == "text2music" else "source_conditioned",
        "style": style,
        "style_brief": style["brief"],
        "bass": bass_mode,
        "drums": {
            "keep_kick_rhythm": groove_similarity >= 0.78,
            "keep_hat_percussion_feel": groove_similarity >= 0.72,
            "source": "drum_stem" if (analysis.get("stem_separation") or {}).get("paths", {}).get("drums") else "full_mix_fingerprint",
        },
        "stab_replacement": stab,
        "prompt": prompt,
        "warnings": [
            "This preserves groove, roles, and energy as controllable traits; final audio remains a new generated performance."
        ],
    }


def _groove_similarity(text: str, analysis: dict, bass_mode: dict, similarity_profile: dict | None = None) -> float:
    if similarity_profile:
        return float(similarity_profile["target_similarity"])
    if bass_mode.get("vary_notes") and re.search(r"\b(same groove|same feeling|same mood|same percussion)\b", text):
        return 0.8
    if re.search(r"\b(100|exact|copy|replica|identical)\b", text):
        return 0.95
    if re.search(r"\b(90|very close|close|keep|preserve)\b", text):
        return 0.9
    if re.search(r"\b(80|similar|inspired)\b", text):
        return 0.8
    if "different" in text or "replace" in text:
        return 0.86
    return 0.78


def _similarity_profile(text: str, analysis: dict) -> dict | None:
    level = (
        _named_similarity_level((analysis or {}).get("reference_similarity_level"), allow_bare=True)
        or _named_similarity_level((analysis or {}).get("similarity_level"), allow_bare=True)
        or _named_similarity_level(os.environ.get("PROMPT2MIDI_REFERENCE_SIMILARITY_LEVEL"), allow_bare=True)
        or _named_similarity_level(text, allow_bare=False)
    )
    if level:
        return dict(_SIMILARITY_PROFILES[level])

    explicit = _explicit_similarity(text, analysis)
    if explicit is not None:
        return _custom_similarity_profile(explicit)
    return None


def _named_similarity_level(value: object, *, allow_bare: bool = False) -> str | None:
    text = " ".join(str(value or "").lower().replace("_", " ").replace("-", " ").split())
    if not text:
        return None
    if re.search(r"\b(near identical|near identical twist|identical with twist|almost identical|closest|closest with twist)\b", text):
        return "near_identical_twist"
    if re.search(r"\bidentical\s+similarity\b", text):
        return "near_identical_twist"
    if re.search(r"\b(medium low|mid low|low medium|medium low similarity|similarity medium low)\b", text) or (
        allow_bare and text in {"medium low", "mid low", "low medium"}
    ):
        return "medium_low"
    if re.search(r"\b(medium high|mid high|high medium|medium high similarity|similarity medium high)\b", text) or (
        allow_bare and text in {"medium high", "mid high", "high medium"}
    ):
        return "medium_high"
    if re.search(r"\bhigh\s+similarity\b|\bsimilarity\s+high\b", text) or (allow_bare and text == "high"):
        return "high"
    if re.search(r"\bmedium\s+similarity\b|\bsimilarity\s+medium\b", text) or (allow_bare and text == "medium"):
        return "medium"
    if re.search(r"\blow\s+similarity\b|\bsimilarity\s+low\b", text) or (allow_bare and text == "low"):
        return "low"
    if text in _SIMILARITY_PROFILES:
        return text
    return None


def _custom_similarity_profile(value: float) -> dict:
    value = max(0.0, min(1.0, float(value)))
    return {
        "id": "custom",
        "label": "Custom similarity",
        "target_similarity": value,
        "description": "Custom numeric similarity retained for compatibility with older test controls.",
    }


def _explicit_similarity(text: str, analysis: dict) -> float | None:
    for key in ("reference_similarity", "target_similarity", "groove_similarity"):
        value = _similarity_value((analysis or {}).get(key))
        if value is not None:
            return value
    env_similarity = _similarity_value(os.environ.get("PROMPT2MIDI_REFERENCE_SIMILARITY"))
    if env_similarity is not None:
        return env_similarity

    for key in ("reference_difference", "variation_level", "difference_level"):
        value = _difference_value((analysis or {}).get(key))
        if value is not None:
            return value
    env_difference = _difference_value(os.environ.get("PROMPT2MIDI_REFERENCE_DIFFERENCE"))
    if env_difference is not None:
        return env_difference

    match = re.search(r"\b([1-9][0-9]?|100)\s*%?\s*(identical|same|similar|close|similarity)\b", text)
    if match:
        return max(0.0, min(1.0, float(match.group(1)) / 100.0))
    match = re.search(r"\b(variation|different|difference)\b.{0,20}\b([1-9][0-9]?|100)\s*%", text)
    if match:
        return max(0.0, min(1.0, 1.0 - float(match.group(2)) / 100.0))
    match = re.search(r"\b([1-9][0-9]?|100)\s*%\s*(variation|different|difference)\b", text)
    if match:
        return max(0.0, min(1.0, 1.0 - float(match.group(1)) / 100.0))

    match = re.search(r"\b([1-9](?:\.\d+)?|10)\s*/\s*10\b.{0,40}\b(different|variation|difference)\b", text)
    if match:
        return _difference_to_similarity(float(match.group(1)))
    match = re.search(r"\b(different|variation|difference)\b.{0,30}\b([1-9](?:\.\d+)?|10)\s*/\s*10\b", text)
    if match:
        return _difference_to_similarity(float(match.group(2)))
    match = re.search(r"\b([1-9](?:\.\d+)?|10)\b.{0,20}\b(different|variation|difference)\b", text)
    if match:
        return _difference_to_similarity(float(match.group(1)))
    return None


def _similarity_value(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 1.0:
        number /= 100.0
    return max(0.0, min(1.0, number))


def _difference_value(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return _difference_to_similarity(float(value))
    except (TypeError, ValueError):
        return None


def _difference_to_similarity(level: float) -> float:
    level = max(1.0, min(10.0, level))
    return round(0.98 - ((level - 1.0) / 9.0) * 0.58, 3)


def _bass_mode(text: str) -> dict:
    vary_notes = bool(
        re.search(r"\b(bit different|little different|different|variation|vary|new)\b", text)
        or re.search(r"\b(change|alter|shift)\b.{0,80}\b(bassline|bass|notes|pitch)\b", text)
        or re.search(r"\b(do not reuse|avoid|not the exact)\b.{0,80}\b(original bass|bass pitch|bassline notes)\b", text)
    )
    keep_groove = bool(re.search(r"\b(same groove|same feeling|same mood|keep groove|preserve groove)\b", text))
    return {
        "keep_rhythm": True,
        "keep_syncopation": True,
        "vary_notes": vary_notes,
        "vary_sound_design": True,
        "variation_amount": 0.16 if vary_notes and keep_groove else (0.22 if vary_notes else 0.12),
        "source_pitch_lock": 0.45 if vary_notes else 0.78,
        "source_rhythm_lock": 0.92 if keep_groove else 0.84,
        "description": (
            "keep the exact reference bass rhythm, rests, syncopation, and attitude, but change the pitch notes slightly"
            if vary_notes and keep_groove
            else "keep the reference bass rhythm and syncopation, but alter note choices and bass tone"
            if vary_notes
            else "preserve the reference bass rhythm, contour, and tone balance"
        ),
    }


def _scale_bass_variation(bass_mode: dict, groove_similarity: float) -> dict:
    scaled = dict(bass_mode)
    difference = max(0.0, min(1.0, 1.0 - groove_similarity))
    if scaled.get("vary_notes"):
        scaled["variation_amount"] = round(max(float(scaled.get("variation_amount") or 0.0), difference), 3)
        scaled["source_pitch_lock"] = round(max(0.18, min(float(scaled.get("source_pitch_lock") or 0.45), 0.72 - difference * 0.5)), 3)
        scaled["source_rhythm_lock"] = round(max(0.84, float(scaled.get("source_rhythm_lock") or 0.84)), 3)
        if groove_similarity < 0.4:
            scaled["description"] = (
                "keep the same BPM, genre, key area, low-end role, and reference groove attitude, "
                "but write a clearly new bass note sequence and bass tone"
            )
        elif groove_similarity < 0.75:
            scaled["description"] = (
                "keep the same BPM, genre, key area, bass role, and syncopated groove feel, "
                "but make a noticeably new bassline note sequence"
            )
    return scaled


def _stab_replacement(text: str) -> dict:
    mentions_stab = bool(re.search(r"\b(stab|stabs|stabbing|chord hit|main effect)\b", text))
    replacement = "dry metallic FM chord stab"
    match = re.search(r"replace (?:it|the stab|the stabbing effect|main stabbing effect)?\s*(?:with|by)\s+([^.;]+)", text)
    if match:
        replacement = match.group(1).strip()
    return {
        "enabled": mentions_stab or "replace" in text,
        "source_role": "main stabbing effect",
        "replacement": replacement,
        "keep_rhythm": True,
        "description": f"replace the main stab role with {replacement}",
    }


def _style_profile(analysis: dict) -> dict:
    genre = analysis.get("genre_deep") if (analysis.get("genre_deep") or {}).get("confidence", 0) > 0 else analysis.get("genre") or {}
    primary = str(genre.get("primary") or "").strip()
    if not primary or primary.lower().startswith("unknown"):
        primary = "reference-informed instrumental"
    tags = [str(tag) for tag in (genre.get("tags") or [])[:4] if str(tag).strip()]
    groove = analysis.get("groove") or {}
    groove_text = groove.get("description") or groove.get("feel") or "reference groove"
    bpm = analysis.get("bpm")
    key = analysis.get("key")
    brief_parts = [primary]
    if tags:
        brief_parts.append("with " + ", ".join(tags))
    bpm_value = _number_or_none(bpm)
    if bpm_value:
        brief_parts.append(f"around {round(bpm_value)} BPM")
    if key and str(key).lower() != "unknown":
        brief_parts.append(f"in the {key} key area")
    brief_parts.append(str(groove_text))
    return {
        "primary": primary,
        "tags": tags,
        "bpm": bpm_value or bpm,
        "key": key,
        "groove": groove_text,
        "brief": "; ".join(brief_parts),
    }


def _prompt(
    *,
    groove_similarity: float,
    bass_mode: dict,
    stab: dict,
    style: dict,
    reference_groove: dict,
    bass_transcription: dict,
    drums: dict,
) -> str:
    style_brief = style.get("brief") or "the detected reference style"
    parts = [
        _similarity_instruction(groove_similarity),
        f"keep the same BPM, key area, groove attitude, and detected reference style: {style_brief}",
        bass_mode["description"],
        (
            "preserve signature rhythmic roles when present: micro-percussion answers, swung hat/shaker movement, "
            "short rhythmic vocal-like chops as percussive texture, and small call-response accent variations"
        ),
    ]
    if bass_mode.get("vary_notes"):
        if groove_similarity < 0.4:
            parts.insert(3, "do not reuse the original bass pitch sequence; make a clearly different bassline while preserving the rhythmic role and pocket")
        elif groove_similarity < 0.75:
            parts.insert(3, "do not reuse the exact original bass pitch sequence; make a noticeable note variation while preserving timing feel")
        else:
            parts.insert(3, "do not reuse the exact original bass pitch sequence; make a small new note variation while preserving timing")
    if groove_similarity >= 0.75:
        parts.append("keep the kick and hat/percussion placement close to the reference but use new drum samples")
    elif groove_similarity >= 0.4:
        parts.append("keep the kick, hat, and percussion pocket close to the reference, but allow secondary accents to move")
    else:
        parts.append("keep the same tempo, timing feel, drum role, percussion energy, and rhythmic attitude, but compose a new accent pattern")
    if stab["enabled"]:
        parts.append(stab["description"] + ", not the original stab timbre")
    grid_verb = "preserve" if groove_similarity >= 0.75 else "use as style reference"
    if reference_groove.get("bass_accent_pattern_16th"):
        parts.append(f"{grid_verb} bass accent grid {reference_groove['bass_accent_pattern_16th']}")
    if reference_groove.get("kick_pattern_16th"):
        parts.append(f"{grid_verb} kick accent grid {reference_groove['kick_pattern_16th']}")
    if reference_groove.get("hat_pattern_16th"):
        parts.append(f"{grid_verb} hat/percussion feel grid {reference_groove['hat_pattern_16th']}")
    if bass_transcription.get("event_count"):
        parts.append(f"use extracted bass MIDI contour as reference with {bass_transcription['event_count']} events")
    if drums.get("method") not in (None, "unavailable"):
        parts.append(f"use extracted drum groove from {drums.get('method')}")
    parts.append("make a new original instrumental in the detected reference style, not a literal master recording duplicate")
    return "; ".join(parts)


def _number_or_none(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _similarity_instruction(groove_similarity: float) -> str:
    if groove_similarity >= 0.92:
        return (
            "reference transformation controls: stay very close to the reference groove, arrangement roles, "
            "low-end weight, and sound-design attitude while making a new generated performance"
        )
    if groove_similarity >= 0.75:
        return (
            "reference transformation controls: keep a strong reference groove and mood anchor, "
            "but allow new bass notes, drum samples, and effect timbres"
        )
    if groove_similarity >= 0.4:
        return (
            "reference transformation controls: use the reference as a producer brief, preserving tempo, key area, "
            "groove pocket, energy, and role balance while changing musical details clearly"
        )
    return (
        "reference transformation controls: create a fresh original track in the detected reference style; "
        "preserve tempo, key area, groove attitude, energy, and production role balance, but do not copy the hook, "
        "bass pitch sequence, percussion accents, or signature sound effects"
    )
