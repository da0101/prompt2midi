#!/usr/bin/env python3
"""ACE-Step REST client for reference-inspired 30-second music samples."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from audio_quality import score_audio_candidate
from reference_groove import score_groove_similarity
from traceability import append_generation_run, generation_trace_record, write_candidate_manifest


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
    candidate_count = candidates or int(os.environ.get("PROMPT2MIDI_ACE_STEP_CANDIDATES") or "3")
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
    _progress("ace-step: submitting reference-conditioned generation task")
    task_id = _submit_task(base_url, payload)
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
        "metadata": {
            "bpm": payload.get("bpm"),
            "key_scale": payload.get("key_scale"),
            "time_signature": payload.get("time_signature"),
            "instrumental": True,
            "task_type": payload.get("task_type"),
            "reference_similarity": payload.get("reference_similarity"),
            "difference_level": payload.get("difference_level"),
            "audio_cover_strength": payload.get("audio_cover_strength"),
            "cover_noise_strength": payload.get("cover_noise_strength"),
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
    key_scale = _key_scale(analysis)
    caption = _caption(prompt, analysis)
    transform = analysis.get("reference_transform") or {}
    groove_similarity = _groove_similarity(transform)
    task_type = os.environ.get("PROMPT2MIDI_ACE_STEP_TASK_TYPE") or _task_type(transform, groove_similarity)
    is_cover = task_type in {"cover", "cover-nofsq"}
    conditioning = _source_conditioning(transform, groove_similarity, is_cover)
    reference_path = os.path.abspath(reference_audio)
    return {
        "task_type": task_type,
        "prompt": caption,
        "lyrics": "[Instrumental]",
        "instrumental": True,
        "reference_audio_path": reference_path,
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
        "guidance_scale": float(os.environ.get("PROMPT2MIDI_ACE_STEP_GUIDANCE") or "7.0"),
        "lm_model_path": os.environ.get("PROMPT2MIDI_ACE_STEP_LM_MODEL") or "acestep-5Hz-lm-0.6B",
        "lm_backend": os.environ.get("PROMPT2MIDI_ACE_STEP_LM_BACKEND") or "mlx",
        "lm_temperature": float(os.environ.get("PROMPT2MIDI_ACE_STEP_LM_TEMPERATURE") or "0.72"),
        "lm_cfg_scale": float(os.environ.get("PROMPT2MIDI_ACE_STEP_LM_CFG") or "2.4"),
        "audio_cover_strength": float(
            os.environ.get("PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH") or conditioning["reference_strength"]
        ),
        "cover_noise_strength": float(
            os.environ.get("PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH") or conditioning["cover_noise_strength"]
        ),
        "lm_negative_prompt": (
            "atonal high pitched artifacts, alien glitches, sci-fi lasers, metallic chirps, "
            "cartoon toy instruments, chipmunk sounds, harsh squeals, random melodies, "
            "busy lead solo, lead vocals, lyrical singing, copied hook, distorted clipping, soft lounge house, "
            "pretty pop melody, weak kick, thin bass, exact original bass pitch sequence, "
            "copied bassline notes, original stab timbre, copied stab sample"
        ),
        "reference_similarity": groove_similarity,
        "difference_level": transform.get("difference_level"),
    }


def _caption(prompt: str, analysis: dict) -> str:
    user = " ".join((prompt or "").replace("\n", " ").split())
    genre = analysis.get("genre") or {}
    genre_tags = genre.get("tags") or []
    genre_text = ", ".join(str(tag) for tag in genre_tags[:4])
    groove = analysis.get("groove") or {}
    groove_text = groove.get("feel") or groove.get("label") or ""
    transform = analysis.get("reference_transform") or {}
    style = transform.get("style") or {}
    style_brief = transform.get("style_brief") or style.get("brief") or genre.get("primary") or "reference-informed instrumental"
    base = (user or f"original instrumental inspired by {style_brief}").rstrip(" .;")
    style_line = (
        "use the reference for tempo, groove pocket, energy, and arrangement feel"
        if user
        else f"original instrumental in the detected reference style: {style_brief}"
    )
    additions = [
        style_line,
        "same tempo and key area as the reference",
        "clear bassline groove",
        "tight rhythmic drums",
        "syncopated percussion feel",
        "defined low-end role",
        "short rhythmic stabs or accent hits when appropriate",
        "micro-percussion movement and short vocal-like rhythmic chops when they are part of the reference style",
        "professional conventional instrument timbres",
        "clean club mix, no lead vocal or lyrical singing, no lead solo, no alien glitch sounds",
    ]
    if genre_text:
        additions.insert(1, f"genre tags: {genre_text}")
    if groove_text:
        additions.insert(2, f"groove feel: {groove_text}")
    caption = f"{base}. " + ". ".join(additions)
    return _sentence_limited(caption, 1100)


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


def _task_type(transform: dict, groove_similarity: float) -> str:
    profile = transform.get("similarity_profile") or {}
    profile_task = profile.get("ace_task_type")
    if profile_task:
        return str(profile_task)
    bass = transform.get("bass") or {}
    if groove_similarity >= 0.96 and not bass.get("vary_notes"):
        return "cover"
    if groove_similarity >= 0.4:
        return "cover"
    return "text2music"


def _source_conditioning(transform: dict, groove_similarity: float, is_cover: bool) -> dict:
    profile = transform.get("similarity_profile") or {}
    if not is_cover:
        return {
            "reference_strength": str(round(float(profile.get("audio_cover_strength") or 0.0), 3)),
            "cover_noise_strength": "0.0",
        }

    if "audio_cover_strength" in profile or "cover_noise_strength" in profile:
        return {
            "reference_strength": str(round(max(0.0, min(1.0, float(profile.get("audio_cover_strength") or 0.0))), 3)),
            "cover_noise_strength": str(round(max(0.0, min(1.0, float(profile.get("cover_noise_strength") or 0.0))), 3)),
        }

    bass = transform.get("bass") or {}
    vary_notes = bool(bass.get("vary_notes"))
    variation = _lock_value(bass.get("variation_amount"), max(0.0, 1.0 - groove_similarity))

    if groove_similarity >= 0.96 and not vary_notes:
        reference_strength = 0.98
        cover_noise_strength = 0.96
    else:
        difference = max(0.0, 1.0 - groove_similarity, variation if vary_notes else 0.0)
        reference_strength = 0.46 + groove_similarity * 0.35 - difference * 0.15
        cover_noise_strength = 0.12 + max(0.0, groove_similarity - 0.75) * 0.9 - difference * 0.08

    return {
        "reference_strength": str(round(max(0.68, min(0.98, reference_strength)), 3)),
        "cover_noise_strength": str(round(max(0.14, min(0.96, cover_noise_strength)), 3)),
    }


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


def _key_scale(analysis: dict) -> str:
    key = str(analysis.get("key") or "").strip()
    if not key or key.lower() == "unknown":
        return ""
    parts = key.replace("minor", "Minor").replace("major", "Major").split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1]}"
    return key


def _health_check(base_url: str) -> None:
    try:
        _request_json("GET", f"{base_url}/health")
    except Exception as exc:
        raise RuntimeError(f"ACE-Step API is not reachable at {base_url}. Start it with `npm run ace-step:start`.") from exc


def _submit_task(base_url: str, payload: dict) -> str:
    reference_path = payload.pop("reference_audio_path", None)
    src_path = payload.pop("src_audio_path", None)
    files = {}
    if reference_path:
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
    target_similarity = _groove_similarity(analysis.get("reference_transform") or {})
    bpm = analysis.get("bpm")
    for index, item in enumerate(results, start=1):
        file_url = item.get("file") or item.get("audio") or item.get("path")
        if not file_url:
            continue
        url = file_url if str(file_url).startswith("http") else f"{base_url}{file_url}"
        output_path = os.path.abspath(os.path.join(output_dir, f"candidate-{index}.wav"))
        _download(url, output_path)
        quality = score_audio_candidate(output_path, target_duration=target_duration)
        similarity = score_groove_similarity(reference_groove, output_path, bpm) if reference_groove else {}
        if similarity:
            quality["reference_similarity"] = similarity
            quality["selection_score"] = _selection_score(
                quality_score=quality["score"],
                exact_similarity_score=similarity["score"],
                target_similarity=target_similarity,
            )
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
        key=lambda item: item["quality"].get("selection_score", item["quality"]["score"]),
    )


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
    parser = argparse.ArgumentParser(description="Generate a 30-second sample with ACE-Step.")
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
