#!/usr/bin/env python3
"""Local trace records for generation runs and listening feedback."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_REGISTRY = REPO_ROOT / ".platform" / "work" / "generation-runs.jsonl"


def write_candidate_manifest(output_dir: str, record: dict) -> str:
    path = Path(output_dir) / "candidate-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path.resolve())


def append_generation_run(record: dict) -> str:
    RUN_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    with RUN_REGISTRY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return str(RUN_REGISTRY)


def generation_trace_record(
    *,
    reference_audio: str,
    output_dir: str,
    provider: str,
    model: str,
    prompt: str,
    payload: dict,
    analysis: dict,
    candidates: list[dict],
    selected_candidate: dict | None,
    selected_by: str,
    suggested_candidate: dict | None,
) -> dict:
    transform = analysis.get("reference_transform") or {}
    profile = transform.get("similarity_profile") or {}
    style = transform.get("style") or {}
    return {
        "schema_version": 1,
        "run_id": _run_id(reference_audio, output_dir, profile.get("id"), prompt),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reference_audio": os.path.abspath(reference_audio),
        "output_dir": os.path.abspath(output_dir),
        "provider": provider,
        "model": model,
        "status": "awaiting_user_selection" if selected_candidate is None else "selected",
        "selection_policy": selected_by,
        "similarity": {
            "level": profile.get("id"),
            "label": profile.get("label"),
            "target_similarity": profile.get("target_similarity"),
            "reference_similarity": payload.get("reference_similarity"),
            "difference_level": payload.get("difference_level"),
            "task_type": payload.get("task_type"),
            "audio_cover_strength": payload.get("audio_cover_strength"),
            "cover_noise_strength": payload.get("cover_noise_strength"),
        },
        "style": {
            "brief": transform.get("style_brief"),
            "primary": style.get("primary"),
            "bpm": analysis.get("bpm"),
            "key": analysis.get("key"),
        },
        "prompt": prompt,
        "candidate_count": len(candidates),
        "suggested_candidate": _candidate_ref(suggested_candidate),
        "selected_candidate": _candidate_ref(selected_candidate),
        "candidates": [_candidate_record(index, candidate) for index, candidate in enumerate(candidates, start=1)],
        "feedback": {
            "status": "pending",
            "user_pick": None,
            "accepted_for_level": None,
            "notes": "",
            "tags": [],
        },
    }


def _candidate_record(index: int, candidate: dict) -> dict:
    quality = candidate.get("quality") or {}
    return {
        "index": index,
        "path": candidate.get("path"),
        "seed": candidate.get("seed"),
        "quality": {
            "score": quality.get("score"),
            "selection_score": quality.get("selection_score"),
            "pulse_score": quality.get("pulse_score"),
            "timbre_score": quality.get("timbre_score"),
            "rms": quality.get("rms"),
            "peak": quality.get("peak"),
            "zero_crossing_rate": quality.get("zero_crossing_rate"),
            "level_gate": quality.get("level_gate"),
            "warnings": quality.get("warnings") or [],
        },
    }


def _candidate_ref(candidate: dict | None) -> dict | None:
    if not candidate:
        return None
    path = str(candidate.get("path") or "")
    index = None
    stem = Path(path).stem
    if stem.startswith("candidate-"):
        try:
            index = int(stem.split("-", 1)[1])
        except ValueError:
            index = None
    return {"index": index, "path": path}


def _run_id(reference_audio: str, output_dir: str, level: object, prompt: str) -> str:
    digest = hashlib.sha1(
        "|".join([os.path.abspath(reference_audio), os.path.abspath(output_dir), str(level or ""), prompt or ""]).encode(
            "utf-8"
        )
    ).hexdigest()
    return digest[:12]
