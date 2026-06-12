#!/usr/bin/env python3
"""ACE-Step REST client for reference-inspired music samples."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import sys
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from analysis.core.audio_quality import score_audio_candidate
from analysis.generation.traceability import append_generation_run, generation_trace_record, write_candidate_manifest
from analysis.reference.key_intent import requested_target_key
from analysis.reference.reference_groove import score_groove_similarity


DEFAULT_BASE_URL = "http://127.0.0.1:8001"
DEFAULT_MODEL = "acestep-v15-turbo"
DEFAULT_DURATION_SECONDS = 30.0
DEFAULT_POLL_SECONDS = 5.0
DEFAULT_TIMEOUT_SECONDS = 1800.0


def generate_with_ace_step(
    reference_audio: str,
    output_dir: str,
    prompt: str,
    analysis: dict | None = None,
    duration_seconds: float = DEFAULT_DURATION_SECONDS,
    candidates: int | None = None,
) -> dict:
    if os.environ.get("PROMPT2MIDI_ENABLE_ACE_STEP") != "1":
        return _disabled(duration_seconds, "Set PROMPT2MIDI_ENABLE_ACE_STEP=1 and start the local ACE-Step API.")

    _require_file(reference_audio)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    base_url = (os.environ.get("PROMPT2MIDI_ACE_STEP_URL") or DEFAULT_BASE_URL).rstrip("/")
    model = os.environ.get("PROMPT2MIDI_ACE_STEP_MODEL") or DEFAULT_MODEL
    candidate_count = candidates or int(os.environ.get("PROMPT2MIDI_ACE_STEP_CANDIDATES") or "4")
    candidate_count = max(1, min(6, candidate_count))

    _health_check(base_url)
    payload = _build_payload(
        reference_audio=reference_audio,
        prompt=prompt,
        analysis=analysis or {},
        duration_seconds=duration_seconds,
        candidate_count=candidate_count,
        model=model,
    )
    effective_prompt_path = os.path.abspath(os.path.join(output_dir, "ace-effective-prompt.txt"))
    Path(effective_prompt_path).write_text(payload["prompt"] + "\n", encoding="utf-8")
    _progress(
        "ace-step: effective controls "
        f"task={payload.get('task_type')} "
        f"reference_guidance={payload.get('audio_cover_strength')} "
        f"audio_start_amount={payload.get('cover_noise_strength')} "
        f"requested_similarity={payload.get('requested_reference_similarity')} "
        f"effective_similarity={payload.get('reference_similarity')}"
    )
    _progress("ace-step: submitting reference-conditioned generation task")
    try:
        task_id = _submit_task(base_url, payload)
    except (TimeoutError, socket.timeout) as exc:
        raise TimeoutError(
            "Local generator timed out while accepting the generation request before a task id was returned. "
            "Try lower source guidance, restart the local generator, or increase PROMPT2MIDI_ACE_STEP_SUBMIT_TIMEOUT."
        ) from exc
    results = _poll_task(base_url, task_id)
    candidates_payload = _download_candidates(base_url, results, output_dir, duration_seconds, analysis or {})
    if not candidates_payload:
        raise RuntimeError("ACE-Step finished without returning downloadable audio.")

    selected, selected_by = _select_candidate_for_promotion(candidates_payload)
    suggested = _suggest_candidate(candidates_payload)
    sample_path = None
    if selected is not None:
        sample_path = os.path.abspath(os.path.join(output_dir, "sample.wav"))
        shutil.copyfile(selected["path"], sample_path)

    trace = generation_trace_record(
        reference_audio=reference_audio,
        output_dir=output_dir,
        provider="ace_step",
        model=model,
        prompt=payload["prompt"],
        payload=payload,
        analysis=analysis or {},
        candidates=candidates_payload,
        selected_candidate=selected,
        selected_by=selected_by,
        suggested_candidate=suggested,
    )
    manifest_path = write_candidate_manifest(output_dir, trace)
    append_generation_run(trace)

    return {
        "status": "succeeded",
        "sample": sample_path,
        "duration_seconds": duration_seconds,
        "provider": "ace_step",
        "model": model,
        "prompt": payload["prompt"],
        "effective_prompt": effective_prompt_path,
        "reference_audio": os.path.abspath(reference_audio),
        "task_id": task_id,
        "candidate_count": len(candidates_payload),
        "review_status": trace["status"],
        "candidate_manifest": manifest_path,
        "selected_candidate": selected["path"] if selected else None,
        "selected_by": selected_by,
        "suggested_candidate": suggested["path"] if suggested else None,
        "suggested_by": "quality_rank_only" if suggested else None,
        "quality": (selected or suggested or candidates_payload[0])["quality"],
        "candidates": candidates_payload,
        "ace_preflight": (analysis or {}).get("ace_preflight"),
        "metadata": {
            "bpm": payload.get("bpm"),
            "key_scale": payload.get("key_scale"),
            "time_signature": payload.get("time_signature"),
            "instrumental": payload.get("instrumental"),
            "task_type": payload.get("task_type"),
            "reference_similarity": payload.get("reference_similarity"),
            "requested_reference_similarity": payload.get("requested_reference_similarity"),
            "difference_level": payload.get("difference_level"),
            "audio_cover_strength": payload.get("audio_cover_strength"),
            "cover_noise_strength": payload.get("cover_noise_strength"),
            "ace_suitability": (analysis or {}).get("ace_preflight"),
        },
        "limitations": [
            "Reference-guided original variation; cover mode controls source conditioning but still requires listening review.",
            "All candidates should be auditioned; quality ranking is advisory and does not choose the final result.",
        ],
    }


def _disabled(duration_seconds: float, reason: str) -> dict:
    return {
        "status": "disabled",
        "sample": None,
        "duration_seconds": duration_seconds,
        "provider": "ace_step",
        "model": os.environ.get("PROMPT2MIDI_ACE_STEP_MODEL") or DEFAULT_MODEL,
        "limitations": [reason],
    }


def _build_payload(
    reference_audio: str,
    prompt: str,
    analysis: dict,
    duration_seconds: float,
    candidate_count: int,
    model: str,
) -> dict:
    bpm = _bpm(analysis)
    target_key = requested_target_key(prompt)
    key_scale = _key_scale(analysis, target_key=target_key)
    reconstruction_diagnostic = _reconstruction_diagnostic_enabled()
    transform = analysis.get("reference_transform") or {}
    requested_similarity = _groove_similarity(transform)
    base_effective_similarity = _effective_similarity(transform, requested_similarity)
    task_type = "cover" if reconstruction_diagnostic else (
        os.environ.get("PROMPT2MIDI_ACE_STEP_TASK_TYPE") or _task_type(transform, base_effective_similarity)
    )
    is_cover = task_type in {"cover", "cover-nofsq"}
    conditioning = _source_conditioning(transform, base_effective_similarity, is_cover)
    audio_cover_strength = float(
        os.environ.get("PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH")
        or ("1.0" if reconstruction_diagnostic else conditioning["reference_strength"])
    )
    cover_noise_strength = float(
        os.environ.get("PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH")
        or ("1.0" if reconstruction_diagnostic else conditioning["cover_noise_strength"])
    )
    diagnostic_intensity = _diagnostic_intensity(audio_cover_strength, cover_noise_strength)
    effective_similarity = diagnostic_intensity if reconstruction_diagnostic else base_effective_similarity
    caption = (
        _reconstruction_caption(prompt, analysis, diagnostic_intensity)
        if reconstruction_diagnostic
        else _caption(prompt, analysis)
    )
    reference_path = os.path.abspath(reference_audio)
    vocal = _vocal_transform(transform, analysis)
    direct_vocal = _uses_direct_vocal(vocal)
    instrumental = not direct_vocal
    # ACE-Step's own cover UI uploads the source clip as src_audio only.
    # Sending the same long WAV as both reference_audio and ctx_audio makes
    # /release_task much heavier and can time out before it returns a task id.
    reference_audio_path = None
    if is_cover and os.environ.get("PROMPT2MIDI_ACE_STEP_DUPLICATE_COVER_REFERENCE") == "1":
        reference_audio_path = reference_path
    seed_value = int(os.environ.get("PROMPT2MIDI_ACE_STEP_SEED") or "-1")
    return {
        "task_type": task_type,
        "prompt": caption,
        "lyrics": _lyrics_for_vocal(vocal),
        "instrumental": instrumental,
        "reference_audio_path": reference_audio_path,
        "src_audio_path": reference_path if is_cover else None,
        "audio_duration": float(duration_seconds),
        "duration": float(duration_seconds),
        "bpm": bpm,
        "key_scale": key_scale,
        "keyscale": key_scale,
        "time_signature": "4",
        "timesignature": "4",
        "model": model,
        "batch_size": candidate_count,
        "audio_format": "wav",
        "thinking": False if is_cover else os.environ.get("PROMPT2MIDI_ACE_STEP_THINKING", "1") != "0",
        "use_format": os.environ.get("PROMPT2MIDI_ACE_STEP_USE_FORMAT", "0") != "0",
        "use_cot_metas": os.environ.get("PROMPT2MIDI_ACE_STEP_COT_METAS", "0") != "0",
        "use_cot_caption": os.environ.get("PROMPT2MIDI_ACE_STEP_COT_CAPTION", "0") != "0",
        "use_cot_language": os.environ.get("PROMPT2MIDI_ACE_STEP_COT_LANGUAGE", "0") != "0",
        "inference_steps": int(os.environ.get("PROMPT2MIDI_ACE_STEP_STEPS") or "12"),
        "seed": seed_value,
        "use_random_seed": seed_value < 0,
        "guidance_scale": float(os.environ.get("PROMPT2MIDI_ACE_STEP_GUIDANCE") or "7.0"),
        "lm_model_path": os.environ.get("PROMPT2MIDI_ACE_STEP_LM_MODEL") or "acestep-5Hz-lm-0.6B",
        "lm_backend": os.environ.get("PROMPT2MIDI_ACE_STEP_LM_BACKEND") or "mlx",
        "lm_temperature": float(os.environ.get("PROMPT2MIDI_ACE_STEP_LM_TEMPERATURE") or "0.72"),
        "lm_cfg_scale": float(os.environ.get("PROMPT2MIDI_ACE_STEP_LM_CFG") or "2.4"),
        "audio_cover_strength": audio_cover_strength,
        "cover_noise_strength": cover_noise_strength,
        "lm_negative_prompt": _reconstruction_negative_prompt(vocal) if reconstruction_diagnostic else _negative_prompt(vocal),
        "reconstruction_diagnostic": reconstruction_diagnostic,
        "reference_similarity": effective_similarity,
        "requested_reference_similarity": requested_similarity,
        "difference_level": transform.get("difference_level"),
    }


def _reconstruction_diagnostic_enabled() -> bool:
    return os.environ.get("PROMPT2MIDI_ACE_STEP_RECONSTRUCTION_DIAGNOSTIC") == "1"


def _diagnostic_intensity(reference_strength: float, cover_noise_strength: float) -> float:
    return max(0.0, min(1.0, max(float(reference_strength or 0.0), float(cover_noise_strength or 0.0))))


def _reconstruction_caption(prompt: str, analysis: dict, intensity: float = 1.0) -> str:
    user = " ".join((prompt or "").replace("\n", " ").split())
    key = _key_scale(analysis)
    if intensity >= 0.92:
        base = (
            "local diagnostic reconstruction: use the source audio as the primary blueprint; "
            "match its groove, timing, arrangement shape, instrument balance, timbre family, dynamics, and mix energy as closely as ACE can"
        )
    elif intensity >= 0.55:
        base = (
            "strong source-guided diagnostic variation: keep the reference groove, timing, arrangement shape, instrument balance, "
            "timbre family, dynamics, and mix energy clearly recognizable, but do not make a literal reconstruction"
        )
    elif intensity >= 0.4:
        base = (
            "balanced source-guided diagnostic variation: use the reference as an audible anchor for groove, energy, and sound family, "
            "while changing performance details, fills, small melodic moves, and sound-design choices"
        )
    else:
        base = (
            "loose source-guided diagnostic variation: use the reference for broad tempo, energy, and attitude only, "
            "with a clearly new groove treatment and new sound-design details"
        )
    additions = [
        "do not reinterpret the reference as a new style brief",
        f"keep the same tempo and {key} key area",
    ]
    requested_layers = _explicit_layer_requests(user)
    if requested_layers:
        additions.insert(0, requested_layers)
    elif user and user.lower().strip(" .") not in {"same tempo and key area as the reference", "same tempo and key area as the reference."}:
        additions.insert(0, f"requested change: {_sentence_limited(user, 420)}")
    return _sentence_limited(". ".join([base] + additions), 1300)


def _caption(prompt: str, analysis: dict) -> str:
    user = " ".join((prompt or "").replace("\n", " ").split())
    genre = analysis.get("genre") or {}
    genre_tags = genre.get("tags") or []
    genre_text = ", ".join(str(tag) for tag in genre_tags[:4])
    groove = analysis.get("groove") or {}
    groove_text = groove.get("feel") or groove.get("label") or ""
    transform = analysis.get("reference_transform") or {}
    vocal = _vocal_transform(transform, analysis)
    target_key = requested_target_key(user)
    harmonic = _harmonic_transform(transform, analysis, target_key=target_key)
    harmonic_guard = _harmonic_guard_text(harmonic)
    character_guard = _reference_character_text(transform)
    style = transform.get("style") or {}
    style_brief = transform.get("style_brief") or style.get("brief") or genre.get("primary") or "reference-informed instrumental"
    direct_vocal = _uses_direct_vocal(vocal)
    track_kind = "track" if direct_vocal else "instrumental guide track"
    base = (user or f"original {track_kind} inspired by {style_brief}").rstrip(" .;")
    bass_guard = _bass_guard_text(transform)
    if ((transform or {}).get("bass") or {}).get("preserve_sound_design") and "bass lock:" not in base.lower():
        base = f"{bass_guard}. {base}"
    requested_layers = _explicit_layer_requests(user)
    style_line = (
        "use the reference for tempo, groove pocket, energy, and arrangement feel"
        if user
        else f"original {track_kind} in the detected reference style: {style_brief}"
    )
    if direct_vocal:
        end_guard = (
        f"clean club mix, new {vocal.get('role', 'vocal hook')} role with original words and voice, "
        "no copied vocal identity, no exact lyric phrase, no lead solo, no alien glitch sounds"
        )
    elif vocal.get("preserve_role"):
        end_guard = (
            f"clean club mix, translate the {vocal.get('role', 'vocal hook')} role into a stable synth/keyboard/non-lyrical chop hook, "
            "no lead vocal, no lyrical singing, no stretched vocal artifacts, no alien glitch sounds"
        )
    else:
        end_guard = "clean club mix, no lead vocal or lyrical singing, no lead solo, no alien glitch sounds"
    additions = [
        style_line,
        character_guard,
        harmonic_guard,
        f"same tempo as the reference, but use the requested target key area: {target_key}"
        if target_key
        else "same tempo and key area as the reference",
        bass_guard,
        "clear bassline groove",
        "tight rhythmic drums",
        "syncopated percussion feel",
        "defined low-end role",
        "short rhythmic stabs or accent hits when appropriate",
        "micro-percussion movement and short vocal-like rhythmic chops when they are part of the reference style",
        "professional conventional instrument timbres",
        end_guard,
    ]
    drum_priority = _drum_priority_text(analysis)
    if drum_priority:
        additions.insert(4, drum_priority)
    if direct_vocal:
        additions.insert(
            4,
            f"preserve the reference's role by creating a new {vocal.get('role', 'vocal hook')} with a new melody contour",
        )
    elif vocal.get("preserve_role"):
        additions.insert(
            4,
            f"preserve the reference's {vocal.get('role', 'vocal hook')} function as a clean instrumental hook proxy",
        )
    if genre_text:
        additions.insert(1, f"genre tags: {genre_text}")
    if groove_text:
        additions.insert(2, f"groove feel: {groove_text}")
    priority = []
    if requested_layers:
        priority.append(f"priority requested layers: {requested_layers}")
    if user:
        priority.append(f"user direction: {_sentence_limited(base, 760)}")
    else:
        priority.append(base)

    caption = ". ".join(priority + additions)
    return _sentence_limited(caption, 1300)


def _drum_priority_text(analysis: dict) -> str:
    drums = (analysis or {}).get("drums") or {}
    if drums.get("percussion_character") == "tribal_percussion":
        return (
            "priority drum layer: preserve dense tribal percussion as a main audible element: "
            "continuous conga/bongo/shaker/tambourine-style 16th-note movement over the house kick, "
            "not sparse generic hats"
        )
    return ""


def _explicit_layer_requests(prompt: str) -> str:
    text = " ".join((prompt or "").lower().replace("-", " ").split())
    if not text:
        return ""

    blocked_vocal_chops = re.search(
        r"\b(no|avoid|without|remove)\b.{0,32}\b(vocal\s+chops?|voice\s+chops?|chopped\s+vocals?)\b",
        text,
    )
    controls = []
    if re.search(r"\b(cow\s*bell|cowbell)\b", text):
        controls.append(
            "an audible dry cowbell percussion layer with short rhythmic accent hits or turnaround fills"
        )
    if not blocked_vocal_chops and re.search(r"\b(vocal\s+chops?|voice\s+chops?|chopped\s+vocals?)\b", text):
        controls.append(
            "short non-lyrical vocal chops used as rhythmic hook or percussion texture, not lead singing"
        )
    if re.search(
        r"\b(tribal\s+percussion|tribal\s+drums?|congas?|bongos?|hand\s+percussion|shakers?|tambourines?|clave|wood\s+hits?|toms?)\b",
        text,
    ):
        controls.append(
            "continuous loud fast tribal percussion as a main audible layer from first bar to last bar: "
            "dense 16th-note congas, bongos, shakers, tambourine, clave or wood hits, and toms over the house kick"
        )
    if not controls:
        return ""
    return "requested added layers: " + "; ".join(controls) + "; make these layers clearly audible in the mix"


def _vocal_transform(transform: dict, analysis: dict | None = None) -> dict:
    if os.environ.get("PROMPT2MIDI_ACE_STEP_FORCE_INSTRUMENTAL") == "1":
        return {}
    if os.environ.get("PROMPT2MIDI_ACE_STEP_FORCE_VOCALS") == "1":
        analysis_vocal = (analysis or {}).get("vocals") or {}
        role = analysis_vocal.get("role") or ((transform or {}).get("vocals") or {}).get("role") or "vocal hook"
        return {
            "present": True,
            "preserve_role": True,
            "render_mode": "direct_vocal_hook",
            "role": role if role != "none" else "vocal hook",
            "description": (
                "force a new original vocal hook: new words, new voice, changed melody contour, "
                "same reference attitude and placement"
            ),
            "confidence": analysis_vocal.get("confidence") or 0.0,
            "source": analysis_vocal.get("source") or "user_override",
        }
    vocal = (transform or {}).get("vocals") or {}
    if vocal.get("preserve_role"):
        return vocal
    analysis_vocal = (analysis or {}).get("vocals") or {}
    if analysis_vocal.get("present"):
        return {
            "preserve_role": True,
            "role": analysis_vocal.get("role") or "vocal hook",
        }
    return {}


def _uses_direct_vocal(vocal: dict) -> bool:
    return bool(vocal.get("preserve_role")) and vocal.get("render_mode") != "instrumental_hook_proxy"


def _harmonic_transform(transform: dict, analysis: dict | None = None, target_key: str | None = None) -> dict:
    if target_key:
        return {"key": target_key, "strict_scale": True, "target_key_override": True}
    harmonic = (transform or {}).get("harmonic") or {}
    if isinstance(harmonic, dict) and harmonic:
        return harmonic
    key = str((analysis or {}).get("key") or "").strip()
    if key and key.lower() != "unknown":
        return {"key": key, "strict_scale": True}
    return {"key": "unknown", "strict_scale": False}


def _harmonic_guard_text(harmonic: dict) -> str:
    key = harmonic.get("key")
    if harmonic.get("strict_scale") and key and str(key).lower() != "unknown":
        if harmonic.get("target_key_override"):
            return (
                f"global harmonic rule: transpose the musical material and keep bass notes, hook, synth melody, chord stabs, fills, risers, and effects tuned inside {key}; "
                "resolved borrowed or chromatic tones are allowed only when they support the requested target key area; "
                "do not keep the original reference bass roots or chord roots when they conflict with the target key; "
                "no out-of-tune instruments, clashing off-key notes, random chromatic wrong notes, or unresolved atonal artifacts"
            )
        return (
            f"global harmonic rule: keep bass notes, hook, synth melody, chord stabs, fills, risers, and effects tuned inside {key}; "
            "resolved borrowed or chromatic tones are allowed only when they fit the key area and reference harmony; "
            "no out-of-tune instruments, clashing off-key notes, random chromatic wrong notes, or unresolved atonal artifacts"
        )
    return (
        "global harmonic rule: keep bass, hook, synth melody, chord stabs, fills, risers, and effects tonal, resolved, and scale-aware; "
        "no out-of-tune instruments, clashing off-key notes, random chromatic wrong notes, or unresolved atonal artifacts"
    )


def _reference_character_text(transform: dict) -> str:
    character = (transform or {}).get("reference_character") or {}
    prompt = str(character.get("prompt") or "").strip()
    if not prompt:
        return "preserve the reference mood, energy, low-end confidence, and hook attitude"
    return prompt


def _bass_guard_text(transform: dict) -> str:
    bass = (transform or {}).get("bass") or {}
    if bass.get("preserve_sound_design"):
        return (
            "bass lock: keep the reference bassline rhythm, note lengths, rests, steady bass tone, envelope, and low-end weight; "
            "change only the bass pitch notes; no glitchy bass, choppy bass, stuttered bass, jumpy bass edits, or broken breakbeat bass"
        )
    return "steady non-glitchy bassline pocket with intentional note choices"


def _lyrics_for_vocal(vocal: dict) -> str:
    if not _uses_direct_vocal(vocal):
        return "[Instrumental]"
    role = str(vocal.get("role") or "vocal hook")
    if "lead" in role:
        return (
            "[Verse]\n"
            "new original short vocal phrases, confident electronic club attitude\n"
            "[Chorus]\n"
            "new memorable vocal hook, original words, new voice, changed melody"
        )
    return "[Vocal Hook]\nnew rhythmic vocal chops and short original phrases, no copied words"


def _negative_prompt(vocal: dict) -> str:
    common = (
        "atonal high pitched artifacts, alien glitches, sci-fi lasers, metallic chirps, "
        "cartoon toy instruments, chipmunk sounds, harsh squeals, random melodies, "
        "Christmas music, holiday music, sleigh bells, jingle bells, church bells, orchestral bells, glockenspiel melody, "
        "choir, carol, cinematic score, nursery rhyme, cheerful pop, cheesy festive melody, "
        "off-key bass notes, out-of-scale lead notes, unresolved chromatic melody, clashing wrong notes, "
        "dissonant random pitch, "
        "stretched vocal chops, warped vocal transitions, squeezed formants, smeared transition notes, "
        "busy lead solo, distorted clipping, soft lounge house, pretty pop melody, weak kick, thin bass, "
        "glitchy bass, choppy bass, stuttered bass, jumpy bass edits, broken breakbeat bass, random bass cuts, "
        "unusable experimental noises, non-musical output, exact original bass pitch sequence, copied bassline notes, "
        "original stab timbre, copied stab sample"
    )
    if _uses_direct_vocal(vocal):
        return (
            common
            + ", copied hook, copied lyrics, copied vocal identity, impersonation, off-key vocals, robotic alien voice"
        )
    return common + ", lead vocals, lyrical singing, copied hook, copied vocal identity"


def _reconstruction_negative_prompt(vocal: dict) -> str:
    common = (
        "atonal high pitched artifacts, alien glitches, sci-fi lasers, metallic chirps, "
        "cartoon toy instruments, chipmunk sounds, harsh squeals, random unrelated melodies, "
        "off-key bass notes, out-of-scale lead notes, unresolved chromatic melody, clashing wrong notes, "
        "dissonant random pitch, distorted clipping, weak kick, thin bass, unusable experimental noises, non-musical output"
    )
    if _uses_direct_vocal(vocal):
        return common + ", off-key vocals, robotic alien voice"
    return common


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


def _groove_similarity(transform: dict) -> float:
    try:
        return max(0.0, min(1.0, float(transform.get("groove_similarity") or 0.0)))
    except (TypeError, ValueError):
        return 0.0


def _effective_similarity(transform: dict, fallback: float | None = None) -> float:
    controls = (((transform or {}).get("ace_preflight") or {}).get("hidden_controls") or {})
    try:
        value = float(controls.get("recommended_similarity"))
    except (TypeError, ValueError):
        value = fallback if fallback is not None else _groove_similarity(transform)
    return max(0.0, min(1.0, float(value or 0.0)))


def _task_type(transform: dict, groove_similarity: float) -> str:
    if _is_full_arrangement_section(transform):
        return "cover"
    route = (((transform or {}).get("ace_preflight") or {}).get("hidden_controls") or {}).get("route")
    if route == "analysis_text_conditioned":
        return "text2music"
    profile = transform.get("similarity_profile") or {}
    profile_task = profile.get("ace_task_type")
    if profile_task:
        return str(profile_task)
    if profile:
        return "cover"
    bass = transform.get("bass") or {}
    if groove_similarity >= 0.96 and not bass.get("vary_notes"):
        return "cover"
    if groove_similarity >= 0.4:
        return "cover"
    return "text2music"


def _source_conditioning(transform: dict, groove_similarity: float, is_cover: bool) -> dict:
    profile = transform.get("similarity_profile") or {}
    controls = (((transform or {}).get("ace_preflight") or {}).get("hidden_controls") or {})
    env_reference_strength = os.environ.get("PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH")
    env_noise_strength = os.environ.get("PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH")
    if not is_cover:
        return {
            "reference_strength": str(round(float(env_reference_strength or controls.get("reference_strength") or profile.get("audio_cover_strength") or 0.0), 3)),
            "cover_noise_strength": str(round(float(env_noise_strength or controls.get("cover_noise_strength") or 0.0), 3)),
        }

    if controls and not (env_reference_strength or env_noise_strength):
        reference_strength = max(0.0, min(1.0, float(controls.get("reference_strength") or 0.0)))
        cover_noise_strength = max(0.0, min(1.0, float(controls.get("cover_noise_strength") or 0.0)))
        if _requires_percussion_preservation(transform):
            reference_strength = max(reference_strength, 0.48)
            cover_noise_strength = max(cover_noise_strength, 0.28)
        return {
            "reference_strength": str(round(reference_strength, 3)),
            "cover_noise_strength": str(round(cover_noise_strength, 3)),
        }

    if "audio_cover_strength" in profile or "cover_noise_strength" in profile:
        reference_strength = max(0.0, min(1.0, float(profile.get("audio_cover_strength") or 0.0)))
        cover_noise_strength = max(0.0, min(1.0, float(profile.get("cover_noise_strength") or 0.0)))
        if _requires_percussion_preservation(transform):
            reference_strength = max(reference_strength, 0.48)
            cover_noise_strength = max(cover_noise_strength, 0.28)
        if _rich_reference_safe_mode(transform, groove_similarity):
            reference_strength = max(reference_strength, 0.26)
            cover_noise_strength = max(cover_noise_strength, 0.1)
        return {
            "reference_strength": str(round(float(env_reference_strength or reference_strength), 3)),
            "cover_noise_strength": str(round(float(env_noise_strength or cover_noise_strength), 3)),
        }

    bass = transform.get("bass") or {}
    vary_notes = bool(bass.get("vary_notes"))
    variation = _lock_value(bass.get("variation_amount"), max(0.0, 1.0 - groove_similarity))

    if groove_similarity >= 0.96 and not vary_notes:
        reference_strength = 0.98
        cover_noise_strength = 0.96
    else:
        difference = max(0.0, 1.0 - groove_similarity, variation if vary_notes else 0.0)
        if groove_similarity < 0.4:
            reference_strength = 0.22 + groove_similarity * 0.18
            cover_noise_strength = 0.12 + groove_similarity * 0.15
        elif groove_similarity < 0.75:
            reference_strength = 0.18 + groove_similarity * 0.25 - difference * 0.04
            cover_noise_strength = 0.08 + groove_similarity * 0.16 - difference * 0.03
        else:
            reference_strength = 0.46 + groove_similarity * 0.35 - difference * 0.15
            cover_noise_strength = 0.12 + max(0.0, groove_similarity - 0.75) * 0.9 - difference * 0.08

    min_reference_strength = 0.2 if groove_similarity < 0.4 else 0.18 if groove_similarity < 0.75 else 0.55
    min_cover_noise_strength = 0.1 if groove_similarity < 0.4 else 0.07 if groove_similarity < 0.75 else 0.14

    return {
        "reference_strength": str(round(max(min_reference_strength, min(0.98, reference_strength)), 3)),
        "cover_noise_strength": str(round(max(min_cover_noise_strength, min(0.96, cover_noise_strength)), 3)),
    }


def _rich_reference_safe_mode(transform: dict, groove_similarity: float) -> bool:
    rich_reference = (transform or {}).get("rich_reference") or {}
    vocal = (transform or {}).get("vocals") or {}
    return bool(rich_reference.get("enabled")) or (
        groove_similarity <= 0.35 and vocal.get("render_mode") == "instrumental_hook_proxy"
    )


def _requires_percussion_preservation(transform: dict) -> bool:
    if _is_full_arrangement_section(transform):
        return False
    drums = (transform or {}).get("drums") or {}
    return drums.get("percussion_character") == "tribal_percussion"


def _is_full_arrangement_section(transform: dict) -> bool:
    generation_context = (transform or {}).get("full_arrangement_generation") or {}
    return generation_context.get("mode") == "section_inspired_stitch"


def _lock_value(value: object, fallback: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return max(0.0, min(1.0, fallback))


def _bpm(analysis: dict) -> int:
    try:
        value = float(analysis.get("bpm") or 124)
    except (TypeError, ValueError):
        value = 124.0
    return int(max(80, min(150, round(value))))


def _key_scale(analysis: dict, target_key: str | None = None) -> str:
    if target_key:
        key = target_key
    else:
        transform = analysis.get("reference_transform") or {}
        harmonic = (transform or {}).get("harmonic") or {}
        key = str(harmonic.get("key") or analysis.get("key") or "").strip()
    if not key or key.lower() == "unknown":
        return ""
    parts = key.replace("minor", "Minor").replace("major", "Major").split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1]}"
    return key


def _health_check(base_url: str) -> None:
    deadline = time.time() + float(os.environ.get("PROMPT2MIDI_ACE_STEP_HEALTH_TIMEOUT") or "90")
    timeout = float(os.environ.get("PROMPT2MIDI_ACE_STEP_HEALTH_HTTP_TIMEOUT") or "10")
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            request = urllib.request.Request(f"{base_url}/health", method="GET")
            with urllib.request.urlopen(request, timeout=timeout) as response:
                json.loads(response.read().decode("utf-8"))
            return
        except Exception as exc:
            last_error = exc
            time.sleep(3.0)
    raise RuntimeError(f"ACE-Step API is not reachable at {base_url}. Start it with `npm run ace-step:start`.") from last_error


def _submit_task(base_url: str, payload: dict) -> str:
    reference_path = payload.pop("reference_audio_path", None)
    src_path = payload.pop("src_audio_path", None)
    files = {}
    if reference_path and os.path.abspath(reference_path) != os.path.abspath(src_path or ""):
        files["reference_audio"] = reference_path
    if src_path:
        files["ctx_audio"] = src_path
    if files:
        response = _request_multipart_files("POST", f"{base_url}/release_task", payload, files)
    else:
        response = _request_json("POST", f"{base_url}/release_task", payload)
    data = response.get("data") or {}
    task_id = data.get("task_id")
    if not task_id:
        raise RuntimeError(f"ACE-Step did not return a task_id: {response}")
    return str(task_id)


def _poll_task(base_url: str, task_id: str) -> list[dict]:
    timeout = float(os.environ.get("PROMPT2MIDI_ACE_STEP_TIMEOUT") or DEFAULT_TIMEOUT_SECONDS)
    poll = float(os.environ.get("PROMPT2MIDI_ACE_STEP_POLL_SECONDS") or DEFAULT_POLL_SECONDS)
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = _request_json("POST", f"{base_url}/query_result", {"task_id_list": [task_id]})
        data = response.get("data") or []
        if data:
            status = data[0].get("status")
            result_raw = data[0].get("result")
            if status == 1 and result_raw:
                parsed = json.loads(result_raw) if isinstance(result_raw, str) else result_raw
                return parsed if isinstance(parsed, list) else [parsed]
            if status == 2:
                raise RuntimeError(f"ACE-Step generation failed: {result_raw or data[0]}")
        _progress(f"ace-step: waiting for task {task_id}")
        time.sleep(poll)
    raise TimeoutError(f"ACE-Step generation timed out after {timeout:.0f}s.")


def _download_candidates(base_url: str, results: list[dict], output_dir: str, target_duration: float, analysis: dict) -> list[dict]:
    candidates: list[dict] = []
    reference_groove = analysis.get("reference_groove") or {}
    transform = analysis.get("reference_transform") or {}
    target_similarity = _effective_similarity(transform, _groove_similarity(transform))
    bpm = analysis.get("bpm")
    for index, item in enumerate(results, start=1):
        file_url = item.get("file") or item.get("audio") or item.get("path")
        if not file_url:
            continue
        url = file_url if str(file_url).startswith("http") else f"{base_url}{file_url}"
        output_path = os.path.abspath(os.path.join(output_dir, f"candidate-{index}.wav"))
        _progress(f"ace-step: downloading candidate {index}")
        _download(url, output_path)
        _progress(f"ace-step: scoring candidate {index}")
        quality = score_audio_candidate(output_path, target_duration=target_duration)
        similarity = score_groove_similarity(reference_groove, output_path, bpm) if reference_groove else {}
        if similarity:
            quality["reference_similarity"] = similarity
            quality["selection_score"] = _selection_score(
                quality_score=quality["score"],
                exact_similarity_score=similarity["score"],
                target_similarity=target_similarity,
            )
        _apply_level_quality_gate(quality, target_similarity)
        candidates.append(
            {
                "path": output_path,
                "quality": quality,
                "seed": item.get("seed_value") or item.get("seed"),
                "metas": item.get("metas") or {},
            }
        )
    return candidates


def _select_candidate_for_promotion(candidates: list[dict]) -> tuple[dict | None, str]:
    preferred = os.environ.get("PROMPT2MIDI_ACE_STEP_SELECT_CANDIDATE")
    if preferred:
        try:
            index = int(preferred)
        except ValueError:
            index = 0
        if 1 <= index <= len(candidates):
            return candidates[index - 1], "manual_candidate_override"

    if os.environ.get("PROMPT2MIDI_ACE_STEP_AUTO_SELECT") != "1":
        return None, "awaiting_user_selection"

    return _suggest_candidate(candidates), "automatic_quality_score"


def _choose_candidate(candidates: list[dict]) -> tuple[dict, str]:
    selected, selected_by = _select_candidate_for_promotion(candidates)
    if selected is not None:
        return selected, selected_by
    return _suggest_candidate(candidates), "quality_rank_only"


def _suggest_candidate(candidates: list[dict]) -> dict:
    return max(
        candidates,
        key=_candidate_rank_key,
    )


def _candidate_rank_key(item: dict) -> tuple[int, float]:
    quality = item.get("quality") or {}
    gate = quality.get("level_gate") or {}
    gate_passed = 0 if gate.get("passed") is False else 1
    return gate_passed, float(quality.get("selection_score", quality.get("score", 0.0)) or 0.0)


def _selection_score(quality_score: float, exact_similarity_score: float, target_similarity: float) -> float:
    quality_score = max(0.0, min(1.0, float(quality_score or 0.0)))
    exact_similarity_score = max(0.0, min(1.0, float(exact_similarity_score or 0.0)))
    target_similarity = max(0.0, min(1.0, float(target_similarity or 0.0)))

    if target_similarity >= 0.75:
        return round(0.58 * quality_score + 0.42 * exact_similarity_score, 3)

    if target_similarity <= 0.35:
        originality_score = 1.0 - exact_similarity_score
        return round(0.72 * quality_score + 0.28 * originality_score, 3)

    target_fit = max(0.0, 1.0 - abs(exact_similarity_score - target_similarity) / 0.45)
    return round(0.70 * quality_score + 0.30 * target_fit, 3)


def _apply_level_quality_gate(quality: dict, target_similarity: float) -> dict:
    target_similarity = max(0.0, min(1.0, float(target_similarity or 0.0)))
    pulse = float(quality.get("pulse_score") or 0.0)
    timbre = float(quality.get("timbre_score") or 0.0)
    score = float(quality.get("score") or 0.0)
    warnings = quality.setdefault("warnings", [])
    failures: list[str] = []

    if target_similarity <= 0.35:
        if pulse < 0.50:
            failures.append("club pulse is too weak for low-similarity house output")
        if score < 0.68:
            failures.append("overall musical quality is below the low-similarity floor")
        if timbre < 0.50:
            failures.append("instrument/timbre stability is below the low-similarity floor")
    elif target_similarity <= 0.55:
        if pulse < 0.45:
            failures.append("club pulse is too weak for reference-inspired output")
        if score < 0.60:
            failures.append("overall musical quality is below the reference-inspired floor")

    quality["level_gate"] = {
        "passed": not failures,
        "target_similarity": round(target_similarity, 3),
        "failures": failures,
    }
    if failures:
        gate_warning = "Level quality gate failed: " + "; ".join(failures) + "."
        if gate_warning not in warnings:
            warnings.append(gate_warning)
    return quality


def _request_json(method: str, url: str, payload: dict | None = None) -> dict:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    api_key = os.environ.get("PROMPT2MIDI_ACE_STEP_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    timeout = float(os.environ.get("PROMPT2MIDI_ACE_STEP_HTTP_TIMEOUT") or "120")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ACE-Step API HTTP {exc.code}: {detail}") from exc


def _request_multipart(method: str, url: str, fields: dict, file_field: str, file_path: str) -> dict:
    return _request_multipart_files(method, url, fields, {file_field: file_path})


def _request_multipart_files(method: str, url: str, fields: dict, files: dict[str, str]) -> dict:
    boundary = f"prompt2midi-{uuid.uuid4().hex}"
    body_parts: list[bytes] = []
    for key, value in fields.items():
        if value is None:
            continue
        body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
        body_parts.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        if isinstance(value, bool):
            text = "true" if value else "false"
        else:
            text = str(value)
        body_parts.append(text.encode("utf-8"))
        body_parts.append(b"\r\n")

    for file_field, file_path in files.items():
        filename = os.path.basename(file_path)
        body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
        body_parts.append(
            f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        body_parts.append(b"Content-Type: audio/wav\r\n\r\n")
        with open(file_path, "rb") as handle:
            body_parts.append(handle.read())
        body_parts.append(b"\r\n")
    body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(body_parts)

    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    api_key = os.environ.get("PROMPT2MIDI_ACE_STEP_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    timeout = float(os.environ.get("PROMPT2MIDI_ACE_STEP_SUBMIT_TIMEOUT") or "3600")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ACE-Step API HTTP {exc.code}: {detail}") from exc


def _download(url: str, output_path: str) -> None:
    request = urllib.request.Request(url, method="GET")
    api_key = os.environ.get("PROMPT2MIDI_ACE_STEP_API_KEY")
    if api_key:
        request.add_header("Authorization", f"Bearer {api_key}")
    with urllib.request.urlopen(request, timeout=300) as response:
        data = response.read()
    with open(output_path, "wb") as handle:
        handle.write(data)


def _require_file(path: str) -> None:
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(f"Reference audio file not found: {path}")


def _progress(message: str) -> None:
    print(f"progress: {message}", file=sys.stderr, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a reference-inspired sample with ACE-Step.")
    parser.add_argument("--reference", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--prompt", default="")
    parser.add_argument("--analysis-json")
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION_SECONDS)
    args = parser.parse_args()
    analysis = {}
    if args.analysis_json:
        with open(args.analysis_json, "r", encoding="utf-8") as handle:
            analysis = json.load(handle)

    try:
        payload = {
            "ok": True,
            "audio": generate_with_ace_step(
                reference_audio=args.reference,
                output_dir=args.output_dir,
                prompt=args.prompt,
                analysis=analysis,
                duration_seconds=args.duration,
            ),
        }
    except Exception as exc:
        payload = {"ok": False, "error": {"code": "ace_step_failed", "message": str(exc)}}
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True))
    sys.stdout.write("\n")
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
