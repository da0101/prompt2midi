#!/usr/bin/env python3
"""ACE-Step suitability and routing heuristics for reference-guided generation."""
from __future__ import annotations

import re
import os


def build_ace_preflight(analysis: dict, reference_transform: dict, user_prompt: str = "") -> dict:
    """Predict whether ACE-Step is the right generator and choose hidden controls."""
    profile = (reference_transform or {}).get("similarity_profile") or {}
    style = (reference_transform or {}).get("style") or {}
    vocal = (reference_transform or {}).get("vocals") or {}
    harmonic = (reference_transform or {}).get("harmonic") or {}
    bass = (reference_transform or {}).get("bass") or {}
    genre = _genre_text(analysis, style)
    prompt = " ".join((user_prompt or "").lower().replace("-", " ").split())

    target_similarity = _float(
        profile.get("target_similarity"),
        _float((reference_transform or {}).get("groove_similarity"), 0.5),
    )
    score = 0.62
    strengths: list[str] = []
    risks: list[dict] = []

    bpm = _float((analysis or {}).get("bpm"), 0.0)
    bpm_confidence = _float((analysis or {}).get("bpm_confidence"), 0.0)
    if 118 <= bpm <= 132 and re.search(r"\b(house|tech|minimal|club|electronic|electro)\b", genre):
        score += 0.22
        strengths.append("stable club tempo and electronic/house lane")
    elif 105 <= bpm <= 140:
        score += 0.06
        strengths.append("usable tempo for reference conditioning")
    else:
        score -= 0.10
        risks.append(_risk("tempo_confidence", "tempo is outside the strongest ACE club-reference range", "medium"))

    if bpm_confidence and bpm_confidence < 0.45:
        score -= 0.08
        risks.append(_risk("weak_tempo_estimate", "BPM confidence is low, so groove-locking may be unstable", "medium"))

    rich_style = bool(re.search(r"\b(pop|funk|soul|r&b|rnb|rock|disco|jackson|electroclash)\b", genre))
    if rich_style:
        score -= 0.18
        risks.append(_risk("rich_melodic_style", "melodic/vocal style identity is stronger than a simple drum-bass groove", "medium"))

    vocal_present = bool(vocal.get("preserve_role") or ((analysis or {}).get("vocals") or {}).get("present"))
    prompt_direct_vocal = _prompt_direct_vocal(prompt)
    force_direct_vocal = os.environ.get("PROMPT2MIDI_ACE_STEP_FORCE_VOCALS") == "1"
    direct_vocal = (
        bool(vocal_present and vocal.get("render_mode") != "instrumental_hook_proxy")
        or prompt_direct_vocal
        or force_direct_vocal
    )
    if direct_vocal:
        score -= 0.22
        risks.append(_risk("lead_vocal_or_hook", "ACE often warps, copies, or destabilizes strong vocal hooks", "high"))
    elif vocal_present:
        score -= 0.10
        risks.append(_risk("vocal_proxy_needed", "vocal role should be represented as a stable hook/proxy, not literal resynthesis", "medium"))

    if _harmonic_density(analysis, harmonic) >= 0.7:
        score -= 0.14
        risks.append(_risk("dense_harmony", "rich chord movement increases off-scale notes and transition artifacts", "medium"))

    if target_similarity >= 0.78:
        score -= 0.10
        risks.append(_risk("copy_risk", "very high source conditioning can copy the reference too closely", "high"))
    elif 0.58 <= target_similarity < 0.78:
        strengths.append("close-reference request without near-identical copy pressure")

    if "runpod" in prompt or "yue" in prompt:
        score -= 0.05
        risks.append(_risk("user_prefers_yue", "user direction mentions YuE/RunPod as an alternate generator", "low"))

    score = round(max(0.0, min(1.0, score)), 3)
    suitability = _suitability_label(score)
    recommended_generator = _recommended_generator(score, risks)
    bass_lock_intent = bool(bass.get("preserve_sound_design") and bass.get("vary_notes"))
    hidden_controls = _hidden_controls(profile, target_similarity, score, risks, direct_vocal, bass_lock_intent)

    return {
        "version": 1,
        "ace_suitability": suitability,
        "score": score,
        "recommended_generator": recommended_generator,
        "recommended_mode": _recommended_mode(recommended_generator, hidden_controls),
        "risk_reasons": risks,
        "strengths": strengths,
        "hidden_controls": hidden_controls,
        "message": _message(suitability, recommended_generator, risks),
    }


def _hidden_controls(
    profile: dict,
    target_similarity: float,
    score: float,
    risks: list[dict],
    direct_vocal: bool,
    bass_lock_intent: bool = False,
) -> dict:
    reference_strength = _float(profile.get("audio_cover_strength"), _default_reference_strength(target_similarity))
    noise = _float(profile.get("cover_noise_strength"), _default_noise(target_similarity))
    profile_id = str(profile.get("id") or "custom")
    risk_codes = {str(risk.get("code")) for risk in risks}
    route = "source_conditioned_cover"
    force_rich_cover = os.environ.get("PROMPT2MIDI_RICH_REFERENCE_COVER") == "1"

    if bass_lock_intent:
        route = "source_conditioned_cover_bass_locked"
    elif score < 0.42 and ("lead_vocal_or_hook" in risk_codes or "rich_melodic_style" in risk_codes) and not force_rich_cover:
        route = "prefer_yue_runpod"
    elif score < 0.55 and target_similarity <= 0.4 and not force_rich_cover:
        route = "analysis_text_conditioned"
        reference_strength = 0.0
        noise = 0.0
    elif target_similarity >= 0.78 and "copy_risk" in risk_codes:
        route = "source_conditioned_cover_copy_risk"
    elif direct_vocal and target_similarity < 0.45:
        route = "source_conditioned_cover_with_new_vocal_hook"

    if bass_lock_intent:
        recommended_profile = "bass_rhythm_sound_locked_pitch_varied"
        recommended_similarity = max(0.68, min(target_similarity, 0.74))
        recommended_reference_strength = max(min(reference_strength, 0.56), 0.46)
        recommended_noise = max(min(noise, 0.28), 0.18)
    elif force_rich_cover:
        route = "source_conditioned_cover_rich_proxy"
        recommended_profile = profile_id
        recommended_similarity = max(target_similarity, 0.4)
        recommended_reference_strength = max(min(reference_strength, 0.48), 0.34)
        recommended_noise = max(min(noise, 0.28), 0.16)
    elif target_similarity >= 0.78 and "copy_risk" in risk_codes:
        recommended_profile = "very_high_reference_locked"
        recommended_similarity = 0.66
        recommended_reference_strength = min(reference_strength, 0.50)
        recommended_noise = min(noise, 0.28)
    else:
        recommended_profile = profile_id
        recommended_similarity = target_similarity
        recommended_reference_strength = reference_strength
        recommended_noise = noise

    if score < 0.42 and not bass_lock_intent:
        recommended_reference_strength = min(recommended_reference_strength, 0.32)
        recommended_noise = min(recommended_noise, 0.14)

    return {
        "route": route,
        "selected_profile": profile_id,
        "recommended_profile": recommended_profile,
        "target_similarity": round(target_similarity, 3),
        "recommended_similarity": round(recommended_similarity, 3),
        "reference_strength": round(max(0.0, min(1.0, recommended_reference_strength)), 3),
        "cover_noise_strength": round(max(0.0, min(1.0, recommended_noise)), 3),
        "vocal_mode": "new_vocal_hook" if direct_vocal else "instrumental_or_hook_proxy",
        "bass_lock_mode": "same_rhythm_same_sound_different_notes" if bass_lock_intent else "profile_default",
    }


def _default_reference_strength(similarity: float) -> float:
    if similarity >= 0.78:
        return 0.72
    if similarity >= 0.62:
        return 0.46
    if similarity >= 0.48:
        return 0.28
    if similarity >= 0.34:
        return 0.19
    return 0.21


def _default_noise(similarity: float) -> float:
    if similarity >= 0.78:
        return 0.48
    if similarity >= 0.62:
        return 0.24
    if similarity >= 0.48:
        return 0.12
    if similarity >= 0.34:
        return 0.09
    return 0.11


def _suitability_label(score: float) -> str:
    if score >= 0.72:
        return "high"
    if score >= 0.56:
        return "medium"
    if score >= 0.40:
        return "medium-low"
    return "low"


def _recommended_generator(score: float, risks: list[dict]) -> str:
    high_risk_codes = {str(risk.get("code")) for risk in risks if risk.get("severity") == "high"}
    if score < 0.42 and {"lead_vocal_or_hook", "copy_risk"} & high_risk_codes:
        return "yue_runpod"
    if score < 0.50:
        return "yue_runpod_or_prompt_only"
    return "ace_step"


def _recommended_mode(generator: str, controls: dict) -> str:
    if generator.startswith("yue"):
        return "runpod_yue_icl"
    return str(controls.get("route") or "source_conditioned_cover")


def _message(suitability: str, generator: str, risks: list[dict]) -> str:
    if generator == "ace_step" and suitability in {"high", "medium"}:
        return "ACE is a reasonable fit for this reference; audition all candidates."
    reasons = ", ".join(str(risk.get("label")) for risk in risks[:3]) or "reference complexity"
    if generator.startswith("yue"):
        return f"ACE may struggle because of {reasons}; use RunPod YuE for a stronger reference-inspired result."
    return f"ACE can be tested, but expect instability because of {reasons}."


def _harmonic_density(analysis: dict, harmonic: dict) -> float:
    chords = (analysis or {}).get("chords") or {}
    progression = [str(chord) for chord in (chords.get("progression") or []) if str(chord).strip()]
    if not progression:
        return 0.0
    unique = len(set(progression[:32]))
    confidence = _float(chords.get("confidence"), 0.0)
    density = min(1.0, unique / 7.0)
    if (harmonic or {}).get("strict_scale"):
        density = max(density, 0.45)
    return round((density * 0.65) + (confidence * 0.35), 3)


def _genre_text(analysis: dict, style: dict) -> str:
    parts = [
        str((style or {}).get("primary") or ""),
        " ".join(str(tag) for tag in ((style or {}).get("tags") or [])),
        str(((analysis or {}).get("genre") or {}).get("primary") or ""),
        " ".join(str(tag) for tag in (((analysis or {}).get("genre") or {}).get("tags") or [])),
        str(((analysis or {}).get("genre_deep") or {}).get("primary") or ""),
        " ".join(str(tag) for tag in (((analysis or {}).get("genre_deep") or {}).get("tags") or [])),
        str((analysis or {}).get("user_direction") or ""),
    ]
    return " ".join(parts).lower()


def _prompt_direct_vocal(prompt: str) -> bool:
    if not prompt:
        return False
    if re.search(r"\b(no|avoid|without|disable|do not|don't)\b.{0,40}\b(vocal|voice|singing|lyrics|lyric|singer)\b", prompt):
        return False
    return bool(re.search(r"\b(vocal|voice|singing|lyrics|lyric|singer|vocal hook)\b", prompt))


def _risk(code: str, label: str, severity: str) -> dict:
    return {"code": code, "label": label, "severity": severity}


def _float(value: object, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
