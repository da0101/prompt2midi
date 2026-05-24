#!/usr/bin/env python3
"""CLI bridge called by the local Node orchestrator."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys

from analysis.arrangement.full_arrangement import build_full_arrangement_package
from analysis.composition.composition import generate_inspired_loop
from analysis.core.beat_grid import analyze_beat_grid
from analysis.core.enhanced_analysis import better_bpm, better_key, estimate_groove, infer_genre
from analysis.core.external_analyzers import analyze_allin1_structure, analyze_essentia_descriptors
from analysis.core.feature_extraction import AnalysisError, analyze_wav
from analysis.detectors.chord_detection import detect_chords
from analysis.detectors.drum_analysis import analyze_drums, drum_pattern_to_midi_events
from analysis.detectors.genre_detection import detect_genre
from analysis.detectors.structure_analysis import analyze_structure
from analysis.detectors.vocal_analysis import analyze_vocal_role
from analysis.generation.audio_generation import generate_reference_sample
from analysis.generation.full_guide_audio import generate_full_arrangement_guide_audio
from analysis.midi.bass_transcription import transcribe_bassline
from analysis.midi.midi_extraction import write_note_events_midi, write_reference_sketch_midi
from analysis.midi.source_transcription import can_run_model_transcription, transcribe_with_model
from analysis.midi.stem_separation import separate_for_transcription
from analysis.reference.ace_preflight import build_ace_preflight
from analysis.reference.reference_groove import analyze_reference_groove
from analysis.reference.reference_transform import build_reference_transform


def run(
    audio_path: str,
    output_dir: str,
    user_prompt: str = "",
    similarity_level: str | None = None,
    fast_sample: bool = False,
) -> dict:
    _progress("feature extraction: reading audio and estimating BPM/key/energy")
    analysis = analyze_wav(audio_path)
    os.makedirs(output_dir, exist_ok=True)

    _progress("enhanced analysis: refining BPM, key, genre, groove")
    bpm_result = better_bpm(audio_path, analysis.get("bpm"), analysis.get("bpm_confidence"))
    if bpm_result["bpm"] is not None:
        analysis["bpm"] = bpm_result["bpm"]
        analysis["bpm_confidence"] = bpm_result["confidence"] or analysis.get("bpm_confidence")
        analysis["bpm_method"] = bpm_result["method"]

    key_result = better_key(audio_path, analysis.get("key"), analysis.get("key_confidence"))
    if key_result["key"] is not None:
        analysis["key"] = key_result["key"]
        analysis["key_confidence"] = key_result["confidence"] or analysis.get("key_confidence")
        analysis["key_method"] = key_result["method"]

    analysis["genre"] = infer_genre(analysis)
    analysis["groove"] = estimate_groove(analysis)

    _progress("external analysis: checking All-In-One and Essentia adapters")
    analysis["allin1"] = analyze_allin1_structure(audio_path, output_dir)
    analysis["essentia"] = analyze_essentia_descriptors(audio_path, output_dir)
    _apply_essentia_overrides(analysis)
    if (_number_or_none(analysis.get("duration_seconds")) or 0.0) >= 20.0 or os.environ.get("PROMPT2MIDI_FORCE_BEAT_GRID") == "1":
        _progress("beat grid: estimating independent beat/downbeat fallback")
        analysis["beat_grid"] = analyze_beat_grid(audio_path, analysis.get("bpm"))
    else:
        analysis["beat_grid"] = {
            "available": False,
            "method": "librosa_beat_track_downbeat_estimate",
            "warnings": ["Beat-grid fallback skipped for short analysis audio."],
        }

    _progress("deep analysis: detecting genre, chords, structure")
    analysis["genre_deep"] = detect_genre(audio_path, progress=_progress)
    if analysis["genre_deep"]["confidence"] > 0.12:
        analysis["genre"] = {
            "primary": analysis["genre_deep"]["primary"],
            "tags": analysis["genre_deep"]["tags"],
            "confidence": analysis["genre_deep"]["confidence"],
        }
    _progress("deep analysis: detecting chord progression")
    analysis["chords"] = detect_chords(audio_path, analysis.get("bpm") or 120.0)
    _progress("deep analysis: detecting arrangement structure")
    allin1_structure = (analysis.get("allin1") or {}).get("structure")
    analysis["structure"] = allin1_structure if allin1_structure else analyze_structure(audio_path, analysis.get("bpm") or 120.0)

    if user_prompt:
        analysis["user_direction"] = user_prompt
    if similarity_level:
        analysis["reference_similarity_level"] = similarity_level
    if fast_sample:
        return _run_fast_sample_lane(audio_path, output_dir, user_prompt, similarity_level, analysis)

    _progress("midi sketch: writing reference-sketch.mid from estimated BPM/key")
    sketch_path = write_reference_sketch_midi(
        os.path.join(output_dir, "reference-sketch.mid"),
        key=analysis.get("key") or "C major",
        bpm=analysis.get("bpm") or 120.0,
    )
    _progress("heuristic bass: tracking low-frequency full-mix fallback")
    bass = transcribe_bassline(audio_path, analysis.get("bpm"))
    _progress("reference groove: fingerprinting full-track kick and bass movement")
    analysis["reference_groove"] = analyze_reference_groove(audio_path, analysis.get("bpm"))
    midi_files = {"reference_sketch": sketch_path}
    midi_assets = [
        {
            "key": "reference_sketch",
            "path": sketch_path,
            "label": "Generated reference sketch",
            "kind": "generated_sketch",
            "is_transcription": False,
            "source_method": "estimated_bpm_key_pattern",
            "confidence": min(float(analysis.get("bpm_confidence") or 0), float(analysis.get("key_confidence") or 0)),
            "limitations": ["Generated from estimated BPM/key only; not transcribed from the track."],
        }
    ]

    stems = separate_for_transcription(audio_path, output_dir) if os.environ.get("PROMPT2MIDI_DISABLE_STEMS") != "1" else _skipped_stems()
    analysis["stem_separation"] = {
        "available": stems["available"],
        "method": stems["method"],
        "stems": sorted((stems.get("stems") or {}).keys()),
        "paths": stems.get("stems") or {},
        "warnings": stems["warnings"],
    }
    _progress("deep analysis: detecting vocal role from separated stem")
    analysis["vocals"] = analyze_vocal_role(stems)
    drum_stem = (stems.get("stems") or {}).get("drums")
    _progress("deep analysis: analyzing drum pattern from stem")
    analysis["drums"] = analyze_drums(drum_stem, analysis.get("bpm") or 120.0)
    drum_events = drum_pattern_to_midi_events(analysis["drums"], analysis.get("bpm") or 120.0)
    if drum_events:
        midi_files["source_drum_groove"] = write_note_events_midi(
            os.path.join(output_dir, "source-drum-groove.mid"),
            drum_events,
            bpm=analysis.get("bpm") or 120.0,
        )
        midi_assets.append(
            {
                "key": "source_drum_groove",
                "path": midi_files["source_drum_groove"],
                "label": "Stem-aware drum groove MIDI",
                "kind": "source_aware_transcription",
                "is_transcription": True,
                "source_method": f"{stems.get('method', 'stem_separation')}+{analysis['drums'].get('method', 'onset_detection')}",
                "confidence": 0.7,
                "note_count": len(drum_events),
                "limitations": [
                    "Drum MIDI is quantized from separated-drum onset bands and should be edited by ear.",
                    "Kick, snare, and hat labels are estimated from frequency bands.",
                ],
                "source_audio": drum_stem,
                "source_stem": "drums",
                "source_stage": "separated_stem",
            }
        )
    model = transcribe_with_model(audio_path, output_dir, analysis.get("bpm"), stems)
    for track in model["tracks"]:
        midi_files[track["key"]] = track["path"]
        midi_assets.append(
            {
                "key": track["key"],
                "path": track["path"],
                "label": track["label"],
                "kind": track.get("kind", "model_transcription"),
                "is_transcription": True,
                "source_method": track.get("source_method") or model["method"],
                "confidence": track["confidence"],
                "note_count": track["note_count"],
                "limitations": track["limitations"],
                "source_audio": track.get("source_audio"),
                "source_stem": track.get("source_stem"),
                "source_stage": track.get("source_stage", "full_mix"),
            }
        )

    if bass["events"]:
        midi_files["bass_transcription"] = write_note_events_midi(
            os.path.join(output_dir, "bass-transcription.mid"),
            bass["events"],
            bpm=analysis.get("bpm") or 120.0,
        )
        midi_assets.append(
            {
                "key": "bass_transcription",
                "path": midi_files["bass_transcription"],
                "label": "Experimental heuristic bass MIDI",
                "kind": "heuristic_transcription",
                "is_transcription": False,
                "source_method": "full_mix_low_frequency_tracking",
                "confidence": bass["confidence"],
                "note_count": len(bass["events"]),
                "limitations": bass["warnings"],
            }
        )

    export_files = _promote_exports(output_dir, midi_files, midi_assets)

    _progress("reference transform: building groove, bass, and sound-replacement controls")
    _attach_reference_transform_and_preflight(analysis, user_prompt)

    _progress("composition: generating inspired 32-bar loop")
    exports_dir = os.path.join(output_dir, "exports")
    os.makedirs(exports_dir, exist_ok=True)
    _write_ace_preflight(exports_dir, analysis)
    _progress("full arrangement: writing arrangement map, analysis report, and SUNO structure prompt")
    full_arrangement = build_full_arrangement_package(
        analysis=analysis,
        output_dir=exports_dir,
        user_prompt=user_prompt,
        similarity_level=similarity_level,
    )
    full_arrangement["guide_audio"] = generate_full_arrangement_guide_audio(
        reference_audio=audio_path,
        output_dir=exports_dir,
        analysis=analysis,
        full_arrangement=full_arrangement,
        user_prompt=user_prompt,
    )
    full_arrangement["paths"]["full_arrangement_guide_audio"] = full_arrangement["guide_audio"].get("path")
    composition, suno_prompt = generate_inspired_loop(
        analysis=analysis,
        output_dir=exports_dir,
        bars=32,
    )
    if os.environ.get("PROMPT2MIDI_SKIP_REFERENCE_SAMPLE") == "1":
        _progress("audio generation: short sample lane skipped because full Arrangement Lock guide is enabled")
        composition["audio"] = {
            "status": "skipped",
            "provider": "audio_generation",
            "sample": None,
            "reason": "Skipped short sample generation because PROMPT2MIDI_SKIP_REFERENCE_SAMPLE=1.",
        }
    else:
        sample_duration = _reference_sample_duration(analysis)
        _progress(f"audio generation: preparing {sample_duration:.1f}-second reference-inspired sample")
        composition["audio"] = generate_reference_sample(
            reference_audio=audio_path,
            output_dir=exports_dir,
            prompt=user_prompt or (suno_prompt or {}).get("text") or "",
            analysis=analysis,
            duration_seconds=sample_duration,
        )

    analysis["bass_transcription"] = {
        "event_count": len(bass["events"]),
        "confidence": bass["confidence"],
        "warnings": bass["warnings"],
        "method": "full_mix_low_frequency_tracking",
    }
    analysis["model_transcription"] = {
        "available": model["available"],
        "method": model["method"],
        "track_count": len(model["tracks"]),
        "warnings": model["warnings"],
    }
    return {
        "ok": True,
        "analysis": analysis,
        "composition": composition,
        "full_arrangement": full_arrangement,
        "suno_prompt": suno_prompt,
        "export_dir": os.path.abspath(exports_dir),
        "ace_preflight_file": os.path.abspath(os.path.join(exports_dir, "ace-preflight.json")),
        "midi_files": midi_files,
        "export_files": export_files,
        "midi_assets": midi_assets,
        "midi_notes": [
            "exports/midi/ contains the generated loop package: bass, drums, chords, melody, full_loop — original compositions inspired by the reference, not transcriptions.",
            "reference-sketch.mid is generated from estimated BPM/key only.",
            "model-transcription.mid is produced by Basic Pitch when the local engine is installed.",
            "source-bass-transcription.mid is produced from a separated bass stem when Demucs and Basic Pitch are installed.",
            "source-drum-groove.mid is produced from a separated drum stem when Demucs is installed.",
            "model-bass-transcription.mid is pitch-filtered model output, not source-separated bass.",
            "bass-transcription.mid is legacy experimental monophonic low-frequency tracking when present.",
        ],
    }


def _run_fast_sample_lane(
    audio_path: str,
    output_dir: str,
    user_prompt: str,
    similarity_level: str | None,
    analysis: dict,
) -> dict:
    _progress("fast sample lane: skipping stems, transcription, MIDI, composition, and full arrangement")
    exports_dir = os.path.join(output_dir, "exports")
    os.makedirs(exports_dir, exist_ok=True)
    analysis["fast_sample_lane"] = {
        "enabled": True,
        "skipped": ["stem_separation", "basic_pitch", "midi_exports", "composition_midi", "full_arrangement"],
    }
    analysis["stem_separation"] = {
        "available": False,
        "method": "fast_sample_skipped",
        "stems": [],
        "paths": {},
        "warnings": ["Skipped in fast sample lane."],
    }
    analysis["vocals"] = _prompt_vocal_hint(user_prompt)
    analysis["drums"] = {"method": "fast_sample_skipped", "warnings": ["Skipped in fast sample lane."]}
    analysis["model_transcription"] = {
        "available": False,
        "method": "fast_sample_skipped",
        "track_count": 0,
        "warnings": ["Skipped in fast sample lane."],
    }
    analysis["bass_transcription"] = {
        "event_count": 0,
        "confidence": 0.0,
        "warnings": ["Skipped in fast sample lane."],
        "method": "fast_sample_skipped",
    }
    _attach_reference_transform_and_preflight(analysis, user_prompt)
    preflight_path = _write_ace_preflight(exports_dir, analysis)
    sample_duration = _reference_sample_duration(analysis)
    _progress(f"fast sample lane: generating {sample_duration:.1f}-second ACE sample batch")
    audio = generate_reference_sample(
        reference_audio=audio_path,
        output_dir=exports_dir,
        prompt=user_prompt,
        analysis=analysis,
        duration_seconds=sample_duration,
    )
    analysis_path = os.path.join(exports_dir, "fast-analysis.json")
    with open(analysis_path, "w", encoding="utf-8") as handle:
        json.dump(analysis, handle, indent=2, sort_keys=True)

    return {
        "ok": True,
        "mode": "fast_sample",
        "analysis": analysis,
        "composition": {"audio": audio},
        "audio": audio,
        "export_dir": os.path.abspath(exports_dir),
        "analysis_file": os.path.abspath(analysis_path),
        "ace_preflight_file": os.path.abspath(preflight_path),
        "midi_files": {},
        "export_files": {},
        "midi_assets": [],
        "limitations": [
            "Fast sample lane is for ACE profile calibration only.",
            "It skips MIDI, stems, source transcription, and full arrangement artifacts.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run prompt2midi local analysis.")
    parser.add_argument("--audio", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--user-prompt", default="")
    parser.add_argument(
        "--similarity-level",
        choices=["low", "medium-low", "medium", "medium-high", "high", "very-high", "near-identical", "identical"],
        help="Named reference regeneration level. 'identical' is treated as near-identical with a twist.",
    )
    parser.add_argument(
        "--fast-sample",
        action="store_true",
        help="Skip MIDI, stems, transcription, composition, and full arrangement; generate only ACE sample candidates.",
    )
    args = parser.parse_args()

    try:
        level = "near_identical_twist" if args.similarity_level in ("near-identical", "identical") else args.similarity_level
        level = level.replace("-", "_") if level else level
        payload = run(
            args.audio,
            args.output_dir,
            user_prompt=args.user_prompt,
            similarity_level=level,
            fast_sample=args.fast_sample,
        )
    except AnalysisError as exc:
        payload = {"ok": False, "error": {"code": exc.code, "message": exc.message}}
    except Exception as exc:  # Defensive boundary for the Node bridge.
        payload = {"ok": False, "error": {"code": "analysis_failed", "message": str(exc)}}

    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True))
    sys.stdout.write("\n")
    return 0 if payload["ok"] else 2


def _skipped_stems() -> dict:
    _progress("stem separation: skipped because stems are disabled")
    return {
        "available": False,
        "method": "skipped",
        "stems": {},
        "warnings": ["Stem separation skipped because PROMPT2MIDI_DISABLE_STEMS is enabled."],
    }


def _attach_reference_transform_and_preflight(analysis: dict, user_prompt: str) -> None:
    transform = build_reference_transform(user_prompt, analysis)
    preflight = build_ace_preflight(analysis, transform, user_prompt)
    transform["ace_preflight"] = preflight
    analysis["reference_transform"] = transform
    analysis["ace_preflight"] = preflight


def _write_ace_preflight(exports_dir: str, analysis: dict) -> str:
    path = os.path.join(exports_dir, "ace-preflight.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(analysis.get("ace_preflight") or {}, handle, indent=2, sort_keys=True)
    return os.path.abspath(path)


def _prompt_vocal_hint(user_prompt: str) -> dict:
    text = " ".join((user_prompt or "").lower().replace("-", " ").split())
    vocal_blocked = bool(
        any(phrase in text for phrase in ("no vocal", "no vocals", "instrumental only"))
        or re.search(r"\b(no|avoid|without|disable|do not|don't)\b.{0,40}\b(vocal|voice|singing|lyrics|lyric|singer)\b", text)
        or re.search(r"\b(vocal|voice|singing|lyrics|lyric|singer)\b.{0,30}\b(resynthesis|synthesis|re synthesis)\b", text)
    )
    if not text or vocal_blocked:
        return {
            "available": False,
            "present": False,
            "role": "none",
            "confidence": 0.0,
            "warnings": ["Fast lane did not run stem-based vocal detection."],
        }
    conditional_only = any(
        phrase in text
        for phrase in (
            "if reference has vocals",
            "if the reference has vocals",
            "if vocals appear",
            "if vocal appears",
            "if the track has vocals",
        )
    )
    explicit_vocal_request = bool(
        re.search(
            r"\b(include|add|create|write|new|clear|lead|main|with)\b.{0,40}\b(vocal|voice|singing|lyrics|lyric)\b",
            text,
        )
        or re.search(r"\b(vocal hook|lead vocal|main vocal|with vocals|include vocals)\b", text)
    )
    if explicit_vocal_request and not conditional_only:
        return {
            "available": False,
            "present": True,
            "role": "lead vocal hook",
            "confidence": 0.55,
            "method": "user_direction_hint",
            "description": "Vocal role inferred from user direction in fast sample lane.",
            "generation_guidance": "include a clear new vocal hook with original words, new voice, and changed melody contour",
            "warnings": ["Fast lane inferred vocal role from the prompt because stem separation was skipped."],
        }
    return {
        "available": False,
        "present": False,
        "role": "none",
        "confidence": 0.0,
        "warnings": ["Fast lane did not run stem-based vocal detection; conditional vocal wording was not treated as proof of vocals."],
    }


def _apply_essentia_overrides(analysis: dict) -> None:
    essentia = analysis.get("essentia") or {}
    if not essentia.get("available"):
        return
    descriptors = essentia.get("descriptors") or {}
    rhythm = descriptors.get("rhythm") or {}
    tonal = descriptors.get("tonal") or {}
    producer = descriptors.get("producer_descriptors") or {}

    bpm = _number_or_none(rhythm.get("bpm"))
    if bpm and float(analysis.get("bpm_confidence") or 0) < 0.75:
        analysis["bpm"] = round(bpm, 2)
        analysis["bpm_confidence"] = 0.78
        analysis["bpm_method"] = "essentia_musicextractor"

    key_key = tonal.get("key_key")
    key_scale = tonal.get("key_scale")
    key_strength = tonal.get("key_strength")
    strength = _number_or_none(key_strength) or 0.0
    if key_key and key_scale and float(analysis.get("key_confidence") or 0) < strength:
        analysis["key"] = f"{key_key} {key_scale}"
        analysis["key_confidence"] = round(strength or 0.6, 2)
        analysis["key_method"] = "essentia_musicextractor"

    mix = descriptors.get("mix") or {}
    analysis["production_descriptors"] = {
        "brightness": producer.get("brightness"),
        "dancefloor_read": producer.get("dancefloor_read"),
        "dynamic_shape": producer.get("dynamic_shape"),
        "tonal_strength": producer.get("tonal_strength"),
        "average_loudness": mix.get("average_loudness"),
        "dynamic_complexity": mix.get("dynamic_complexity"),
    }


def _number_or_none(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _reference_sample_duration(analysis: dict) -> float:
    configured = str(os.environ.get("PROMPT2MIDI_REFERENCE_SAMPLE_DURATION") or "").strip().lower()
    source_duration = max(1.0, _number_or_none((analysis or {}).get("duration_seconds")) or 30.0)
    max_duration = _number_or_none(os.environ.get("PROMPT2MIDI_REFERENCE_SAMPLE_MAX_DURATION"))
    cap = max(10.0, max_duration) if max_duration else source_duration
    if configured in {"", "sample", "loop", "30", "30s"}:
        return min(30.0, cap)
    if configured in {"full", "reference", "track", "source"}:
        return min(source_duration, cap)
    try:
        return max(10.0, min(source_duration, cap, float(configured.rstrip("s"))))
    except ValueError:
        return min(30.0, cap)


def _promote_exports(output_dir: str, midi_files: dict, midi_assets: list[dict]) -> dict:
    exports_dir = os.path.join(output_dir, "exports")
    os.makedirs(exports_dir, exist_ok=True)
    export_files: dict[str, str] = {}
    has_source_bass = any(asset["key"] == "source_bass_transcription" for asset in midi_assets)

    for asset in midi_assets:
        key = asset["key"]
        export_name = _export_name(key, has_source_bass)
        block_reason = _midi_export_block_reason(asset)
        if export_name is None or block_reason:
            asset["is_recommended_output"] = False
            asset["debug_path"] = asset["path"]
            if block_reason:
                asset["review_required"] = True
                asset.setdefault("warnings", []).append(block_reason)
                asset.setdefault("limitations", []).append(block_reason)
            continue

        exported_path = os.path.abspath(os.path.join(exports_dir, export_name))
        shutil.copyfile(asset["path"], exported_path)
        asset["debug_path"] = asset["path"]
        asset["path"] = exported_path
        asset["is_recommended_output"] = True
        asset["export_name"] = export_name
        export_files[key] = exported_path
        midi_files[key] = exported_path

    return export_files


def _midi_export_block_reason(asset: dict) -> str | None:
    key = asset.get("key")
    confidence = float(asset.get("confidence") or 0.0)
    note_count = int(asset.get("note_count") or 0)
    source_method = str(asset.get("source_method") or "")
    if key == "model_transcription":
        return "Full-mix model transcription is debug-only until a MIDI quality report validates timing, density, register, and key fit."
    if key == "model_bass_transcription":
        return "Full-mix filtered bass MIDI is debug-only because it is not separated from drums, stabs, vocals, or low percussion."
    if key == "source_bass_transcription" and confidence < 0.68:
        return "Stem-aware bass MIDI did not pass the recommendation gate; keep as debug output until house-aware bass cleanup validates timing, register, and key fit."
    if key == "source_drum_groove" and "fallback" in source_method:
        return "Stem-aware drum MIDI used the dependency-free fallback and is for debugging only; install/run the stronger onset analyzer or house-aware drum mapper before recommending it."
    if key == "source_drum_groove" and note_count > 64:
        return "Stem-aware drum MIDI is too dense for a two-bar groove export and needs cleanup before recommendation."
    return None


def _export_name(key: str, has_source_bass: bool) -> str | None:
    if key == "source_bass_transcription":
        return "stem-bass.mid"
    if key == "source_drum_groove":
        return "stem-drums.mid"
    if key == "model_transcription":
        return "full-mix-model.mid"
    if key == "model_bass_transcription" and not has_source_bass:
        return "fallback-full-mix-bass.mid"
    return None


def _progress(message: str) -> None:
    print(f"progress: {message}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
