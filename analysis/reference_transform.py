#!/usr/bin/env python3
"""Turn producer direction into controllable reference-transformation settings."""
from __future__ import annotations

import re
import os

_SIMILARITY_PROFILES = {
    "low": {
        "id": "low",
        "label": "Low similarity",
        "target_similarity": 0.24,
        "ace_task_type": "cover",
        "audio_cover_strength": 0.21,
        "cover_noise_strength": 0.11,
        "bass_variation_amount": 0.88,
        "bass_pitch_lock": 0.18,
        "bass_rhythm_lock": 0.8,
        "vary_bass_notes": True,
        "variation_scope": (
            "write a new track using the reference as a style, energy, BPM, key-area, and mood anchor only; "
            "do not carry over the recognizable bass pitch motif, stab/effect samples, hook gestures, or signature sounds; "
            "keep low-end confidence, rhythmic attitude, detected pulse, and conventional professional instrumentation for the detected genre; "
            "write the new bassline as a strong musical hook or low-end driver in the detected key area, not as cautious root notes or a soft pad; "
            "staying tonal, style-usable, and producer-clean; do not drift into unrelated genre, glitch, alien, robotic, "
            "distorted, random, or experimental sounds"
        ),
        "description": (
            "Fresh original track in the same genre, BPM, key area, mood, and production lane; "
            "use the reference as a stable style floor while changing the composition and recognizable sounds."
        ),
    },
    "medium_low": {
        "id": "medium_low",
        "label": "Medium-low similarity",
        "target_similarity": 0.34,
        "ace_task_type": "cover",
        "audio_cover_strength": 0.18,
        "cover_noise_strength": 0.08,
        "bass_variation_amount": 0.64,
        "bass_pitch_lock": 0.23,
        "bass_rhythm_lock": 0.76,
        "vary_bass_notes": True,
        "variation_scope": (
            "take a new musical path with different bass notes, percussion answers, fills, and sound palette; "
            "keep it tonal, listenable, club-focused, and in the same genre, BPM, key area, and mood"
        ),
        "description": (
            "Fresh new track that keeps more of the reference pocket than low similarity, while still changing "
            "bass notes, percussion accents, and sound palette clearly."
        ),
    },
    "medium": {
        "id": "medium",
        "label": "Medium similarity",
        "target_similarity": 0.37,
        "ace_task_type": "cover",
        "audio_cover_strength": 0.19,
        "cover_noise_strength": 0.09,
        "bass_variation_amount": 0.58,
        "bass_pitch_lock": 0.25,
        "bass_rhythm_lock": 0.77,
        "vary_bass_notes": True,
        "variation_scope": (
            "make a clear original variation with a new bass note sequence, new secondary percussion answers, "
            "and a changed sound palette while preserving the same club lane, BPM, key area, mood, and pocket confidence"
        ),
        "description": (
            "Usable original variation: not a copy, but still visibly in the same musical lane and pocket."
        ),
    },
    "medium_high": {
        "id": "medium_high",
        "label": "Medium-high similarity",
        "target_similarity": 0.4,
        "ace_task_type": "cover",
        "audio_cover_strength": 0.2,
        "cover_noise_strength": 0.1,
        "bass_variation_amount": 0.55,
        "bass_pitch_lock": 0.28,
        "bass_rhythm_lock": 0.78,
        "vary_bass_notes": True,
        "variation_scope": (
            "calibrated medium-high anchor: keep the reference groove attitude and musical confidence, but make bass notes, "
            "secondary percussion, fills, and sound palette audibly different"
        ),
        "description": (
            "Close usable reference-inspired version calibrated from the accepted Callao medium-low result: "
            "same lane and mood, but clearly not the same bassline or sound palette."
        ),
    },
    "high": {
        "id": "high",
        "label": "High similarity",
        "target_similarity": 0.52,
        "ace_task_type": "cover",
        "audio_cover_strength": 0.28,
        "cover_noise_strength": 0.12,
        "bass_variation_amount": 0.42,
        "bass_pitch_lock": 0.36,
        "bass_rhythm_lock": 0.84,
        "vary_bass_notes": True,
        "variation_scope": (
            "stay closer than medium-high, but the bass pitch sequence, percussion answers, fills, samples, and "
            "effect timbres must still be audibly changed"
        ),
        "description": (
            "Strong reference anchor without collapsing into a copy: preserve tempo, key area, timing confidence, "
            "energy, and broad arrangement, but keep audible musical variation."
        ),
    },
    "very_high": {
        "id": "very_high",
        "label": "Very-high similarity",
        "target_similarity": 0.66,
        "ace_task_type": "cover",
        "audio_cover_strength": 0.46,
        "cover_noise_strength": 0.24,
        "bass_variation_amount": 0.24,
        "bass_pitch_lock": 0.48,
        "bass_rhythm_lock": 0.89,
        "vary_bass_notes": True,
        "variation_scope": (
            "reference-locked but not near-identical: keep the groove, tempo, hook placement, energy, and broad arrangement "
            "very close, while changing bass notes, vocal wording, sample identity, fills, and effect timbres enough to avoid a copy"
        ),
        "description": (
            "Between high and near-identical: strong source anchor with audible musical and sound-design changes."
        ),
    },
    "near_identical_twist": {
        "id": "near_identical_twist",
        "label": "Near-identical with twist",
        "target_similarity": 0.82,
        "ace_task_type": "cover",
        "audio_cover_strength": 0.72,
        "cover_noise_strength": 0.48,
        "bass_variation_amount": 0.08,
        "bass_pitch_lock": 0.68,
        "bass_rhythm_lock": 0.93,
        "vary_bass_notes": False,
        "variation_scope": (
            "keep the bass and drum behavior closest to the reference, but change the generated performance, "
            "samples, fills, effects, and small transition details enough to avoid a literal duplicate"
        ),
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
    vocals = analysis.get("vocals") or {}

    similarity_profile = _similarity_profile(text, analysis)
    bass_mode = _apply_profile_to_bass_mode(_bass_mode(text), similarity_profile)
    groove_similarity = _groove_similarity(text, analysis, bass_mode, similarity_profile)
    stab = _stab_replacement(text)
    style = _style_profile(analysis, text)
    harmonic = _harmonic_policy(style, analysis)
    reference_character = _reference_character(analysis, style)
    vocal_mode = _vocal_mode(vocals, groove_similarity, text)
    rich_reference = _rich_reference_policy(analysis, style, vocal_mode, groove_similarity)
    similarity_profile = _adapt_profile_for_rich_reference(similarity_profile, rich_reference, groove_similarity)
    prompt = _prompt(
        groove_similarity=groove_similarity,
        bass_mode=bass_mode,
        stab=stab,
        style=style,
        harmonic=harmonic,
        reference_character=reference_character,
        rich_reference=rich_reference,
        reference_groove=reference_groove,
        bass_transcription=bass_transcription,
        drums=drums,
        vocal_mode=vocal_mode,
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
        "harmonic": harmonic,
        "reference_character": reference_character,
        "rich_reference": rich_reference,
        "bass": bass_mode,
        "drums": {
            "keep_kick_rhythm": groove_similarity >= 0.78,
            "keep_hat_percussion_feel": groove_similarity >= 0.72,
            "source": "drum_stem" if (analysis.get("stem_separation") or {}).get("paths", {}).get("drums") else "full_mix_fingerprint",
        },
        "stab_replacement": stab,
        "vocals": vocal_mode,
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
    if re.search(r"\b(very high|very close|reference locked|between high and near identical)\b", text) or (
        allow_bare and text in {"very high", "very close", "reference locked"}
    ):
        return "very_high"
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
    preserve_sound = bool(
        re.search(r"\b(same|similar|keep|preserve)\b.{0,50}\b(bass sound|bass tone|bass timbre|bassline sound|low end sound)\b", text)
        or re.search(r"\b(bass sound|bass tone|bass timbre|bassline sound|low end sound)\b.{0,50}\b(same|similar|keep|preserve)\b", text)
    )
    exact_bass_rhythm = bool(
        re.search(r"\b(same|exact|keep|preserve)\b.{0,50}\b(bass line rhythm|bassline rhythm|bass rhythm|bass groove)\b", text)
        or re.search(r"\b(bass line rhythm|bassline rhythm|bass rhythm|bass groove)\b.{0,50}\b(same|exact|keep|preserve)\b", text)
    )
    return {
        "keep_rhythm": True,
        "keep_syncopation": True,
        "vary_notes": vary_notes,
        "vary_sound_design": not preserve_sound,
        "preserve_sound_design": preserve_sound,
        "sound_lock": 0.88 if preserve_sound else 0.35,
        "variation_amount": 0.16 if vary_notes and keep_groove else (0.22 if vary_notes else 0.12),
        "source_pitch_lock": 0.45 if vary_notes else 0.78,
        "source_rhythm_lock": 0.96 if exact_bass_rhythm else 0.92 if keep_groove else 0.84,
        "description": (
            "keep the exact reference bass rhythm, rests, syncopation, steady bass tone, and low-end attitude, but change only the pitch notes"
            if vary_notes and (keep_groove or exact_bass_rhythm) and preserve_sound
            else "keep the exact reference bass rhythm, rests, syncopation, and attitude, but change the pitch notes slightly"
            if vary_notes and keep_groove
            else "keep the reference bass rhythm and syncopation, but alter note choices and bass tone"
            if vary_notes
            else "preserve the reference bass rhythm, contour, and tone balance"
        ),
    }


def _apply_profile_to_bass_mode(bass_mode: dict, similarity_profile: dict | None) -> dict:
    if not similarity_profile:
        return bass_mode
    adjusted = dict(bass_mode)
    if similarity_profile.get("vary_bass_notes"):
        adjusted["vary_notes"] = True
    adjusted["variation_amount"] = max(
        float(adjusted.get("variation_amount") or 0.0),
        float(similarity_profile.get("bass_variation_amount") or 0.0),
    )
    if "bass_pitch_lock" in similarity_profile:
        adjusted["source_pitch_lock"] = float(similarity_profile["bass_pitch_lock"])
    if "bass_rhythm_lock" in similarity_profile:
        adjusted["source_rhythm_lock"] = float(similarity_profile["bass_rhythm_lock"])
    if similarity_profile.get("variation_scope"):
        adjusted["variation_scope"] = str(similarity_profile["variation_scope"])
    if adjusted.get("vary_notes"):
        if adjusted.get("preserve_sound_design"):
            adjusted["description"] = (
                "keep the bass rhythm, rests, syncopation, steady bass tone, envelope, and low-end role very close, "
                "but change the bass pitch notes according to the selected variation target"
            )
        else:
            adjusted["description"] = (
                "keep the bass rhythm, rests, syncopation, and low-end role, but change the bass pitch notes "
                f"according to the {similarity_profile.get('label', 'selected similarity')} target"
            )
    return adjusted


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
    if scaled.get("preserve_sound_design"):
        scaled["source_rhythm_lock"] = round(max(0.95, float(scaled.get("source_rhythm_lock") or 0.0)), 3)
        scaled["sound_lock"] = round(max(0.86, float(scaled.get("sound_lock") or 0.0)), 3)
        scaled["variation_amount"] = round(max(float(scaled.get("variation_amount") or 0.0), 0.22), 3)
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


def _style_profile(analysis: dict, user_prompt_text: str = "") -> dict:
    direction = " ".join([str(analysis.get("user_direction") or ""), user_prompt_text or ""]).strip()
    override = _style_override_from_user_direction(direction, analysis)
    if override:
        return override
    deep_genre = analysis.get("genre_deep") or {}
    genre = deep_genre if float(deep_genre.get("confidence") or 0.0) >= 0.12 else analysis.get("genre") or {}
    primary = str(genre.get("primary") or "").strip()
    if not primary or primary.lower().startswith("unknown"):
        primary = "reference-informed instrumental"
    tags = [str(tag) for tag in (genre.get("tags") or [])[:4] if str(tag).strip()]
    groove = analysis.get("groove") or {}
    groove_text = groove.get("description") or groove.get("feel") or "reference groove"
    bpm = analysis.get("bpm")
    key = _corrected_key_area(analysis)
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


def _style_override_from_user_direction(user_direction: str, analysis: dict) -> dict | None:
    text = " ".join((user_direction or "").lower().replace("/", " ").split())
    if not text:
        return None
    if re.search(r"\b(electro funk|electro-funk|dance pop|dance-pop|post disco|post-disco|80s|1980s)\b", text):
        tags = ["1980s electro-funk", "dance-pop", "post-disco", "club pop"]
        bpm = _number_or_none(analysis.get("bpm"))
        key = _corrected_key_area(analysis)
        brief_parts = [
            "1980s electro-funk / dance-pop",
            "tight 16th-note funk pocket",
            "staccato syncopated bass",
            "punchy snare/clap backbeat",
            "dramatic synth stabs and call-response hook energy",
        ]
        if bpm:
            brief_parts.append(f"around {round(bpm)} BPM")
        if key and str(key).lower() != "unknown":
            brief_parts.append(f"in the {key} key area")
        return {
            "primary": "1980s electro-funk / dance-pop",
            "tags": tags,
            "bpm": bpm,
            "key": key,
            "groove": "tight 16th-note electro-funk pocket with syncopated bass and punchy backbeat",
            "brief": "; ".join(brief_parts),
        }
    if re.search(r"\b(deep tech|minimal house|minimal tech|tech house|underground house|minimal deep tech)\b", text):
        tags = ["underground house", "minimal house", "deep tech", "tech house"]
        bpm = _number_or_none(analysis.get("bpm"))
        key = _corrected_key_area(analysis)
        brief_parts = [
            "underground minimal / deep tech house",
            "rolling club groove",
            "tight low-end pressure",
            "restrained percussive stabs",
        ]
        if bpm:
            brief_parts.append(f"around {round(bpm)} BPM")
        if key and str(key).lower() != "unknown":
            brief_parts.append(f"in the {key} key area")
        return {
            "primary": "underground minimal / deep tech house",
            "tags": tags,
            "bpm": bpm,
            "key": key,
            "groove": "rolling club groove with tight low-end pressure",
            "brief": "; ".join(brief_parts),
        }
    if re.search(r"\b(electro house|electronic house|club house|house club|house track|house music)\b", text) or (
        re.search(r"\belectronic\b", text) and re.search(r"\bhouse\b", text)
    ):
        tags = ["electro house", "electronic house", "club", "dance"]
        bpm = _number_or_none(analysis.get("bpm"))
        key = _corrected_key_area(analysis)
        brief_parts = [
            "electro house / electronic house",
            "clean four-four club groove",
            "memorable synth or vocal hook character",
            "confident bass and drums",
        ]
        if bpm:
            brief_parts.append(f"around {round(bpm)} BPM")
        if key and str(key).lower() != "unknown":
            brief_parts.append(f"in the {key} key area")
        return {
            "primary": "electro house / electronic house",
            "tags": tags,
            "bpm": bpm,
            "key": key,
            "groove": "clean four-four electronic house club groove",
            "brief": "; ".join(brief_parts),
        }
    return None


def _prompt(
    *,
    groove_similarity: float,
    bass_mode: dict,
    stab: dict,
    style: dict,
    harmonic: dict,
    reference_character: dict,
    rich_reference: dict,
    reference_groove: dict,
    bass_transcription: dict,
    drums: dict,
    vocal_mode: dict,
) -> str:
    style_brief = style.get("brief") or "the detected reference style"
    parts = [
        _similarity_instruction(groove_similarity),
        f"keep the same BPM, key area, groove attitude, and detected reference style: {style_brief}",
        reference_character["prompt"],
        harmonic["generation_rule"],
        bass_mode["description"],
        (
            "preserve signature rhythmic roles when present: micro-percussion answers, swung hat/shaker movement, "
            "short rhythmic vocal-like chops as percussive texture, and small call-response accent variations"
        ),
    ]
    profile_scope = _profile_variation_scope(groove_similarity, bass_mode)
    if profile_scope:
        parts.insert(3, profile_scope)
    if rich_reference.get("enabled"):
        parts.insert(4, rich_reference["generation_rule"])
    if bass_mode.get("vary_notes"):
        if groove_similarity < 0.4:
            parts.insert(3, "do not reuse the original bass pitch sequence; make a clearly different bassline while preserving the rhythmic role and pocket")
        elif groove_similarity < 0.75:
            parts.insert(3, "do not reuse the exact original bass pitch sequence; make a noticeable note variation while preserving timing feel")
        else:
            parts.insert(3, "do not reuse the exact original bass pitch sequence; make a small new note variation while preserving timing")
    if bass_mode.get("preserve_sound_design"):
        parts.insert(
            4,
            "bass lock: preserve the reference bassline rhythm, note lengths, rests, envelope, weight, and steady bass tone; "
            "change only the pitch notes; no glitch bass, no chopped/stuttered bass, no jumpy edits, no broken breakbeat bass behavior"
        )
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
    if vocal_mode["preserve_role"]:
        parts.append(vocal_mode["description"])
        if vocal_mode.get("render_mode") == "instrumental_hook_proxy":
            parts.append(
                "do not render lead singing in the local guide sample; avoid stretched vocal chops, warped formants, and squeezed transition artifacts"
            )
        else:
            parts.append("do not copy the original singer, lyric phrase, exact vocal rhythm, or exact melody signature")
        parts.append("make a new original track in the detected reference style, not a literal master recording duplicate")
    else:
        parts.append("make a new original instrumental in the detected reference style, not a literal master recording duplicate")
    return "; ".join(parts)


def _harmonic_policy(style: dict, analysis: dict) -> dict:
    key = str((style or {}).get("key") or _corrected_key_area(analysis) or (analysis or {}).get("key") or "").strip()
    if not key or key.lower() == "unknown":
        return {
            "key": "unknown",
            "strict_scale": False,
            "generation_rule": (
                "keep bass, vocal hook, synth melody, and chord stabs tonal, confident, and musically resolved; avoid random chromatic notes"
            ),
        }
    chord_confidence = float(((analysis or {}).get("chords") or {}).get("confidence") or 0.0)
    borrowed_rule = (
        "only use borrowed or chromatic chord tones when they are clearly resolved back into the detected key"
        if chord_confidence >= 0.72
        else "do not add borrowed or chromatic notes unless the reference analysis explicitly supports them"
    )
    return {
        "key": key,
        "strict_scale": True,
        "chord_confidence": chord_confidence,
        "generation_rule": (
            f"scale-aware harmonic guard: keep bass notes, vocal hook, synth melody, and chord stabs inside {key}; "
            f"{borrowed_rule}; keep the bassline confident and hooky while avoiding off-scale passing notes, clashing lead notes, and unresolved chromatic melody"
        ),
    }


def _corrected_key_area(analysis: dict) -> str:
    key = str((analysis or {}).get("key") or "").strip()
    chords = (analysis or {}).get("chords") or {}
    progression = [str(chord).strip() for chord in (chords.get("progression") or []) if str(chord).strip()]
    chord_confidence = float(chords.get("confidence") or 0.0)
    if not progression or chord_confidence < 0.65:
        return key
    root_counts: dict[str, int] = {}
    for chord in progression[:48]:
        match = re.match(r"([A-G](?:#|b)?)", chord)
        if not match:
            continue
        root = _normalize_root(match.group(1))
        root_counts[root] = root_counts.get(root, 0) + 1
    if not root_counts:
        return key
    dominant_root, dominant_count = max(root_counts.items(), key=lambda item: item[1])
    current_root_match = re.match(r"([A-G](?:#|b)?)", key)
    current_root = _normalize_root(current_root_match.group(1)) if current_root_match else ""
    if dominant_root != current_root and dominant_count >= max(5, len(progression[:48]) * 0.22):
        scale = "minor" if "minor" in key.lower() else "major" if "major" in key.lower() else "minor"
        return f"{dominant_root} {scale}"
    return key


def _normalize_root(root: str) -> str:
    flats = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
    return flats.get(root, root)


def _reference_character(analysis: dict, style: dict) -> dict:
    curve = (analysis or {}).get("energy_curve") or []
    energies = [float(point.get("energy") or 0.0) for point in curve if isinstance(point, dict)]
    avg_energy = sum(energies) / len(energies) if energies else 0.0
    peak_energy = max(energies) if energies else 0.0
    loudness = _number_or_none((analysis or {}).get("loudness"))
    spectral = (analysis or {}).get("spectral_features") or {}
    zcr = _number_or_none(spectral.get("zero_crossing_rate")) or 0.0
    groove = (analysis or {}).get("groove") or {}
    vocals = (analysis or {}).get("vocals") or {}

    energy_label = "high-energy" if avg_energy >= 0.24 or (loudness is not None and loudness > -12.0) else "medium-energy"
    drive_label = "driving" if peak_energy >= 0.5 else "steady"
    brightness = "bright/edgy" if zcr >= 0.12 else "controlled"
    groove_text = groove.get("description") or groove.get("feel") or (style or {}).get("groove") or "reference groove"
    vocal_text = (
        f"{vocals.get('role', 'vocal hook')} attitude"
        if (vocals or {}).get("present")
        else "instrumental hook attitude"
    )
    prompt = (
        f"reference character: {drive_label} {energy_label} club energy, {brightness} electronic texture, "
        f"{groove_text}, confident low-end pressure, and {vocal_text}"
    )
    return {
        "energy": energy_label,
        "drive": drive_label,
        "brightness": brightness,
        "groove": groove_text,
        "vocal_role": vocal_text,
        "prompt": prompt,
    }


def _rich_reference_policy(analysis: dict, style: dict, vocal_mode: dict, groove_similarity: float) -> dict:
    genre_text = " ".join(
        [
            str((style or {}).get("primary") or ""),
            " ".join(str(tag) for tag in ((style or {}).get("tags") or [])),
        ]
    ).lower()
    rich_style = bool(re.search(r"\b(pop|funk|rock|disco|soul|r&b|rnb|electro)\b", genre_text))
    vocal_rich = bool(vocal_mode.get("preserve_role"))
    chords = (analysis or {}).get("chords") or {}
    chord_values = [str(chord) for chord in (chords.get("progression") or []) if str(chord).strip()]
    harmonic_density = float(chords.get("confidence") or 0.0) >= 0.65 and len(set(chord_values[:32])) >= 4
    enabled = groove_similarity <= 0.35 and (vocal_rich or rich_style or harmonic_density)
    if not enabled:
        return {"enabled": False}
    reasons = []
    if vocal_rich:
        reasons.append(vocal_mode.get("role") or "vocal hook")
    if rich_style:
        reasons.append("dense melodic/electronic reference style")
    if harmonic_density:
        reasons.append("rich harmonic movement")
    return {
        "enabled": True,
        "reason": ", ".join(reasons) or "dense reference",
        "generation_rule": (
            "rich-reference proxy: build a complete clean proxy section with drums, bass, claps, hats, percussion fills, "
            "dramatic stabs, layered keys or comping, call-response hook energy, and optional stable new vocal phrases; "
            "preserve role balance and arrangement feel without copying lyrics, melody, singer identity, or the master recording"
        ),
    }


def _adapt_profile_for_rich_reference(similarity_profile: dict | None, rich_reference: dict, groove_similarity: float) -> dict | None:
    if not similarity_profile or not rich_reference.get("enabled") or groove_similarity > 0.35:
        return similarity_profile
    adjusted = dict(similarity_profile)
    if os.environ.get("PROMPT2MIDI_RICH_REFERENCE_COVER") == "1":
        adjusted["ace_task_type"] = "cover"
        adjusted["audio_cover_strength"] = max(float(adjusted.get("audio_cover_strength") or 0.0), 0.28)
        adjusted["cover_noise_strength"] = max(float(adjusted.get("cover_noise_strength") or 0.0), 0.14)
        adjusted["reference_mode"] = "source_conditioned_proxy"
        adjusted["variation_scope"] = (
            "rich close proxy: use source audio conditioning for groove, timing, section energy, and role balance, "
            "but generate new bass notes, new hook contour, new lyrics or vocal chops, new samples, and a complete arrangement; "
            "avoid copying the singer, melody, lyrics, and master recording"
        )
        adjusted["description"] = (
            str(adjusted.get("description") or "")
            + " Dense melodic/vocal reference uses source-conditioned proxy mode to retain feel while changing protected details."
        ).strip()
        return adjusted
    adjusted["ace_task_type"] = "text2music"
    adjusted["audio_cover_strength"] = 0.0
    adjusted["cover_noise_strength"] = 0.0
    adjusted["reference_mode"] = "analysis_text_only"
    adjusted["variation_scope"] = (
        "rich low-similarity reference: do not use source-audio cover conditioning; compose a clean new track from the analyzed "
        "tempo, key area, mood, energy, groove attitude, hook role, and harmonic character; avoid chopped-source artifacts, "
        "warped vocals, copied hooks, and unstable transition textures"
    )
    adjusted["description"] = (
        str(adjusted.get("description") or "")
        + " Dense melodic/vocal references use analysis-text conditioning at low similarity to avoid cover-mode artifacts."
    ).strip()
    return adjusted


def _vocal_mode(vocals: dict, groove_similarity: float, user_prompt_text: str = "") -> dict:
    present = bool((vocals or {}).get("present"))
    role = str((vocals or {}).get("role") or "none")
    if not present:
        return {
            "present": False,
            "preserve_role": False,
            "role": "none",
            "description": "instrumental focus unless short vocal texture naturally fits the style",
        }
    confidence = float((vocals or {}).get("confidence") or 0.0)
    available = bool((vocals or {}).get("available"))
    method = str((vocals or {}).get("method") or "")
    source_reliable = available and confidence >= 0.65 and method != "user_direction_hint"
    direct_vocal_blocked = bool(
        re.search(
            r"\b(no|avoid|without|disable|do not|don't)\b.{0,40}\b(vocal|voice|singing|lyrics|lyric|singer)\b",
            user_prompt_text or "",
        )
        or re.search(r"\b(vocal|voice|singing|lyrics|lyric|singer)\b.{0,30}\b(resynthesis|synthesis|re-synthesis)\b", user_prompt_text or "")
    )
    explicit_direct_vocal = not direct_vocal_blocked and bool(
        re.search(
            r"\b(lead vocal|main vocal|singer|singing|lyrics|lyric|full vocal|with vocals|include vocals)\b",
            user_prompt_text or "",
        )
    )
    if groove_similarity <= 0.35 and not (source_reliable or explicit_direct_vocal):
        return {
            "present": True,
            "preserve_role": True,
            "render_mode": "instrumental_hook_proxy",
            "role": role,
            "description": (
                f"preserve the reference's {role} function as a clean synth, keyboard, or short non-lyrical vocal-chop hook; "
                "keep the hook attitude but avoid lead singing, copied words, and unstable vocal resynthesis"
            ),
            "confidence": confidence,
            "source": vocals.get("source"),
        }
    if groove_similarity < 0.4:
        description = (
            f"preserve the reference's {role} role as a new vocal idea: new words, new voice, "
            "new melody contour, same energy and hook function"
        )
    elif groove_similarity < 0.75:
        description = (
            f"keep a {role} role with original lyrics and a changed melody contour while staying in the same mood"
        )
    else:
        description = (
            f"keep the {role} role close in placement and energy, but use original lyrics, voice, and melody variation"
        )
    return {
        "present": True,
        "preserve_role": True,
        "render_mode": "direct_vocal_hook",
        "role": role,
        "description": description,
        "confidence": confidence,
        "source": vocals.get("source"),
    }


def _profile_variation_scope(groove_similarity: float, bass_mode: dict) -> str:
    if bass_mode.get("variation_scope"):
        return str(bass_mode["variation_scope"])
    amount = float(bass_mode.get("variation_amount") or 0.0)
    if groove_similarity >= 0.92:
        return "near-identical twist: keep the core bass/drum behavior closest, but vary samples, fills, FX, and transition details"
    if amount >= 0.7:
        return "low similarity variation must be musical: new bass notes, new percussion accents, and new sounds, while staying tonal, genre-accurate, and club-usable"
    if amount >= 0.5:
        return "medium-low variation: change bass notes, percussion answers, fills, and sound palette, but keep the original genre, speed, key area, mood, and groove confidence"
    if amount >= 0.3:
        return "medium variation: clearly change bass notes and secondary percussion while preserving the reference pocket and role balance"
    if amount >= 0.1:
        return "close variation: make a small audible bass-note change plus new fills, drum samples, and effect timbres"
    return ""


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
