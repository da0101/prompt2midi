#!/usr/bin/env python3
"""Build a longer DJ arrangement by reusing existing generated stems.

The arranger is intentionally deterministic. It does not generate new audio;
it preserves the supplied Suno/ACE material and appends copied phrase blocks
from the same stems to create a longer underground-house arrangement.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

from analysis.core.feature_extraction import compute_energy_curve, estimate_tempo
from analysis.drums.drum_subseparation import separate_drum_elements


ROLE_ORDER = ("kick", "snare", "hihats", "toms", "cymbals", "drums", "percussion", "bass", "stabs", "synths", "fx", "other", "vocals")
PERCUSSION_ROLES = {"kick", "snare", "hihats", "cymbals", "toms", "drums", "percussion"}
BREAKDOWN_DRUM_MODES = {"tops", "none", "full", "half-tops", "half-full"}
VOCAL_TOKENS = ("vocal", "voice", "vox", "lead vocal")
FULL_MIX_TOKENS = ("full", "mix", "master", "song", "candidate", "proxy")


@dataclass(frozen=True)
class StemAudio:
    role: str
    source_name: str
    path: str
    samples: np.ndarray
    sample_rate: int

    @property
    def duration_seconds(self) -> float:
        return len(self.samples) / float(self.sample_rate)


@dataclass(frozen=True)
class PhraseBlock:
    start: int
    end: int
    start_seconds: float
    end_seconds: float
    role_energy: dict[str, float]
    role_spectrum: dict[str, dict[str, float]]
    total_energy: float


def arrange_continuation(
    input_dir: str,
    output_dir: str,
    target_duration: float = 360.0,
    continue_from: str | float = "auto",
    bpm: float | None = None,
    phrase_bars: int = 16,
    include_vocals: bool = False,
    blueprint_audio: str | None = None,
    intro_bars: int | None = None,
    source_intro_bars: int = 0,
    prepend_intro_bars: int = 0,
    source_end_trim_bars: int = 0,
    breakdown_bars: int | None = None,
    breakdown_drum_mode: str = "tops",
    outro_bars: int | None = None,
    blueprint_breakdown_bars: int = 16,
    blueprint_outro_bars: int = 16,
    drum_substems: bool = False,
    arrangement_mode: str = "blueprint",
    transition_grid_bars: int = 16,
    pre_break_groove_bars: int = 32,
    post_drop_groove_bars: int = 48,
    second_half_extra_bars: int = 0,
    preserve_source_bars: int | None = None,
    preserve_source_start_bars: int = 0,
    pre_break_source_start_bars: int | None = None,
    pre_break_source_bars: int = 16,
    breakdown_source_start_bars: int | None = None,
    breakdown_source_bars: int = 16,
    post_drop_source_start_bars: int | None = None,
    post_drop_source_bars: int | None = None,
    percussion_reference_input_dir: str | None = None,
) -> dict:
    source = Path(input_dir)
    if not source.exists():
        raise FileNotFoundError(f"Input stem folder not found: {input_dir}")

    out = Path(output_dir)
    arranged_stem_dir = out / "arranged-stems"
    percussion_reference_dir = out / "percussion-reference-stems"
    arranged_stem_dir.mkdir(parents=True, exist_ok=True)

    stems, ignored = load_stems(str(source), include_vocals=include_vocals)
    if not stems:
        raise RuntimeError("No usable WAV stems found. Export WAV stems from Suno and place them in the input folder.")
    drum_subseparation = None
    drum_reference_stems: list[StemAudio] = []
    percussion_reference_ignored: list[dict] = []
    if drum_substems:
        drum_reference_stems, drum_subseparation = load_drum_reference_substems(stems, out / "drum-substems-source")
    if percussion_reference_input_dir:
        explicit_reference_stems, percussion_reference_ignored = load_percussion_reference_stems(percussion_reference_input_dir)
        if explicit_reference_stems:
            drum_reference_stems = explicit_reference_stems

    sample_rate = stems[0].sample_rate
    original_samples = min(len(stem.samples) for stem in stems)
    original_duration = original_samples / sample_rate
    bpm = float(bpm or estimate_bpm_from_stems(stems) or 128.0)
    bar_samples = max(1, int(round(sample_rate * 60.0 / bpm * 4.0)))
    phrase_samples = max(bar_samples, bar_samples * max(1, int(phrase_bars)))
    target_samples = max(original_samples, int(round(target_duration * sample_rate)))
    if arrangement_mode in {"suno-blocks", "prebreak-diagnostic", "club-second-half", "reference-blueprint"} and target_samples > original_samples:
        target_samples = max(original_samples, int(math.ceil(target_samples / bar_samples)) * bar_samples)
    if intro_bars is not None:
        if source_intro_bars < 0:
            raise ValueError("source_intro_bars must be >= 0.")
        prepend_intro_bars = max(0, int(intro_bars) - int(source_intro_bars))
    if breakdown_bars is not None:
        blueprint_breakdown_bars = int(breakdown_bars)
        breakdown_source_bars = int(breakdown_bars)
    breakdown_drum_mode = normalize_breakdown_drum_mode(breakdown_drum_mode)
    if outro_bars is not None:
        blueprint_outro_bars = int(outro_bars)
    effective_post_drop_groove_bars = int(post_drop_groove_bars) + int(second_half_extra_bars)
    if arrangement_mode in {"suno-blocks", "prebreak-diagnostic", "club-second-half", "reference-blueprint"}:
        validate_bar_locked_house_args(
            phrase_bars=phrase_bars,
            intro_bars=intro_bars,
            source_intro_bars=source_intro_bars,
            prepend_intro_bars=prepend_intro_bars,
            preserve_source_bars=preserve_source_bars,
            preserve_source_start_bars=preserve_source_start_bars,
            transition_grid_bars=transition_grid_bars,
            pre_break_groove_bars=pre_break_groove_bars,
            post_drop_groove_bars=post_drop_groove_bars,
            second_half_extra_bars=second_half_extra_bars,
            effective_post_drop_groove_bars=effective_post_drop_groove_bars,
            pre_break_source_start_bars=pre_break_source_start_bars,
            pre_break_source_bars=pre_break_source_bars,
            breakdown_source_start_bars=breakdown_source_start_bars,
            breakdown_source_bars=breakdown_source_bars,
            post_drop_source_start_bars=post_drop_source_start_bars,
            post_drop_source_bars=post_drop_source_bars,
            blueprint_breakdown_bars=blueprint_breakdown_bars,
            blueprint_outro_bars=blueprint_outro_bars,
        )
    if preserve_source_bars is not None:
        preserve_samples = bars_to_samples_checked(
            preserve_source_bars,
            bar_samples,
            original_samples,
            label="preserve_source_bars",
        )
    else:
        preserve_samples = resolve_continue_from(continue_from, original_samples, sample_rate, bar_samples)
        if source_end_trim_bars > 0:
            preserve_samples -= int(source_end_trim_bars * bar_samples)
            preserve_samples = int(round(preserve_samples / bar_samples) * bar_samples)
    preserve_source_start_samples = bars_to_samples_checked(
        int(preserve_source_start_bars),
        bar_samples,
        original_samples,
        label="preserve_source_start_bars",
    )
    if preserve_source_start_samples + preserve_samples > original_samples:
        max_preserve_bars = max(0, (original_samples - preserve_source_start_samples) // bar_samples)
        raise ValueError(
            f"preserve_source_start_bars={preserve_source_start_bars} plus preserve_source_bars/continue_from "
            f"exceeds source length; max preserve_source_bars from this start is {max_preserve_bars}."
        )
    preserve_samples = min(preserve_samples, original_samples)
    preserve_samples = max(0, preserve_samples)

    blocks = analyze_phrase_blocks(stems, original_samples, phrase_samples)
    selections = select_blocks(blocks, stems)
    prepend_intro_samples = max(0, int(prepend_intro_bars * bar_samples))
    arranged_base_samples = prepend_intro_samples + preserve_samples
    role_outputs: dict[str, np.ndarray] = {}
    if arrangement_mode == "prebreak-diagnostic":
        section_plan, blueprint = build_prebreak_diagnostic_plan(
            stems=stems,
            arranged_base_samples=arranged_base_samples,
            sample_rate=sample_rate,
            bar_samples=bar_samples,
            original_samples=original_samples,
            selections=selections,
            pre_break_repeat_bars=pre_break_groove_bars,
            pre_break_source_start_bars=pre_break_source_start_bars,
            pre_break_source_bars=pre_break_source_bars,
            breakdown_source_start_bars=breakdown_source_start_bars,
            breakdown_source_bars=breakdown_source_bars,
            breakdown_drum_mode=breakdown_drum_mode,
        )
        target_samples = arranged_base_samples + sum(int(section["duration"]) for section in section_plan)
    elif arrangement_mode == "club-second-half":
        section_plan, blueprint = build_club_second_half_plan(
            stems=stems,
            arranged_base_samples=arranged_base_samples,
            sample_rate=sample_rate,
            bar_samples=bar_samples,
            original_samples=original_samples,
            selections=selections,
            transition_grid_bars=transition_grid_bars,
            pre_break_repeat_bars=pre_break_groove_bars,
            pre_break_source_start_bars=pre_break_source_start_bars,
            pre_break_source_bars=pre_break_source_bars,
            breakdown_source_start_bars=breakdown_source_start_bars,
            breakdown_source_bars=breakdown_source_bars,
            breakdown_drum_mode=breakdown_drum_mode,
            post_drop_repeat_bars=effective_post_drop_groove_bars,
            post_drop_source_start_bars=post_drop_source_start_bars,
            post_drop_source_bars=post_drop_source_bars,
            outro_bars=blueprint_outro_bars,
        )
        target_samples = arranged_base_samples + sum(int(section["duration"]) for section in section_plan)
    elif arrangement_mode == "reference-blueprint":
        if not blueprint_audio:
            raise ValueError("reference-blueprint mode requires --blueprint-audio pointing at the original/reference arrangement.")
        section_plan, blueprint = build_reference_blueprint_plan(
            stems=stems,
            blueprint_audio=blueprint_audio,
            arranged_base_samples=arranged_base_samples,
            target_samples=target_samples,
            sample_rate=sample_rate,
            bar_samples=bar_samples,
            original_samples=original_samples,
            selections=selections,
            transition_grid_bars=transition_grid_bars,
            breakdown_drum_mode=breakdown_drum_mode,
            outro_bars=blueprint_outro_bars,
        )
    elif arrangement_mode == "suno-blocks":
        section_plan, blueprint = build_suno_block_sequence_plan(
            arranged_base_samples=arranged_base_samples,
            target_samples=target_samples,
            sample_rate=sample_rate,
            selections=selections,
            bar_samples=bar_samples,
            pre_break_bars=pre_break_groove_bars,
            breakdown_bars=blueprint_breakdown_bars,
            outro_bars=blueprint_outro_bars,
            blueprint_audio=blueprint_audio,
        )
    elif blueprint_audio:
        section_plan, blueprint = build_blueprint_section_plan(
            blueprint_audio=blueprint_audio,
            preserve_samples=preserve_samples,
            arranged_base_samples=arranged_base_samples,
            target_samples=target_samples,
            sample_rate=sample_rate,
            phrase_samples=phrase_samples,
            selections=selections,
            stems=stems,
            bar_samples=bar_samples,
            breakdown_bars=blueprint_breakdown_bars,
            outro_bars=blueprint_outro_bars,
        )
    else:
        section_plan = build_section_plan(
            preserve_samples=preserve_samples,
            target_samples=target_samples,
            sample_rate=sample_rate,
            selections=selections,
            stems=stems,
        )
        blueprint = None

    for stem in stems:
        arranged = render_arranged_stem(
            stem=stem,
            selections=selections,
            section_plan=section_plan,
            target_samples=target_samples,
            prepend_intro_samples=prepend_intro_samples,
            preserve_source_start_samples=preserve_source_start_samples,
            preserve_samples=preserve_samples,
        )
        role_outputs[stem.role] = arranged
        write_wav(arranged_stem_dir / f"{stem.role}.wav", sample_rate, arranged)

    percussion_reference_outputs: dict[str, str] = {}
    if drum_reference_stems:
        percussion_reference_dir.mkdir(parents=True, exist_ok=True)
        for stem in drum_reference_stems:
            arranged = render_arranged_stem(
                stem=stem,
                selections=selections,
                section_plan=section_plan,
                target_samples=target_samples,
                prepend_intro_samples=prepend_intro_samples,
                preserve_source_start_samples=preserve_source_start_samples,
                preserve_samples=preserve_samples,
            )
            path = percussion_reference_dir / f"{stem.role}.wav"
            write_wav(path, sample_rate, arranged)
            percussion_reference_outputs[stem.role] = str(path.resolve())

    full_mix = sum_role_outputs(role_outputs, target_samples)
    full_mix_path = out / "arranged-full-mix.wav"
    write_wav(full_mix_path, sample_rate, full_mix)

    warnings = arrangement_warnings(stems, ignored, include_vocals, target_samples, original_samples)
    if drum_subseparation and not drum_subseparation.get("available"):
        warnings.extend(drum_subseparation.get("warnings") or [])

    plan = {
        "ok": True,
        "engine": "continuation_arranger_v0",
        "input_dir": str(source.resolve()),
        "output_dir": str(out.resolve()),
        "target_duration_seconds": round(target_samples / sample_rate, 3),
        "original_duration_seconds": round(original_duration, 3),
        "continue_from_seconds": round(preserve_samples / sample_rate, 3),
        "bpm": round(bpm, 3),
        "phrase_bars": phrase_bars,
        "intro_bars": intro_bars,
        "source_intro_bars": source_intro_bars,
        "prepend_intro_bars": prepend_intro_bars,
        "preserve_source_start_bars": preserve_source_start_bars,
        "preserve_source_start_seconds": round(preserve_source_start_samples / sample_rate, 3),
        "preserve_source_end_seconds": round((preserve_source_start_samples + preserve_samples) / sample_rate, 3),
        "source_end_trim_bars": source_end_trim_bars,
            "breakdown_bars": breakdown_bars,
            "breakdown_drum_mode": breakdown_drum_mode,
            "outro_bars": outro_bars,
        "blueprint_breakdown_bars": blueprint_breakdown_bars,
        "blueprint_outro_bars": blueprint_outro_bars,
        "drum_substems_requested": drum_substems,
        "drum_subseparation": drum_subseparation,
        "percussion_reference_stems": [
            {
                "role": stem.role,
                "source_name": stem.source_name,
                "path": stem.path,
                "duration_seconds": round(stem.duration_seconds, 3),
            }
            for stem in drum_reference_stems
        ],
        "percussion_reference_input_dir": str(Path(percussion_reference_input_dir).resolve()) if percussion_reference_input_dir else None,
        "percussion_reference_ignored_files": percussion_reference_ignored,
        "arrangement_mode": arrangement_mode,
        "transition_grid_bars": transition_grid_bars,
        "pre_break_groove_bars": pre_break_groove_bars,
        "post_drop_groove_bars": post_drop_groove_bars,
        "second_half_extra_bars": second_half_extra_bars,
        "effective_post_drop_groove_bars": effective_post_drop_groove_bars,
        "preserve_source_bars": preserve_source_bars,
        "pre_break_source_start_bars": pre_break_source_start_bars,
        "pre_break_source_bars": pre_break_source_bars,
        "breakdown_source_start_bars": breakdown_source_start_bars,
        "breakdown_source_bars": breakdown_source_bars,
        "post_drop_source_start_bars": post_drop_source_start_bars,
        "post_drop_source_bars": post_drop_source_bars,
        "bar_seconds": round(bar_samples / sample_rate, 6),
        "stems": [
            {
                "role": stem.role,
                "source_name": stem.source_name,
                "path": stem.path,
                "duration_seconds": round(stem.duration_seconds, 3),
            }
            for stem in stems
        ],
        "ignored_files": ignored,
        "selected_blocks": {
            key: block_to_json(block) if block else None
            for key, block in selections.items()
        },
        "blueprint": blueprint,
        "sections": section_plan_to_json(section_plan, sample_rate, bar_samples),
        "outputs": {
            "full_mix": str(full_mix_path.resolve()),
            "stems_dir": str(arranged_stem_dir.resolve()),
            "percussion_reference_dir": str(percussion_reference_dir.resolve()) if percussion_reference_outputs else None,
            "percussion_reference_stems": percussion_reference_outputs,
            "arrangement_map": str((out / "arrangement-map.json").resolve()),
            "report": str((out / "arrangement-report.md").resolve()),
        },
        "warnings": warnings,
    }
    (out / "arrangement-map.json").write_text(json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8")
    (out / "arrangement-report.md").write_text(render_report(plan), encoding="utf-8")
    return plan


def load_stems(input_dir: str, include_vocals: bool = False) -> tuple[list[StemAudio], list[dict]]:
    root = Path(input_dir)
    wavs = sorted(path for path in root.rglob("*") if path.suffix.lower() in {".wav", ".wave"})
    stems: list[StemAudio] = []
    ignored: list[dict] = []
    target_rate: int | None = None

    for path in wavs:
        role = infer_role(path)
        if role == "full_mix":
            ignored.append({"path": str(path.resolve()), "reason": "full_mix_or_candidate_not_used_as_stem"})
            continue
        if role == "vocals" and not include_vocals:
            ignored.append({"path": str(path.resolve()), "role": "vocals", "reason": "vocals_muted_by_default"})
            continue
        sample_rate, data = wavfile.read(str(path))
        samples = pcm_to_float(data)
        if samples.ndim == 1:
            samples = np.stack([samples, samples], axis=1)
        if samples.shape[1] > 2:
            samples = samples[:, :2]
        if samples.shape[1] == 1:
            samples = np.repeat(samples, 2, axis=1)
        if target_rate is None:
            target_rate = int(sample_rate)
        elif sample_rate != target_rate:
            samples = resample_linear(samples, int(sample_rate), target_rate)
            sample_rate = target_rate
        stems.append(
            StemAudio(
                role=dedupe_role(role, [stem.role for stem in stems]),
                source_name=path.name,
                path=str(path.resolve()),
                samples=np.asarray(samples, dtype=np.float32),
                sample_rate=int(sample_rate),
            )
        )

    stems.sort(key=lambda stem: ROLE_ORDER.index(base_role(stem.role)) if base_role(stem.role) in ROLE_ORDER else 99)
    return stems, ignored


def load_drum_reference_substems(stems: list[StemAudio], output_dir: Path) -> tuple[list[StemAudio], dict]:
    drum = next((stem for stem in stems if base_role(stem.role) == "drums"), None)
    if not drum:
        return [], {
            "available": False,
            "method": "drumsep_onnx",
            "stems": {},
            "warnings": ["No drum stem was available for drum sub-separation."],
        }

    result = separate_drum_elements(drum.path, str(output_dir))
    if not result.get("available"):
        return [], result

    reference_stems: list[StemAudio] = []
    existing_roles: list[str] = []
    for role, path in sorted((result.get("stems") or {}).items(), key=lambda item: ROLE_ORDER.index(item[0]) if item[0] in ROLE_ORDER else 99):
        sample_rate, data = wavfile.read(path)
        samples = pcm_to_float(data)
        if samples.ndim == 1:
            samples = np.stack([samples, samples], axis=1)
        if samples.shape[1] > 2:
            samples = samples[:, :2]
        if int(sample_rate) != drum.sample_rate:
            samples = resample_linear(samples, int(sample_rate), drum.sample_rate)
            sample_rate = drum.sample_rate
        deduped_role = dedupe_role(role, existing_roles)
        reference_stems.append(
            StemAudio(
                role=deduped_role,
                source_name=Path(path).name,
                path=str(Path(path).resolve()),
                samples=np.asarray(samples, dtype=np.float32),
                sample_rate=int(sample_rate),
            )
        )
        existing_roles.append(deduped_role)
    reference_stems.sort(key=lambda stem: ROLE_ORDER.index(base_role(stem.role)) if base_role(stem.role) in ROLE_ORDER else 99)
    return reference_stems, result


def load_percussion_reference_stems(input_dir: str) -> tuple[list[StemAudio], list[dict]]:
    stems, ignored = load_stems(input_dir, include_vocals=False)
    reference_stems = [stem for stem in stems if base_role(stem.role) in {"kick", "snare", "hihats", "cymbals", "toms", "percussion"}]
    extra_ignored = [
        {
            "path": stem.path,
            "role": stem.role,
            "reason": "not_percussion_reference_role",
        }
        for stem in stems
        if stem not in reference_stems
    ]
    return reference_stems, ignored + extra_ignored


def infer_role(path: Path) -> str:
    name = normalize_name(path.stem)
    parent = normalize_name(path.parent.name)
    role = infer_role_from_text(name)
    if role != "other":
        return role
    return infer_role_from_text(parent)


def infer_role_from_text(text: str) -> str:
    if any(token in text for token in VOCAL_TOKENS):
        return "vocals"
    if "kick" in text or "bombo" in text:
        return "kick"
    if "snare" in text or "clap" in text or "redoblante" in text:
        return "snare"
    if "hihat" in text or "hi hat" in text or "hh" in text:
        return "hihats"
    if "cymbal" in text or "cymbals" in text or "ride" in text or "crash" in text or "platillos" in text:
        return "cymbals"
    if "tom" in text or "toms" in text:
        return "toms"
    if "drum" in text or "kit" in text:
        return "drums"
    if "perc" in text or "shaker" in text or "hat" in text:
        return "percussion"
    if "bass" in text or "sub" in text:
        return "bass"
    if "stab" in text or "chord" in text or "keys" in text or "piano" in text:
        return "stabs"
    if "synth" in text or "pad" in text or "arp" in text:
        return "synths"
    if "fx" in text or "effect" in text or "atmos" in text or "noise" in text or "ambience" in text:
        return "fx"
    if any(token in text for token in FULL_MIX_TOKENS):
        return "full_mix"
    return "other"


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def dedupe_role(role: str, existing: list[str]) -> str:
    if role not in existing:
        return role
    index = 2
    while f"{role}_{index}" in existing:
        index += 1
    return f"{role}_{index}"


def base_role(role: str) -> str:
    return role.split("_", 1)[0]


def pcm_to_float(data: np.ndarray) -> np.ndarray:
    if np.issubdtype(data.dtype, np.floating):
        return np.asarray(np.clip(data, -1.0, 1.0), dtype=np.float32)
    if data.dtype == np.uint8:
        return ((data.astype(np.float32) - 128.0) / 128.0).astype(np.float32)
    info = np.iinfo(data.dtype)
    scale = max(abs(info.min), abs(info.max))
    return (data.astype(np.float32) / float(scale)).astype(np.float32)


def resample_linear(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate:
        return samples
    duration = len(samples) / float(source_rate)
    target_count = max(1, int(round(duration * target_rate)))
    source_x = np.linspace(0.0, duration, num=len(samples), endpoint=False)
    target_x = np.linspace(0.0, duration, num=target_count, endpoint=False)
    channels = [np.interp(target_x, source_x, samples[:, channel]) for channel in range(samples.shape[1])]
    return np.stack(channels, axis=1).astype(np.float32)


def estimate_bpm_from_stems(stems: list[StemAudio]) -> float | None:
    preferred = next((stem for stem in stems if base_role(stem.role) == "drums"), stems[0])
    mono = np.mean(preferred.samples, axis=1)
    if len(mono) > preferred.sample_rate * 90:
        mono = mono[: preferred.sample_rate * 90]
    curve = compute_energy_curve([float(value) for value in mono], preferred.sample_rate)
    tempo = estimate_tempo(curve)
    bpm = tempo.get("bpm")
    return float(bpm) if bpm else None


def resolve_continue_from(value: str | float, original_samples: int, sample_rate: int, bar_samples: int) -> int:
    if isinstance(value, (int, float)):
        seconds = float(value)
    else:
        text = str(value).strip().lower()
        if text in {"", "auto", "end"}:
            return original_samples
        if text.endswith("s"):
            text = text[:-1]
        seconds = float(text)
    samples = int(round(seconds * sample_rate))
    if bar_samples > 0:
        samples = int(round(samples / bar_samples) * bar_samples)
    return max(0, min(original_samples, samples))


def analyze_phrase_blocks(stems: list[StemAudio], original_samples: int, phrase_samples: int) -> list[PhraseBlock]:
    blocks: list[PhraseBlock] = []
    sample_rate = stems[0].sample_rate
    for start in range(0, max(1, original_samples - phrase_samples + 1), phrase_samples):
        end = min(original_samples, start + phrase_samples)
        if end - start < phrase_samples * 0.5:
            continue
        role_energy: dict[str, float] = {}
        role_spectrum: dict[str, dict[str, float]] = {}
        for stem in stems:
            chunk = stem.samples[start:end]
            role_energy[stem.role] = rms(chunk)
            role_spectrum[stem.role] = spectral_profile(chunk, sample_rate)
        total = sum(role_energy.values())
        blocks.append(
            PhraseBlock(
                start=start,
                end=end,
                start_seconds=start / sample_rate,
                end_seconds=end / sample_rate,
                role_energy=role_energy,
                role_spectrum=role_spectrum,
                total_energy=total,
            )
        )
    if not blocks:
        role_energy = {stem.role: rms(stem.samples[:original_samples]) for stem in stems}
        role_spectrum = {stem.role: spectral_profile(stem.samples[:original_samples], sample_rate) for stem in stems}
        blocks.append(
            PhraseBlock(
                start=0,
                end=original_samples,
                start_seconds=0.0,
                end_seconds=original_samples / sample_rate,
                role_energy=role_energy,
                role_spectrum=role_spectrum,
                total_energy=sum(role_energy.values()),
            )
        )
    return blocks


def select_blocks(blocks: list[PhraseBlock], stems: list[StemAudio]) -> dict[str, PhraseBlock]:
    bass_roles = [stem.role for stem in stems if base_role(stem.role) == "bass"]
    drum_roles = [stem.role for stem in stems if base_role(stem.role) in PERCUSSION_ROLES]
    fx_roles = [stem.role for stem in stems if base_role(stem.role) == "fx"]
    source_end = max(block.end for block in blocks)
    usable = [block for block in blocks if block.end_seconds <= (source_end / stems[0].sample_rate) - 8.0] or blocks
    first_half = [block for block in usable if block.start <= source_end * 0.52] or usable
    later_half = [block for block in usable if block.start >= source_end * 0.35] or usable
    intro_candidates = [block for block in usable if block.start <= source_end * 0.2] or usable

    def energy(block: PhraseBlock, roles: list[str]) -> float:
        return sum(block.role_energy.get(role, 0.0) for role in roles)

    def high_ratio(block: PhraseBlock, roles: list[str]) -> float:
        values = [block.role_spectrum.get(role, {}).get("high_ratio", 0.0) for role in roles]
        return float(np.mean(values)) if values else 0.0

    def low_ratio(block: PhraseBlock, roles: list[str]) -> float:
        values = [block.role_spectrum.get(role, {}).get("low_ratio", 0.0) for role in roles]
        return float(np.mean(values)) if values else 0.0

    intro = max(
        intro_candidates,
        key=lambda block: energy(block, drum_roles) * 0.8 + high_ratio(block, drum_roles) * 0.25 - energy(block, bass_roles),
    )
    full = max(first_half, key=lambda block: block.total_energy + energy(block, bass_roles) * 0.8)
    developed = max(
        later_half,
        key=lambda block: (
            block.total_energy
            + energy(block, bass_roles) * 0.65
            + energy(block, fx_roles) * 0.35
            + high_ratio(block, drum_roles) * 0.2
            - low_ratio(block, drum_roles) * 0.05
        ),
    )
    drums = max(usable, key=lambda block: energy(block, drum_roles) + high_ratio(block, drum_roles) * 0.2 + block.total_energy * 0.1)
    fx = max(usable, key=lambda block: energy(block, fx_roles) + block.total_energy * 0.05) if fx_roles else drums
    reduced_candidates = sorted(
        usable,
        key=lambda block: (energy(block, drum_roles) + energy(block, fx_roles) * 0.7 - energy(block, bass_roles) * 0.8),
        reverse=True,
    )
    reduced = reduced_candidates[0] if reduced_candidates else drums
    return {"intro": intro, "full_groove": full, "developed_groove": developed, "drums": drums, "breakdown": reduced, "fx": fx}


def spectral_profile(samples: np.ndarray, sample_rate: int) -> dict[str, float]:
    if samples.size == 0:
        return {"low_ratio": 0.0, "mid_ratio": 0.0, "high_ratio": 0.0, "centroid_hz": 0.0}
    mono = np.mean(samples, axis=1) if samples.ndim > 1 else samples
    if len(mono) > sample_rate * 20:
        stride = max(1, int(len(mono) / (sample_rate * 20)))
        mono = mono[::stride]
    window = np.hanning(len(mono)) if len(mono) > 1 else np.ones_like(mono)
    spectrum = np.abs(np.fft.rfft(mono * window))
    freqs = np.fft.rfftfreq(len(mono), d=1.0 / sample_rate)
    total = float(np.sum(spectrum)) or 1.0
    low = float(np.sum(spectrum[(freqs >= 20.0) & (freqs < 180.0)]))
    mid = float(np.sum(spectrum[(freqs >= 180.0) & (freqs < 2500.0)]))
    high = float(np.sum(spectrum[(freqs >= 2500.0) & (freqs < 12000.0)]))
    centroid = float(np.sum(freqs * spectrum) / total)
    return {
        "low_ratio": low / total,
        "mid_ratio": mid / total,
        "high_ratio": high / total,
        "centroid_hz": centroid,
    }


def build_section_plan(
    preserve_samples: int,
    target_samples: int,
    sample_rate: int,
    selections: dict[str, PhraseBlock],
    stems: list[StemAudio],
) -> list[dict]:
    extension = max(0, target_samples - preserve_samples)
    if extension <= 0:
        return []
    full_a = int(extension * 0.28)
    breakdown = int(extension * 0.24)
    full_b = int(extension * 0.30)
    outro = extension - full_a - breakdown - full_b

    return [
        {
            "name": "continue_groove",
            "duration": full_a,
            "source": selections["full_groove"],
            "mute_roles": set(),
            "fade_out_roles": set(),
        },
        {
            "name": "stripped_breakdown",
                "duration": breakdown,
                "source": selections["breakdown"],
                "mute_roles": {"bass", "vocals"},
                "fade_out_roles": set(),
                "breakdown_drum_mode": "tops",
            },
        {
            "name": "return_to_groove",
            "duration": full_b,
            "source": selections["full_groove"],
            "mute_roles": {"vocals"},
            "fade_out_roles": set(),
        },
        {
            "name": "dj_outro",
            "duration": outro,
            "source": selections["drums"],
                "mute_roles": {"bass", "kick", "vocals"},
            "fade_out_roles": {base_role(stem.role) for stem in stems},
        },
    ]


def build_blueprint_section_plan(
    blueprint_audio: str,
    preserve_samples: int,
    arranged_base_samples: int,
    target_samples: int,
    sample_rate: int,
    phrase_samples: int,
    selections: dict[str, PhraseBlock],
    stems: list[StemAudio],
    bar_samples: int,
    breakdown_bars: int,
    outro_bars: int,
) -> tuple[list[dict], dict]:
    blueprint_path = Path(blueprint_audio)
    if not blueprint_path.exists():
        raise FileNotFoundError(f"Blueprint audio not found: {blueprint_audio}")
    blueprint_rate, blueprint_data = wavfile.read(str(blueprint_path))
    blueprint_samples = pcm_to_float(blueprint_data)
    if blueprint_samples.ndim == 1:
        blueprint_samples = np.stack([blueprint_samples, blueprint_samples], axis=1)
    if blueprint_samples.shape[1] > 2:
        blueprint_samples = blueprint_samples[:, :2]
    if int(blueprint_rate) != sample_rate:
        blueprint_samples = resample_linear(blueprint_samples, int(blueprint_rate), sample_rate)

    blueprint_total = min(len(blueprint_samples), target_samples)
    extension = max(0, target_samples - arranged_base_samples)
    if extension <= 0:
        return [], {
            "path": str(blueprint_path.resolve()),
            "duration_seconds": round(len(blueprint_samples) / sample_rate, 3),
            "mode": "no_extension_needed",
        }

    raw_blocks = analyze_blueprint_blocks(
        blueprint_samples=blueprint_samples,
        start_sample=preserve_samples,
        end_sample=blueprint_total,
        phrase_samples=phrase_samples,
        sample_rate=sample_rate,
    )
    if not raw_blocks:
        return build_section_plan(preserve_samples, target_samples, sample_rate, selections, stems), {
            "path": str(blueprint_path.resolve()),
            "duration_seconds": round(len(blueprint_samples) / sample_rate, 3),
            "mode": "fallback_generic_no_blueprint_tail",
        }

    section_plan = build_structured_blueprint_plan(
        raw_blocks=raw_blocks,
        preserve_samples=arranged_base_samples,
        target_samples=target_samples,
        sample_rate=sample_rate,
        selections=selections,
        bar_samples=bar_samples,
        breakdown_bars=breakdown_bars,
        outro_bars=outro_bars,
    )
    plan_duration = sum(int(section["duration"]) for section in section_plan)
    if plan_duration < extension:
        section_plan.append(
            {
                "name": "dj_outro",
                "duration": extension - plan_duration,
                "source": selections["drums"],
                "mute_roles": {"bass", "kick", "vocals"},
                "fade_out_roles": set(),
            }
        )
    elif plan_duration > extension and section_plan:
        section_plan[-1]["duration"] = max(0, int(section_plan[-1]["duration"]) - (plan_duration - extension))

    return section_plan, {
        "path": str(blueprint_path.resolve()),
        "duration_seconds": round(len(blueprint_samples) / sample_rate, 3),
        "mode": "structured_energy_tail_after_continue_from",
        "tail_start_seconds": round(preserve_samples / sample_rate, 3),
        "breakdown_bars": breakdown_bars,
        "outro_bars": outro_bars,
        "blocks": [
            {
                "start_seconds": round(block["start"] / sample_rate, 3),
                "end_seconds": round(block["end"] / sample_rate, 3),
                "energy": round(block["energy"], 6),
            }
            for block in raw_blocks
        ],
    }


def build_suno_block_sequence_plan(
    arranged_base_samples: int,
    target_samples: int,
    sample_rate: int,
    selections: dict[str, PhraseBlock],
    bar_samples: int,
    pre_break_bars: int,
    breakdown_bars: int,
    outro_bars: int,
    blueprint_audio: str | None = None,
) -> tuple[list[dict], dict | None]:
    extension = max(0, target_samples - arranged_base_samples)
    if extension <= 0:
        return [], None

    pre_break = clamp_section_samples(pre_break_bars * bar_samples, extension, minimum=0)
    breakdown = clamp_section_samples(breakdown_bars * bar_samples, max(0, extension - pre_break), minimum=0)
    outro = clamp_section_samples(outro_bars * bar_samples, max(0, extension - pre_break - breakdown), minimum=0)
    postdrop = max(0, extension - pre_break - breakdown - outro)

    sections: list[dict] = []
    cursor = arranged_base_samples
    developed = selections.get("developed_groove") or selections["full_groove"]
    full = selections["full_groove"]
    breakdown_block = selections["breakdown"]
    outro_block = selections.get("intro") or selections["drums"]

    if pre_break > 0:
        sections.append(
            make_section(
                name="pre_break_developed_groove",
                start=cursor,
                end=cursor + pre_break,
                source=developed,
                mute_roles={"vocals"},
                fade_out_roles=set(),
                sample_rate=sample_rate,
                blueprint_energy=0.0,
            )
        )
        cursor += pre_break
    if breakdown > 0:
        sections.append(
            make_section(
                name="stripped_breakdown",
                start=cursor,
                end=cursor + breakdown,
                source=breakdown_block,
                mute_roles={"bass", "vocals"},
                fade_out_roles=set(),
                sample_rate=sample_rate,
                blueprint_energy=0.0,
                breakdown_drum_mode="tops",
            )
        )
        cursor += breakdown
    for index, duration in enumerate(split_postdrop_sections(postdrop, bar_samples)):
        source = developed if index % 2 == 0 else full
        sections.append(
            make_section(
                name="post_drop_developed_groove" if index == 0 else "post_drop_variation",
                start=cursor,
                end=cursor + duration,
                source=source,
                mute_roles={"vocals"},
                fade_out_roles=set(),
                sample_rate=sample_rate,
                blueprint_energy=0.0,
            )
        )
        cursor += duration
    if outro > 0:
        sections.append(
            make_section(
                name="dj_outro",
                start=cursor,
                end=cursor + outro,
                source=outro_block,
                mute_roles={"bass", "kick", "vocals"},
                fade_out_roles=set(),
                sample_rate=sample_rate,
                blueprint_energy=0.0,
            )
        )

    blueprint = {
        "mode": "suno_block_sequence",
        "path": str(Path(blueprint_audio).resolve()) if blueprint_audio else None,
        "tail_start_seconds": round(arranged_base_samples / sample_rate, 3),
        "pre_break_bars": pre_break_bars,
        "breakdown_bars": breakdown_bars,
        "outro_bars": outro_bars,
        "rule": "preserve Suno first half, repeat developed Suno groove before breakdown, then reuse developed/full blocks after the drop.",
    }
    return sections, blueprint


def normalize_breakdown_drum_mode(value: str) -> str:
    mode = str(value or "tops").strip().lower().replace("_", "-")
    aliases = {
        "top": "tops",
        "top-only": "tops",
        "no-drums": "none",
        "silent": "none",
        "mute": "none",
        "with-drums": "full",
        "drums": "full",
        "first-half-none-second-half-tops": "half-tops",
        "half": "half-tops",
        "first-half-none-second-half-drums": "half-full",
        "half-drums": "half-full",
    }
    mode = aliases.get(mode, mode)
    if mode not in BREAKDOWN_DRUM_MODES:
        allowed = ", ".join(sorted(BREAKDOWN_DRUM_MODES))
        raise ValueError(f"breakdown_drum_mode must be one of: {allowed}.")
    return mode


def build_prebreak_diagnostic_plan(
    stems: list[StemAudio],
    arranged_base_samples: int,
    sample_rate: int,
    bar_samples: int,
    original_samples: int,
    selections: dict[str, PhraseBlock],
    pre_break_repeat_bars: int,
    pre_break_source_start_bars: int | None,
    pre_break_source_bars: int,
    breakdown_source_start_bars: int | None,
    breakdown_source_bars: int,
    breakdown_drum_mode: str,
) -> tuple[list[dict], dict]:
    """Render only the bar-locked bridge from Suno's first half into the breakdown.

    This mode is deliberately strict: every appended section is an integer number
    of bars and every copied source block is an integer number of bars. It is for
    validating house/techno arrangement math before attempting a full second half.
    """
    pre_break_source = source_block_from_bars(
        stems=stems,
        start_bars=pre_break_source_start_bars,
        bars=pre_break_source_bars,
        fallback=selections.get("developed_groove") or selections["full_groove"],
        bar_samples=bar_samples,
        original_samples=original_samples,
        sample_rate=sample_rate,
        label="pre_break_source",
    )
    breakdown_source = source_block_from_bars(
        stems=stems,
        start_bars=breakdown_source_start_bars,
        bars=breakdown_source_bars,
        fallback=selections["breakdown"],
        bar_samples=bar_samples,
        original_samples=original_samples,
        sample_rate=sample_rate,
        label="breakdown_source",
    )
    pre_break_duration = max(0, pre_break_repeat_bars) * bar_samples
    breakdown_duration = max(0, breakdown_source_bars) * bar_samples
    cursor = arranged_base_samples
    sections: list[dict] = []
    if pre_break_duration > 0:
        sections.append(
            make_section(
                name="pre_break_developed_groove",
                start=cursor,
                end=cursor + pre_break_duration,
                source=pre_break_source,
                mute_roles={"vocals"},
                fade_out_roles=set(),
                sample_rate=sample_rate,
                blueprint_energy=pre_break_source.total_energy,
            )
        )
        cursor += pre_break_duration
    if breakdown_duration > 0:
        sections.append(
            make_section(
                name="stripped_breakdown",
                start=cursor,
                end=cursor + breakdown_duration,
                source=breakdown_source,
                mute_roles={"bass", "vocals"},
                fade_out_roles=set(),
                sample_rate=sample_rate,
                blueprint_energy=breakdown_source.total_energy,
                breakdown_drum_mode=breakdown_drum_mode,
            )
        )

    return sections, {
        "mode": "prebreak_diagnostic",
        "rule": "preserve Suno source, repeat one exact developed phrase to a bar-locked 32-bar pre-break, then render one bar-locked breakdown; no post-drop/outro fill.",
        "tail_start_seconds": round(arranged_base_samples / sample_rate, 3),
        "pre_break_repeat_bars": pre_break_repeat_bars,
        "pre_break_source_start_bars": round(pre_break_source.start / bar_samples, 3),
        "pre_break_source_bars": round((pre_break_source.end - pre_break_source.start) / bar_samples, 3),
        "breakdown_source_start_bars": round(breakdown_source.start / bar_samples, 3),
        "breakdown_source_bars": round((breakdown_source.end - breakdown_source.start) / bar_samples, 3),
        "breakdown_drum_mode": breakdown_drum_mode,
    }


def build_club_second_half_plan(
    stems: list[StemAudio],
    arranged_base_samples: int,
    sample_rate: int,
    bar_samples: int,
    original_samples: int,
    selections: dict[str, PhraseBlock],
    transition_grid_bars: int,
    pre_break_repeat_bars: int,
    pre_break_source_start_bars: int | None,
    pre_break_source_bars: int,
    breakdown_source_start_bars: int | None,
    breakdown_source_bars: int,
    breakdown_drum_mode: str,
    post_drop_repeat_bars: int,
    post_drop_source_start_bars: int | None,
    post_drop_source_bars: int | None,
    outro_bars: int,
) -> tuple[list[dict], dict]:
    """Build the accepted first half plus a bar-locked second-half continuation.

    The post-drop source is selected as one contiguous source window using
    FFT-derived spectral profiles and RMS energy. This avoids gluing unrelated
    small fragments together.
    """
    pre_break_source = source_block_from_bars(
        stems=stems,
        start_bars=pre_break_source_start_bars,
        bars=pre_break_source_bars,
        fallback=selections.get("developed_groove") or selections["full_groove"],
        bar_samples=bar_samples,
        original_samples=original_samples,
        sample_rate=sample_rate,
        label="pre_break_source",
    )
    breakdown_source = source_block_from_bars(
        stems=stems,
        start_bars=breakdown_source_start_bars,
        bars=breakdown_source_bars,
        fallback=selections["breakdown"],
        bar_samples=bar_samples,
        original_samples=original_samples,
        sample_rate=sample_rate,
        label="breakdown_source",
    )
    post_drop_source, analysis = select_fft_post_drop_window(
        stems=stems,
        original_samples=original_samples,
        bar_samples=bar_samples,
        sample_rate=sample_rate,
        transition_grid_bars=transition_grid_bars,
        post_drop_bars=post_drop_repeat_bars,
        source_bars=post_drop_source_bars,
        explicit_start_bars=post_drop_source_start_bars,
        fallback=selections.get("developed_groove") or selections["full_groove"],
    )
    outro_source = repeated_render_tail_block(
        stems=stems,
        source=post_drop_source,
        rendered_bars=post_drop_repeat_bars,
        bars=outro_bars,
        bar_samples=bar_samples,
        sample_rate=sample_rate,
        label="outro_source",
    )

    cursor = arranged_base_samples
    sections: list[dict] = []
    sections.append(
        make_section(
            name="pre_break_developed_groove",
            start=cursor,
            end=cursor + pre_break_repeat_bars * bar_samples,
            source=pre_break_source,
            mute_roles={"vocals"},
            fade_out_roles=set(),
            sample_rate=sample_rate,
            blueprint_energy=pre_break_source.total_energy,
        )
    )
    cursor += pre_break_repeat_bars * bar_samples
    sections.append(
        make_section(
            name="stripped_breakdown",
            start=cursor,
            end=cursor + breakdown_source_bars * bar_samples,
            source=breakdown_source,
            mute_roles={"bass", "vocals"},
            fade_out_roles=set(),
            sample_rate=sample_rate,
            blueprint_energy=breakdown_source.total_energy,
            breakdown_drum_mode=breakdown_drum_mode,
        )
    )
    cursor += breakdown_source_bars * bar_samples
    sections.append(
        make_section(
            name="post_drop_fft_selected_groove",
            start=cursor,
            end=cursor + post_drop_repeat_bars * bar_samples,
            source=post_drop_source,
            mute_roles={"vocals"},
            fade_out_roles=set(),
            sample_rate=sample_rate,
            blueprint_energy=post_drop_source.total_energy,
        )
    )
    cursor += post_drop_repeat_bars * bar_samples
    if outro_bars > 0:
        sections.append(
            make_section(
                name="dj_outro",
                start=cursor,
                end=cursor + outro_bars * bar_samples,
                source=outro_source,
                mute_roles={"bass", "vocals"},
                fade_out_roles=set(),
                sample_rate=sample_rate,
                blueprint_energy=outro_source.total_energy,
            )
        )

    return sections, {
        "mode": "club_second_half_fft",
        "rule": (
            "preserve accepted first half; repeat the accepted pre-break phrase; render one bar-locked breakdown; "
            "select one contiguous FFT/RMS-scored source window for the post-drop groove; finish by reusing the tail of that groove with bass muted"
        ),
        "tail_start_seconds": round(arranged_base_samples / sample_rate, 3),
        "transition_grid_bars": transition_grid_bars,
        "pre_break_repeat_bars": pre_break_repeat_bars,
        "pre_break_source_start_bars": round(pre_break_source.start / bar_samples, 3),
        "pre_break_source_bars": round((pre_break_source.end - pre_break_source.start) / bar_samples, 3),
        "breakdown_source_start_bars": round(breakdown_source.start / bar_samples, 3),
        "breakdown_source_bars": round((breakdown_source.end - breakdown_source.start) / bar_samples, 3),
        "breakdown_drum_mode": breakdown_drum_mode,
        "post_drop_repeat_bars": post_drop_repeat_bars,
        "post_drop_source_start_bars": round(post_drop_source.start / bar_samples, 3),
        "post_drop_source_bars": round((post_drop_source.end - post_drop_source.start) / bar_samples, 3),
        "outro_bars": outro_bars,
        "outro_source_start_bars": round(outro_source.start / bar_samples, 3),
        "outro_source_bars": round((outro_source.end - outro_source.start) / bar_samples, 3),
        "outro_source_rule": "same repeated post-drop slice with bass muted",
        "post_drop_selection": analysis,
    }


def build_reference_blueprint_plan(
    stems: list[StemAudio],
    blueprint_audio: str,
    arranged_base_samples: int,
    target_samples: int,
    sample_rate: int,
    bar_samples: int,
    original_samples: int,
    selections: dict[str, PhraseBlock],
    transition_grid_bars: int,
    breakdown_drum_mode: str,
    outro_bars: int,
) -> tuple[list[dict], dict]:
    """Build appended sections from the reference arrangement's spectral energy map.

    The reference decides when the track is full, bass-reduced, broken down, or
    in an outro. The generated Suno stems still supply all audio material.
    """
    blueprint_path = Path(blueprint_audio)
    if not blueprint_path.exists():
        raise FileNotFoundError(f"Blueprint audio not found: {blueprint_audio}")

    blueprint_samples, blueprint_rate = read_audio_float(blueprint_path)
    if blueprint_rate != sample_rate:
        blueprint_samples = resample_linear(blueprint_samples, blueprint_rate, sample_rate)

    extension = max(0, target_samples - arranged_base_samples)
    if extension <= 0:
        return [], {
            "mode": "reference_blueprint_no_extension_needed",
            "path": str(blueprint_path.resolve()),
        }

    unit_bars = reference_blueprint_unit_bars(transition_grid_bars)
    blueprint_units = analyze_reference_blueprint_units(
        blueprint_samples=blueprint_samples,
        sample_rate=sample_rate,
        bar_samples=bar_samples,
        unit_bars=unit_bars,
        target_samples=target_samples,
        outro_bars=outro_bars,
    )
    appended_units = [
        unit
        for unit in blueprint_units
        if unit["end"] > arranged_base_samples and unit["start"] < target_samples
    ]
    if not appended_units:
        fallback, analysis = select_fft_post_drop_window(
            stems=stems,
            original_samples=original_samples,
            bar_samples=bar_samples,
            sample_rate=sample_rate,
            transition_grid_bars=transition_grid_bars,
            post_drop_bars=max(unit_bars, extension // bar_samples),
            source_bars=None,
            explicit_start_bars=None,
            fallback=selections.get("developed_groove") or selections["full_groove"],
        )
        return [
            make_section(
                name="reference_full_groove",
                start=arranged_base_samples,
                end=target_samples,
                source=fallback,
                mute_roles={"vocals"},
                fade_out_roles=set(),
                sample_rate=sample_rate,
                blueprint_energy=fallback.total_energy,
            )
        ], {
            "mode": "reference_blueprint_fallback_no_appended_units",
            "path": str(blueprint_path.resolve()),
            "post_drop_selection": analysis,
        }

    section_specs = merge_reference_units(appended_units, arranged_base_samples, target_samples)
    sections: list[dict] = []
    source_cache: dict[tuple[str, int], PhraseBlock] = {}
    source_analysis: dict[str, dict] = {}
    for spec in section_specs:
        duration = max(0, int(spec["end"]) - int(spec["start"]))
        if duration <= 0:
            continue
        section_bars = max(unit_bars, int(round(duration / bar_samples)))
        source = reference_source_for_state(
            state=spec["state"],
            section_bars=section_bars,
            stems=stems,
            original_samples=original_samples,
            bar_samples=bar_samples,
            sample_rate=sample_rate,
            transition_grid_bars=transition_grid_bars,
            selections=selections,
            cache=source_cache,
            analysis=source_analysis,
        )
        name, mute_roles, drum_mode = reference_section_controls(
            state=spec["state"],
            breakdown_drum_mode=breakdown_drum_mode,
        )
        sections.append(
            make_section(
                name=name,
                start=int(spec["start"]),
                end=int(spec["end"]),
                source=source,
                mute_roles=mute_roles,
                fade_out_roles=set(),
                sample_rate=sample_rate,
                blueprint_energy=float(spec["energy"]),
                breakdown_drum_mode=drum_mode,
            )
        )

    return sections, {
        "mode": "reference_blueprint_spectral_grid",
        "path": str(blueprint_path.resolve()),
        "duration_seconds": round(len(blueprint_samples) / sample_rate, 3),
        "unit_bars": unit_bars,
        "tail_start_bars": round(arranged_base_samples / bar_samples, 3),
        "rule": (
            "classify the reference on an 8/16-bar FFT/RMS grid, then apply those full-groove, bass-muted, "
            "breakdown, and outro states to the generated Suno stems without off-grid slicing"
        ),
        "source_selection": source_analysis,
        "units": [
            {
                "start_bars": round(unit["start"] / bar_samples, 3),
                "end_bars": round(unit["end"] / bar_samples, 3),
                "state": unit["state"],
                "rms_norm": round(unit["rms_norm"], 4),
                "low_norm": round(unit["low_norm"], 4),
                "high_norm": round(unit["high_norm"], 4),
                "low_ratio": round(unit["low_ratio"], 4),
                "energy": round(unit["energy"], 6),
            }
            for unit in blueprint_units
        ],
    }


def read_audio_float(path: Path) -> tuple[np.ndarray, int]:
    sample_rate, data = wavfile.read(str(path))
    samples = pcm_to_float(data)
    if samples.ndim == 1:
        samples = np.stack([samples, samples], axis=1)
    if samples.shape[1] > 2:
        samples = samples[:, :2]
    if samples.shape[1] == 1:
        samples = np.repeat(samples, 2, axis=1)
    return np.asarray(samples, dtype=np.float32), int(sample_rate)


def reference_blueprint_unit_bars(transition_grid_bars: int) -> int:
    grid = max(1, int(transition_grid_bars))
    if grid >= 16:
        return 8
    if grid >= 8:
        return 8
    return grid


def analyze_reference_blueprint_units(
    blueprint_samples: np.ndarray,
    sample_rate: int,
    bar_samples: int,
    unit_bars: int,
    target_samples: int,
    outro_bars: int,
) -> list[dict]:
    unit_samples = max(1, unit_bars * bar_samples)
    end_limit = min(len(blueprint_samples), target_samples)
    raw: list[dict] = []
    for start in range(0, end_limit, unit_samples):
        end = min(end_limit, start + unit_samples)
        if end - start < unit_samples * 0.75:
            continue
        chunk = blueprint_samples[start:end]
        profile = spectral_profile(chunk, sample_rate)
        energy = rms(chunk)
        raw.append(
            {
                "start": start,
                "end": end,
                "energy": energy,
                "low_ratio": profile["low_ratio"],
                "mid_ratio": profile["mid_ratio"],
                "high_ratio": profile["high_ratio"],
                "low_power": energy * profile["low_ratio"],
                "high_power": energy * profile["high_ratio"],
            }
        )
    if raw and raw[-1]["end"] < target_samples:
        tail = raw[-1].copy()
        tail["start"] = raw[-1]["end"]
        tail["end"] = target_samples
        raw.append(tail)
    if not raw:
        return []

    rms_median = robust_positive_median([unit["energy"] for unit in raw])
    low_median = robust_positive_median([unit["low_power"] for unit in raw])
    high_median = robust_positive_median([unit["high_power"] for unit in raw])
    outro_start = max(0, target_samples - max(0, outro_bars) * bar_samples)

    for unit in raw:
        unit["rms_norm"] = unit["energy"] / rms_median
        unit["low_norm"] = unit["low_power"] / low_median
        unit["high_norm"] = unit["high_power"] / high_median
        unit["state"] = classify_reference_unit(unit, outro_start=outro_start)
    return raw


def robust_positive_median(values: list[float]) -> float:
    positives = [float(value) for value in values if value > 1e-9]
    if not positives:
        return 1.0
    return max(1e-9, float(np.median(positives)))


def classify_reference_unit(unit: dict, outro_start: int) -> str:
    if unit["start"] >= outro_start:
        return "outro"
    rms_norm = float(unit["rms_norm"])
    low_norm = float(unit["low_norm"])
    high_norm = float(unit["high_norm"])
    low_ratio = float(unit["low_ratio"])
    if rms_norm < 0.48:
        return "breakdown"
    if low_norm < 0.42:
        return "breakdown"
    if low_norm < 0.68 and high_norm >= 0.45:
        return "bass_muted"
    if low_ratio < 0.14 and rms_norm < 0.85:
        return "bass_muted"
    return "full_groove"


def merge_reference_units(units: list[dict], start: int, end: int) -> list[dict]:
    specs: list[dict] = []
    for unit in units:
        unit_start = max(start, int(unit["start"]))
        unit_end = min(end, int(unit["end"]))
        if unit_end <= unit_start:
            continue
        if specs and specs[-1]["state"] == unit["state"] and specs[-1]["end"] == unit_start:
            specs[-1]["end"] = unit_end
            specs[-1]["energy_values"].append(float(unit["energy"]))
        else:
            specs.append(
                {
                    "state": unit["state"],
                    "start": unit_start,
                    "end": unit_end,
                    "energy_values": [float(unit["energy"])],
                }
            )
    for spec in specs:
        spec["energy"] = float(np.mean(spec.pop("energy_values")))
    return specs


def reference_source_for_state(
    state: str,
    section_bars: int,
    stems: list[StemAudio],
    original_samples: int,
    bar_samples: int,
    sample_rate: int,
    transition_grid_bars: int,
    selections: dict[str, PhraseBlock],
    cache: dict[tuple[str, int], PhraseBlock],
    analysis: dict[str, dict],
) -> PhraseBlock:
    source_bars = max(1, int(section_bars))
    cache_key = (state, source_bars)
    if cache_key in cache:
        return cache[cache_key]

    if state in {"full_groove", "outro"}:
        fallback = selections.get("developed_groove") or selections["full_groove"]
        block, details = select_fft_post_drop_window(
            stems=stems,
            original_samples=original_samples,
            bar_samples=bar_samples,
            sample_rate=sample_rate,
            transition_grid_bars=transition_grid_bars,
            post_drop_bars=source_bars,
            source_bars=None,
            explicit_start_bars=None,
            fallback=fallback,
        )
        analysis[f"{state}_{source_bars}"] = details
    elif state == "breakdown":
        block = source_block_from_bars(
            stems=stems,
            start_bars=None,
            bars=source_bars,
            fallback=selections["breakdown"],
            bar_samples=bar_samples,
            original_samples=original_samples,
            sample_rate=sample_rate,
            label="reference_breakdown_source",
        )
    else:
        block = source_block_from_bars(
            stems=stems,
            start_bars=None,
            bars=source_bars,
            fallback=selections.get("developed_groove") or selections["full_groove"],
            bar_samples=bar_samples,
            original_samples=original_samples,
            sample_rate=sample_rate,
            label="reference_bass_muted_source",
        )
    cache[cache_key] = block
    return block


def reference_section_controls(state: str, breakdown_drum_mode: str) -> tuple[str, set[str], str]:
    if state == "breakdown":
        return "stripped_breakdown", {"bass", "vocals"}, breakdown_drum_mode
    if state == "bass_muted":
        return "reference_bass_muted_groove", {"bass", "vocals"}, "tops"
    if state == "outro":
        return "dj_outro", {"bass", "vocals"}, "tops"
    return "reference_full_groove", {"vocals"}, "tops"


def source_tail_block(
    stems: list[StemAudio],
    source: PhraseBlock,
    bars: int,
    bar_samples: int,
    sample_rate: int,
    label: str,
) -> PhraseBlock:
    if bars <= 0:
        raise ValueError(f"{label} must be at least 1 bar.")
    duration = bars * bar_samples
    if source.end - source.start < duration:
        start = source.start
    else:
        start = source.end - duration
    end = source.end
    role_energy: dict[str, float] = {}
    role_spectrum: dict[str, dict[str, float]] = {}
    for stem in stems:
        chunk = stem.samples[start:end]
        role_energy[stem.role] = rms(chunk)
        role_spectrum[stem.role] = spectral_profile(chunk, sample_rate)
    return PhraseBlock(
        start=start,
        end=end,
        start_seconds=start / sample_rate,
        end_seconds=end / sample_rate,
        role_energy=role_energy,
        role_spectrum=role_spectrum,
        total_energy=sum(role_energy.values()),
    )


def repeated_render_tail_block(
    stems: list[StemAudio],
    source: PhraseBlock,
    rendered_bars: int,
    bars: int,
    bar_samples: int,
    sample_rate: int,
    label: str,
) -> PhraseBlock:
    """Return the source slice playing immediately before an outro.

    A long post-drop may render by looping a shorter developed source window.
    The outro must continue that same musical material with bass muted, not jump
    to a different tail of the source window.
    """
    if bars <= 0:
        raise ValueError(f"{label} must be at least 1 bar.")
    source_bars = max(1, int(round((source.end - source.start) / bar_samples)))
    if bars > source_bars:
        return source_tail_block(stems, source, bars, bar_samples, sample_rate, label)
    offset_bars = (int(rendered_bars) - int(bars)) % source_bars
    if offset_bars + bars > source_bars:
        offset_bars = max(0, source_bars - bars)
    start = source.start + offset_bars * bar_samples
    end = start + bars * bar_samples
    role_energy: dict[str, float] = {}
    role_spectrum: dict[str, dict[str, float]] = {}
    for stem in stems:
        chunk = stem.samples[start:end]
        role_energy[stem.role] = rms(chunk)
        role_spectrum[stem.role] = spectral_profile(chunk, sample_rate)
    return PhraseBlock(
        start=start,
        end=end,
        start_seconds=start / sample_rate,
        end_seconds=end / sample_rate,
        role_energy=role_energy,
        role_spectrum=role_spectrum,
        total_energy=sum(role_energy.values()),
    )


def select_fft_post_drop_window(
    stems: list[StemAudio],
    original_samples: int,
    bar_samples: int,
    sample_rate: int,
    transition_grid_bars: int,
    post_drop_bars: int,
    source_bars: int | None,
    explicit_start_bars: int | None,
    fallback: PhraseBlock,
) -> tuple[PhraseBlock, dict]:
    if post_drop_bars <= 0:
        raise ValueError("post_drop_bars must be at least 1 bar.")
    window = int(source_bars if source_bars is not None else post_drop_bars)
    if window <= 0:
        raise ValueError("post_drop_source_bars must be at least 1 bar.")
    if explicit_start_bars is not None:
        block = source_block_from_bars(
            stems=stems,
            start_bars=explicit_start_bars,
            bars=window,
            fallback=fallback,
            bar_samples=bar_samples,
            original_samples=original_samples,
            sample_rate=sample_rate,
            label="post_drop_source",
        )
        return block, {
            "method": "explicit_start",
            "selected_start_bars": explicit_start_bars,
            "selected_bars": window,
            "render_bars": post_drop_bars,
            "candidates": [],
        }

    grid = max(1, int(transition_grid_bars))
    complete_bars = original_samples // bar_samples
    if complete_bars < window:
        block = source_block_from_bars(
            stems=stems,
            start_bars=max(0, complete_bars - window),
            bars=min(window, complete_bars),
            fallback=fallback,
            bar_samples=bar_samples,
            original_samples=original_samples,
            sample_rate=sample_rate,
            label="post_drop_source",
        )
        return block, {
            "method": "fallback_source_too_short",
            "selected_start_bars": round(block.start / bar_samples, 3),
            "selected_bars": round((block.end - block.start) / bar_samples, 3),
            "render_bars": post_drop_bars,
            "candidates": [],
        }

    candidates: list[tuple[float, dict]] = []
    max_start = complete_bars - window
    for start_bars in range(0, max_start + 1, grid):
        block = source_block_from_bars(
            stems=stems,
            start_bars=start_bars,
            bars=window,
            fallback=fallback,
            bar_samples=bar_samples,
            original_samples=original_samples,
            sample_rate=sample_rate,
            label="post_drop_source_candidate",
        )
        child_blocks = analyze_grid_blocks(
            stems=stems,
            start=block.start,
            end=block.end,
            block_samples=grid * bar_samples,
            sample_rate=sample_rate,
        )
        score, metrics = score_post_drop_candidate(block, child_blocks, stems)
        payload = {
            "start_bars": start_bars,
            "end_bars": start_bars + window,
            "score": round(score, 6),
            **metrics,
        }
        candidates.append((score, payload))
    if not candidates:
        fallback_start = max(0, int(round(fallback.start / bar_samples / grid)) * grid)
        block = source_block_from_bars(
            stems=stems,
            start_bars=fallback_start,
            bars=window,
            fallback=fallback,
            bar_samples=bar_samples,
            original_samples=original_samples,
            sample_rate=sample_rate,
            label="post_drop_source",
        )
        return block, {"method": "fallback_no_candidates", "candidates": []}

    candidates.sort(key=lambda item: item[0], reverse=True)
    selected = candidates[0][1]
    block = source_block_from_bars(
        stems=stems,
        start_bars=int(selected["start_bars"]),
        bars=window,
        fallback=fallback,
        bar_samples=bar_samples,
        original_samples=original_samples,
        sample_rate=sample_rate,
        label="post_drop_source",
    )
    return block, {
        "method": "fft_rms_contiguous_window",
        "selected_start_bars": selected["start_bars"],
        "selected_bars": window,
        "render_bars": post_drop_bars,
        "selected_score": selected["score"],
        "candidates": [payload for _, payload in candidates[:8]],
    }


def analyze_grid_blocks(
    stems: list[StemAudio],
    start: int,
    end: int,
    block_samples: int,
    sample_rate: int,
) -> list[PhraseBlock]:
    blocks: list[PhraseBlock] = []
    cursor = start
    while cursor + block_samples <= end:
        role_energy: dict[str, float] = {}
        role_spectrum: dict[str, dict[str, float]] = {}
        for stem in stems:
            chunk = stem.samples[cursor : cursor + block_samples]
            role_energy[stem.role] = rms(chunk)
            role_spectrum[stem.role] = spectral_profile(chunk, sample_rate)
        blocks.append(
            PhraseBlock(
                start=cursor,
                end=cursor + block_samples,
                start_seconds=cursor / sample_rate,
                end_seconds=(cursor + block_samples) / sample_rate,
                role_energy=role_energy,
                role_spectrum=role_spectrum,
                total_energy=sum(role_energy.values()),
            )
        )
        cursor += block_samples
    return blocks


def score_post_drop_candidate(
    block: PhraseBlock,
    child_blocks: list[PhraseBlock],
    stems: list[StemAudio],
) -> tuple[float, dict]:
    bass_roles = [stem.role for stem in stems if base_role(stem.role) == "bass"]
    drum_roles = [stem.role for stem in stems if base_role(stem.role) in PERCUSSION_ROLES]
    fx_roles = [stem.role for stem in stems if base_role(stem.role) == "fx"]
    synth_roles = [stem.role for stem in stems if base_role(stem.role) in {"synths", "stabs", "other"}]

    def energy(source: PhraseBlock, roles: list[str]) -> float:
        return sum(source.role_energy.get(role, 0.0) for role in roles)

    bass_energy = energy(block, bass_roles)
    drum_energy = energy(block, drum_roles)
    fx_energy = energy(block, fx_roles)
    synth_energy = energy(block, synth_roles)
    transition_scores = [
        spectral_distance(left, right, roles=drum_roles + fx_roles + synth_roles)
        for left, right in zip(child_blocks, child_blocks[1:])
    ]
    transition_score = float(np.mean(transition_scores)) if transition_scores else 0.0
    consistency_penalty = float(np.std([child.total_energy for child in child_blocks])) if child_blocks else 0.0
    bass_floor_penalty = 0.04 if bass_energy <= 0.02 else 0.0
    score = (
        block.total_energy
        + bass_energy * 0.9
        + drum_energy * 0.45
        + fx_energy * 0.4
        + synth_energy * 0.25
        + transition_score * 0.35
        - consistency_penalty * 0.25
        - bass_floor_penalty
    )
    return score, {
        "total_energy": round(block.total_energy, 6),
        "bass_energy": round(bass_energy, 6),
        "drum_energy": round(drum_energy, 6),
        "fx_energy": round(fx_energy, 6),
        "synth_energy": round(synth_energy, 6),
        "transition_score": round(transition_score, 6),
        "consistency_penalty": round(consistency_penalty, 6),
    }


def spectral_distance(left: PhraseBlock, right: PhraseBlock, roles: list[str]) -> float:
    if not roles:
        return abs(right.total_energy - left.total_energy)
    distances = []
    for role in roles:
        left_profile = left.role_spectrum.get(role) or {}
        right_profile = right.role_spectrum.get(role) or {}
        distances.append(
            abs(right.role_energy.get(role, 0.0) - left.role_energy.get(role, 0.0))
            + abs(right_profile.get("low_ratio", 0.0) - left_profile.get("low_ratio", 0.0))
            + abs(right_profile.get("mid_ratio", 0.0) - left_profile.get("mid_ratio", 0.0))
            + abs(right_profile.get("high_ratio", 0.0) - left_profile.get("high_ratio", 0.0))
        )
    return float(np.mean(distances))


def source_block_from_bars(
    stems: list[StemAudio],
    start_bars: int | None,
    bars: int,
    fallback: PhraseBlock,
    bar_samples: int,
    original_samples: int,
    sample_rate: int,
    label: str,
) -> PhraseBlock:
    if bars <= 0:
        raise ValueError(f"{label} must be at least 1 bar.")
    if start_bars is None:
        start = snap_to_bar(fallback.start, bar_samples)
    else:
        if start_bars < 0:
            raise ValueError(f"{label} start bars must be >= 0.")
        start = int(start_bars * bar_samples)
    duration = int(bars * bar_samples)
    end = start + duration
    if end > original_samples:
        max_start_bar = max(0, (original_samples - duration) // bar_samples)
        raise ValueError(
            f"{label} source bars {start_bars if start_bars is not None else round(start / bar_samples, 3)}"
            f"-{round(end / bar_samples, 3)} exceed source length; choose start <= {max_start_bar} for {bars} bars."
        )
    role_energy: dict[str, float] = {}
    role_spectrum: dict[str, dict[str, float]] = {}
    for stem in stems:
        chunk = stem.samples[start:end]
        role_energy[stem.role] = rms(chunk)
        role_spectrum[stem.role] = spectral_profile(chunk, sample_rate)
    return PhraseBlock(
        start=start,
        end=end,
        start_seconds=start / sample_rate,
        end_seconds=end / sample_rate,
        role_energy=role_energy,
        role_spectrum=role_spectrum,
        total_energy=sum(role_energy.values()),
    )


def bars_to_samples_checked(bars: int, bar_samples: int, original_samples: int, label: str) -> int:
    if bars < 0:
        raise ValueError(f"{label} must be >= 0.")
    samples = int(bars * bar_samples)
    if samples > original_samples:
        max_bars = original_samples // bar_samples
        raise ValueError(f"{label}={bars} exceeds source length; max complete bars is {max_bars}.")
    return samples


def validate_bar_locked_house_args(
    *,
    phrase_bars: int,
    intro_bars: int | None,
    source_intro_bars: int,
    prepend_intro_bars: int,
    preserve_source_bars: int | None,
    preserve_source_start_bars: int,
    transition_grid_bars: int,
    pre_break_groove_bars: int,
    post_drop_groove_bars: int,
    second_half_extra_bars: int,
    effective_post_drop_groove_bars: int,
    pre_break_source_start_bars: int | None,
    pre_break_source_bars: int,
    breakdown_source_start_bars: int | None,
    breakdown_source_bars: int,
    post_drop_source_start_bars: int | None,
    post_drop_source_bars: int | None,
    blueprint_breakdown_bars: int,
    blueprint_outro_bars: int,
) -> None:
    """Reject non-house-grid section math in deterministic arrangement modes."""
    phrase = max(1, int(phrase_bars))
    house_unit = 8 if phrase >= 8 else phrase
    checks = {
        "intro_bars": intro_bars,
        "source_intro_bars": source_intro_bars,
        "prepend_intro_bars": prepend_intro_bars,
        "preserve_source_bars": preserve_source_bars,
        "preserve_source_start_bars": preserve_source_start_bars,
        "transition_grid_bars": transition_grid_bars,
        "pre_break_groove_bars": pre_break_groove_bars,
        "post_drop_groove_bars": post_drop_groove_bars,
        "second_half_extra_bars": second_half_extra_bars,
        "effective_post_drop_groove_bars": effective_post_drop_groove_bars,
        "pre_break_source_start_bars": pre_break_source_start_bars,
        "pre_break_source_bars": pre_break_source_bars,
        "breakdown_source_start_bars": breakdown_source_start_bars,
        "breakdown_source_bars": breakdown_source_bars,
        "post_drop_source_start_bars": post_drop_source_start_bars,
        "post_drop_source_bars": post_drop_source_bars,
        "blueprint_breakdown_bars": blueprint_breakdown_bars,
        "blueprint_outro_bars": blueprint_outro_bars,
    }
    for label, value in checks.items():
        if value is None or value == 0:
            continue
        if value < 0:
            raise ValueError(f"{label} must be >= 0.")
        if value % house_unit != 0:
            raise ValueError(
                f"{label}={value} is not house-grid locked. Use exact 8/16/32-bar boundaries."
            )
        if label.endswith("_source_bars") and value % phrase != 0:
            raise ValueError(
                f"{label}={value} is not source-phrase locked. Use a multiple of --phrase-bars ({phrase}) "
                "for copied source loops."
            )


def clamp_section_samples(value: int, available: int, minimum: int = 0) -> int:
    if available <= 0:
        return 0
    return max(minimum, min(int(value), int(available)))


def split_postdrop_sections(total_samples: int, bar_samples: int) -> list[int]:
    if total_samples <= 0:
        return []
    chunk = max(1, 16 * bar_samples)
    sections: list[int] = []
    remaining = total_samples
    while remaining > 0:
        take = min(chunk, remaining)
        sections.append(take)
        remaining -= take
    return sections


def analyze_blueprint_blocks(
    blueprint_samples: np.ndarray,
    start_sample: int,
    end_sample: int,
    phrase_samples: int,
    sample_rate: int,
) -> list[dict]:
    blocks: list[dict] = []
    cursor = start_sample
    while cursor < end_sample:
        end = min(end_sample, cursor + phrase_samples)
        if end - cursor >= phrase_samples * 0.25:
            blocks.append(
                {
                    "start": cursor,
                    "end": end,
                    "energy": rms(blueprint_samples[cursor:end]),
                }
            )
        cursor = end
    return blocks


def build_structured_blueprint_plan(
    raw_blocks: list[dict],
    preserve_samples: int,
    target_samples: int,
    sample_rate: int,
    selections: dict[str, PhraseBlock],
    bar_samples: int,
    breakdown_bars: int,
    outro_bars: int,
) -> list[dict]:
    extension = max(0, target_samples - preserve_samples)
    if not raw_blocks or extension <= 0:
        return []

    breakdown_duration = max(bar_samples, int(breakdown_bars * bar_samples))
    outro_duration = max(bar_samples, int(outro_bars * bar_samples))
    latest_breakdown_start = max(preserve_samples, target_samples - outro_duration - breakdown_duration)
    breakdown_candidates = [
        block
        for block in raw_blocks
        if block["start"] >= preserve_samples and block["start"] <= latest_breakdown_start
    ]
    if not breakdown_candidates:
        breakdown_candidates = raw_blocks
    breakdown_block = min(breakdown_candidates, key=lambda block: block["energy"])
    breakdown_start = snap_to_bar(breakdown_block["start"], bar_samples)
    breakdown_start = max(preserve_samples, min(breakdown_start, latest_breakdown_start))
    breakdown_end = min(target_samples, breakdown_start + breakdown_duration)

    outro_start = max(breakdown_end, target_samples - outro_duration)
    if outro_start < breakdown_end:
        outro_start = breakdown_end

    sections: list[dict] = []
    if breakdown_start > preserve_samples:
        sections.append(
            make_section(
                name="continue_groove",
                start=preserve_samples,
                end=breakdown_start,
                source=selections["full_groove"],
                mute_roles=set(),
                fade_out_roles=set(),
                sample_rate=sample_rate,
                blueprint_energy=energy_for_range(raw_blocks, preserve_samples, breakdown_start),
            )
        )
    if breakdown_end > breakdown_start:
        sections.append(
            make_section(
                name="stripped_breakdown",
                start=breakdown_start,
                end=breakdown_end,
                source=selections["breakdown"],
                mute_roles={"bass", "vocals"},
                fade_out_roles=set(),
                sample_rate=sample_rate,
                blueprint_energy=energy_for_range(raw_blocks, breakdown_start, breakdown_end),
                breakdown_drum_mode="tops",
            )
        )
    if outro_start > breakdown_end:
        sections.append(
            make_section(
                name="return_to_groove",
                start=breakdown_end,
                end=outro_start,
                source=selections.get("developed_groove") or selections["full_groove"],
                mute_roles={"vocals"},
                fade_out_roles=set(),
                sample_rate=sample_rate,
                blueprint_energy=energy_for_range(raw_blocks, breakdown_end, outro_start),
            )
        )
    if target_samples > outro_start:
        sections.append(
            make_section(
                name="dj_outro",
                start=outro_start,
                end=target_samples,
                source=selections["drums"],
                mute_roles={"bass", "kick", "vocals"},
                fade_out_roles=set(),
                sample_rate=sample_rate,
                blueprint_energy=energy_for_range(raw_blocks, outro_start, target_samples),
            )
        )
    return sections


def make_section(
    name: str,
    start: int,
    end: int,
    source: PhraseBlock,
    mute_roles: set[str],
    fade_out_roles: set[str],
    sample_rate: int,
    blueprint_energy: float,
    breakdown_drum_mode: str = "tops",
) -> dict:
    return {
        "name": name,
        "duration": max(0, end - start),
        "source": source,
        "mute_roles": mute_roles,
        "fade_out_roles": fade_out_roles,
        "breakdown_drum_mode": normalize_breakdown_drum_mode(breakdown_drum_mode),
        "blueprint_start_seconds": start / sample_rate,
        "blueprint_end_seconds": end / sample_rate,
        "blueprint_energy": blueprint_energy,
    }


def energy_for_range(raw_blocks: list[dict], start: int, end: int) -> float:
    overlaps = []
    for block in raw_blocks:
        overlap = max(0, min(end, block["end"]) - max(start, block["start"]))
        if overlap > 0:
            overlaps.append((block["energy"], overlap))
    if not overlaps:
        return 0.0
    total = sum(weight for _, weight in overlaps)
    return float(sum(energy * weight for energy, weight in overlaps) / total)


def snap_to_bar(sample: int, bar_samples: int) -> int:
    if bar_samples <= 0:
        return sample
    return int(round(sample / bar_samples) * bar_samples)


def merge_adjacent_sections(section_plan: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for section in section_plan:
        if (
            merged
            and merged[-1]["name"] == section["name"]
            and merged[-1]["source"] == section["source"]
            and merged[-1]["mute_roles"] == section["mute_roles"]
            and merged[-1]["fade_out_roles"] == section["fade_out_roles"]
        ):
            merged[-1]["duration"] += section["duration"]
            if "blueprint_end_seconds" in section:
                merged[-1]["blueprint_end_seconds"] = section["blueprint_end_seconds"]
        else:
            merged.append(section.copy())
    return merged


def render_arranged_stem(
    stem: StemAudio,
    selections: dict[str, PhraseBlock],
    section_plan: list[dict],
    target_samples: int,
    prepend_intro_samples: int,
    preserve_source_start_samples: int,
    preserve_samples: int,
) -> np.ndarray:
    arranged = np.zeros((0, 2), dtype=np.float32)
    if prepend_intro_samples > 0:
        arranged = render_section_for_stem(
            stem=stem,
            section={
                "name": "dj_intro",
                "duration": prepend_intro_samples,
                "source": selections["intro"],
                "mute_roles": {"bass", "kick", "vocals"},
                "fade_out_roles": set(),
            },
        )
    preserve_end = preserve_source_start_samples + preserve_samples
    arranged = np.concatenate(
        [arranged, np.asarray(stem.samples[preserve_source_start_samples:preserve_end], dtype=np.float32)],
        axis=0,
    )
    return append_sections_for_stem(arranged, stem, section_plan, target_samples)


def append_sections_for_stem(arranged: np.ndarray, stem: StemAudio, section_plan: list[dict], target_samples: int) -> np.ndarray:
    first_append = True
    for section in section_plan:
        if len(arranged) >= target_samples:
            break
        duration = min(section["duration"], target_samples - len(arranged))
        if duration <= 0:
            continue
        section_for_duration = section.copy()
        section_for_duration["duration"] = duration
        segment = render_section_for_stem(stem, section_for_duration)
        segment = apply_fade_in(segment, seconds=0.01, sample_rate=stem.sample_rate) if first_append else segment
        arranged = np.concatenate([arranged, segment], axis=0)
        first_append = False
    if len(arranged) < target_samples:
        pad = np.zeros((target_samples - len(arranged), 2), dtype=np.float32)
        arranged = np.concatenate([arranged, pad], axis=0)
    return arranged[:target_samples]


def render_section_for_stem(stem: StemAudio, section: dict) -> np.ndarray:
    duration = int(section["duration"])
    role = base_role(stem.role)
    if role in section["mute_roles"]:
        return np.zeros((duration, 2), dtype=np.float32)
    segment = build_repeated_segment(stem.samples, section["source"], duration)
    if section["name"] == "stripped_breakdown" and role not in PERCUSSION_ROLES | {"fx", "stabs", "synths", "other"}:
        segment *= 0.0
    if section["name"] == "stripped_breakdown" and role in PERCUSSION_ROLES:
        segment = apply_breakdown_drum_mode(
            segment,
            sample_rate=stem.sample_rate,
            role=role,
            mode=section.get("breakdown_drum_mode", "tops"),
        )
    if role in section["fade_out_roles"]:
        segment = apply_fade_out(segment)
    if section["name"] == "stripped_breakdown" and role in {"stabs", "synths", "other"}:
        segment *= 0.45
    if section["name"] == "dj_intro" and role in {"stabs", "synths", "other", "fx"}:
        segment *= 0.35
    if section["name"] == "dj_outro" and role in {"stabs", "synths", "other", "fx"}:
        segment *= 0.5
    return np.asarray(segment, dtype=np.float32)


def apply_breakdown_drum_mode(samples: np.ndarray, sample_rate: int, role: str, mode: str) -> np.ndarray:
    mode = normalize_breakdown_drum_mode(mode)
    if mode == "none":
        return np.zeros_like(samples, dtype=np.float32)
    if mode == "full":
        return np.asarray(samples, dtype=np.float32)
    if mode == "tops":
        return apply_breakdown_tops(samples, sample_rate, role)
    midpoint = len(samples) // 2
    shaped = np.zeros_like(samples, dtype=np.float32)
    if mode == "half-tops":
        shaped[midpoint:] = apply_breakdown_tops(samples[midpoint:], sample_rate, role)
    elif mode == "half-full":
        shaped[midpoint:] = samples[midpoint:]
    return shaped.astype(np.float32)


def apply_breakdown_tops(samples: np.ndarray, sample_rate: int, role: str) -> np.ndarray:
    if role == "kick":
        return np.zeros_like(samples, dtype=np.float32)
    if role == "drums":
        return apply_breakdown_drum_shape(samples, sample_rate)
    return np.asarray(samples, dtype=np.float32)


def apply_breakdown_drum_shape(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    """Keep top percussion in a breakdown while suppressing the kick band."""
    if len(samples) < sample_rate:
        return samples
    high = highpass_filter(samples, sample_rate, cutoff_hz=180.0)
    midpoint = len(high) // 2
    shaped = high.copy()
    shaped[:midpoint] *= 0.58
    shaped[midpoint:] *= np.linspace(0.62, 0.9, len(shaped) - midpoint, dtype=np.float32)[:, None]
    return shaped.astype(np.float32)


def highpass_filter(samples: np.ndarray, sample_rate: int, cutoff_hz: float) -> np.ndarray:
    nyquist = sample_rate / 2.0
    if cutoff_hz <= 0 or cutoff_hz >= nyquist:
        return samples
    sos = signal.butter(4, cutoff_hz / nyquist, btype="highpass", output="sos")
    filtered = signal.sosfiltfilt(sos, samples, axis=0)
    return np.asarray(filtered, dtype=np.float32)


def lowpass_filter(samples: np.ndarray, sample_rate: int, cutoff_hz: float) -> np.ndarray:
    nyquist = sample_rate / 2.0
    if cutoff_hz <= 0 or cutoff_hz >= nyquist:
        return samples
    sos = signal.butter(4, cutoff_hz / nyquist, btype="lowpass", output="sos")
    filtered = signal.sosfiltfilt(sos, samples, axis=0)
    return np.asarray(filtered, dtype=np.float32)


def write_pseudo_drum_substems(out_dir: Path, drum_role: str, sample_rate: int, samples: np.ndarray) -> None:
    prefix = "drums" if drum_role == "drums" else drum_role
    kick = lowpass_filter(samples, sample_rate, cutoff_hz=170.0)
    top = highpass_filter(samples, sample_rate, cutoff_hz=170.0)
    write_wav(out_dir / f"{prefix}-kick-pseudo.wav", sample_rate, kick)
    write_wav(out_dir / f"{prefix}-tops-pseudo.wav", sample_rate, top)


def build_repeated_segment(samples: np.ndarray, block: PhraseBlock, duration: int) -> np.ndarray:
    source = samples[block.start:block.end]
    if len(source) <= 0:
        return np.zeros((duration, 2), dtype=np.float32)
    chunks = []
    remaining = duration
    while remaining > 0:
        take = min(remaining, len(source))
        chunks.append(source[:take])
        remaining -= take
    return np.concatenate(chunks, axis=0).astype(np.float32)


def rms(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(samples.astype(np.float64)))))


def apply_fade_in(samples: np.ndarray, seconds: float, sample_rate: int) -> np.ndarray:
    count = min(len(samples), max(1, int(round(seconds * sample_rate))))
    out = samples.copy()
    out[:count] *= np.linspace(0.0, 1.0, count, dtype=np.float32)[:, None]
    return out


def apply_fade_out(samples: np.ndarray) -> np.ndarray:
    out = samples.copy()
    if len(out) <= 0:
        return out
    out *= np.linspace(1.0, 0.0, len(out), dtype=np.float32)[:, None]
    return out


def sum_role_outputs(role_outputs: dict[str, np.ndarray], target_samples: int) -> np.ndarray:
    mix = np.zeros((target_samples, 2), dtype=np.float32)
    for samples in role_outputs.values():
        mix[: len(samples)] += samples[:target_samples]
    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if peak > 0.98:
        mix *= 0.98 / peak
    return mix


def write_wav(path: Path, sample_rate: int, samples: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(samples, -1.0, 1.0)
    wavfile.write(str(path), sample_rate, np.asarray(clipped * 32767.0, dtype=np.int16))


def block_to_json(block: PhraseBlock) -> dict:
    return {
        "start_seconds": round(block.start_seconds, 3),
        "end_seconds": round(block.end_seconds, 3),
        "total_energy": round(block.total_energy, 6),
        "role_energy": {role: round(value, 6) for role, value in sorted(block.role_energy.items())},
        "role_spectrum": {
            role: {key: round(value, 6) for key, value in sorted(profile.items())}
            for role, profile in sorted(block.role_spectrum.items())
        },
    }


def section_plan_to_json(section_plan: list[dict], sample_rate: int, bar_samples: int) -> list[dict]:
    cursor = 0
    payload = []
    for section in section_plan:
        duration = int(section["duration"])
        source = section["source"]
        payload.append(
            {
                "name": section["name"],
                "relative_start_seconds": round(cursor / sample_rate, 3),
                "duration_seconds": round(duration / sample_rate, 3),
                "relative_start_bars": round(cursor / bar_samples, 3) if bar_samples else None,
                "duration_bars": round(duration / bar_samples, 3) if bar_samples else None,
                "source_start_bars": round(source.start / bar_samples, 3) if bar_samples else None,
                "source_end_bars": round(source.end / bar_samples, 3) if bar_samples else None,
                "source_block": block_to_json(section["source"]),
                "mute_roles": sorted(section["mute_roles"]),
                "fade_out_roles": sorted(section["fade_out_roles"]),
                "breakdown_drum_mode": section.get("breakdown_drum_mode"),
                "blueprint_start_seconds": round(section["blueprint_start_seconds"], 3)
                if "blueprint_start_seconds" in section
                else None,
                "blueprint_end_seconds": round(section["blueprint_end_seconds"], 3)
                if "blueprint_end_seconds" in section
                else None,
                "blueprint_energy": round(section["blueprint_energy"], 6)
                if "blueprint_energy" in section
                else None,
            }
        )
        cursor += duration
    return payload


def arrangement_warnings(
    stems: list[StemAudio],
    ignored: list[dict],
    include_vocals: bool,
    target_samples: int,
    original_samples: int,
) -> list[str]:
    warnings = [
        "v0 arranger reuses copied phrase blocks only; it does not create new transitions or new FX.",
        "Review joins by ear before using the output as a final arrangement.",
    ]
    if not include_vocals and any(item.get("role") == "vocals" for item in ignored):
        warnings.append("Vocal stems were muted by default.")
    if target_samples <= original_samples:
        warnings.append("Target duration is not longer than the source; output mainly preserves the original stems.")
    if not any(base_role(stem.role) == "bass" for stem in stems):
        warnings.append("No bass stem was detected; continuation will not include a dedicated bass lane.")
    if not any(base_role(stem.role) in PERCUSSION_ROLES for stem in stems):
        warnings.append("No drum/percussion stem was detected; phrase selection may be weak.")
    return warnings


def render_report(plan: dict) -> str:
    lines = [
        "# Continuation Arrangement Report",
        "",
        f"- Engine: `{plan['engine']}`",
        f"- BPM: {plan['bpm']}",
        f"- Original duration: {plan['original_duration_seconds']}s",
        f"- Continue from: {plan['continue_from_seconds']}s",
        f"- Target duration: {plan['target_duration_seconds']}s",
        f"- Bar length: {plan['bar_seconds']}s",
        "",
        "## Section Controls",
        f"- Desired intro: {plan.get('intro_bars') if plan.get('intro_bars') is not None else 'not set'} bars",
        f"- Source intro already present: {plan.get('source_intro_bars', 0)} bars",
        f"- Prepended intro: {plan.get('prepend_intro_bars', 0)} bars",
        f"- Preserved source starts at: {plan.get('preserve_source_start_bars', 0)} bars",
        f"- Transition grid: {plan.get('transition_grid_bars')} bars",
        f"- Pre-break groove: {plan.get('pre_break_groove_bars')} bars",
        f"- Post-drop groove: {plan.get('post_drop_groove_bars')} bars",
        f"- Second-half extra: {plan.get('second_half_extra_bars', 0)} bars",
        f"- Effective post-drop groove: {plan.get('effective_post_drop_groove_bars', plan.get('post_drop_groove_bars'))} bars",
        f"- Breakdown: {plan.get('breakdown_bars') if plan.get('breakdown_bars') is not None else plan.get('breakdown_source_bars')} bars",
        f"- Breakdown drums: {plan.get('breakdown_drum_mode')}",
        f"- Outro: {plan.get('outro_bars') if plan.get('outro_bars') is not None else plan.get('blueprint_outro_bars')} bars",
        "",
        "## Stems",
    ]
    for stem in plan["stems"]:
        lines.append(f"- `{stem['role']}` from `{stem['source_name']}` ({stem['duration_seconds']}s)")
    if plan.get("prepend_intro_bars", 0):
        intro_seconds = plan["prepend_intro_bars"] * plan["bar_seconds"]
        lines.extend(["", "## Prepended Sections"])
        target_intro = plan.get("intro_bars")
        if target_intro is not None:
            lines.append(
                f"- dj_intro: 0.00s-{intro_seconds:.2f}s ({plan['prepend_intro_bars']} prepended bars), "
                f"target intro {target_intro} bars with {plan.get('source_intro_bars', 0)} bars already in the preserved source"
            )
        else:
            lines.append(f"- dj_intro: 0.00s-{intro_seconds:.2f}s ({plan['prepend_intro_bars']} bars), source selected from Suno intro material")
    lines.extend(["", "## Preserved Source"])
    preserved_start = plan.get("prepend_intro_bars", 0)
    preserved_end = preserved_start + plan["continue_from_seconds"] / plan["bar_seconds"] if plan.get("bar_seconds") else preserved_start
    source_start_bars = plan.get("preserve_source_start_bars", 0)
    source_end_bars = source_start_bars + plan["continue_from_seconds"] / plan["bar_seconds"] if plan.get("bar_seconds") else source_start_bars
    lines.append(
        f"- original_suno: output bars {preserved_start:.1f}-{preserved_end:.1f}, "
        f"source bars {source_start_bars:.1f}-{source_end_bars:.1f}, "
        f"{plan.get('preserve_source_start_seconds', 0.0):.2f}s-{plan.get('preserve_source_end_seconds', plan['continue_from_seconds']):.2f}s"
    )
    lines.extend(["", "## Appended Sections"])
    absolute = plan["continue_from_seconds"] + plan.get("prepend_intro_bars", 0) * plan["bar_seconds"]
    for section in plan["sections"]:
        start = absolute + section["relative_start_seconds"]
        end = start + section["duration_seconds"]
        start_bar = start / plan["bar_seconds"] if plan.get("bar_seconds") else 0.0
        end_bar = end / plan["bar_seconds"] if plan.get("bar_seconds") else 0.0
        drum_mode = (
            f", breakdown_drum_mode={section['breakdown_drum_mode']}"
            if section["name"] == "stripped_breakdown"
            else ""
        )
        lines.append(
            f"- {section['name']}: bars {start_bar:.1f}-{end_bar:.1f} ({section['duration_bars']:.1f} bars), "
            f"{start:.2f}s-{end:.2f}s, source bars {section['source_start_bars']:.1f}-{section['source_end_bars']:.1f}, source "
            f"{section['source_block']['start_seconds']:.2f}s-{section['source_block']['end_seconds']:.2f}s, "
            f"mute={section['mute_roles'] or 'none'}{drum_mode}"
        )
    lines.extend(["", "## Warnings"])
    for warning in plan["warnings"]:
        lines.append(f"- {warning}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Continue a generated stem arrangement by reusing its own phrase blocks.")
    parser.add_argument("--input-dir", required=True, help="Folder containing Suno/ACE WAV stems.")
    parser.add_argument("--output-dir", required=True, help="Folder for arranged WAVs and reports.")
    parser.add_argument("--target-duration", type=float, default=360.0, help="Target output duration in seconds.")
    parser.add_argument("--continue-from", default="auto", help="'auto'/'end' or seconds to preserve before appending.")
    parser.add_argument("--bpm", type=float, default=None, help="Optional BPM override.")
    parser.add_argument("--phrase-bars", type=int, default=16, help="Phrase block size used for copied source material.")
    parser.add_argument("--include-vocals", action="store_true", help="Include vocal stems instead of muting them.")
    parser.add_argument("--blueprint-audio", default=None, help="Optional full-length ACE/demo WAV used as the continuation energy blueprint.")
    parser.add_argument("--intro-bars", type=int, default=None, help="Desired total DJ intro length in bars. The arranger prepends only the missing bars.")
    parser.add_argument("--source-intro-bars", type=int, default=0, help="Bars of intro already present at the start of the preserved source.")
    parser.add_argument("--prepend-intro-bars", type=int, default=0, help="Bars of DJ intro to prepend from Suno's own intro/top-percussion material.")
    parser.add_argument("--source-end-trim-bars", type=int, default=0, help="Beat-aligned bars to remove from the end of the Suno source before continuing.")
    parser.add_argument("--breakdown-bars", type=int, default=None, help="Desired breakdown length in bars. In strict modes this also sets the copied breakdown source block length.")
    parser.add_argument(
        "--breakdown-drum-mode",
        default="tops",
        choices=sorted(BREAKDOWN_DRUM_MODES),
        help="Drum behavior during breakdown: tops, none, full, half-tops, or half-full.",
    )
    parser.add_argument("--outro-bars", type=int, default=None, help="Desired DJ outro length in bars for modes that render an outro.")
    parser.add_argument("--blueprint-breakdown-bars", type=int, default=16, help="Breakdown length in bars when using a blueprint.")
    parser.add_argument("--blueprint-outro-bars", type=int, default=16, help="Outro length in bars when using a blueprint.")
    parser.add_argument("--drum-substems", action="store_true", help="Use optional DrumSep engine to replace drums with kick/snare/cymbals/toms before arranging.")
    parser.add_argument("--arrangement-mode", default="blueprint", choices=["blueprint", "suno-blocks", "prebreak-diagnostic", "club-second-half", "reference-blueprint"], help="Arrangement strategy: blueprint energy heuristic, explicit Suno block sequence, strict pre-break diagnostic, FFT-scored club second half, or reference-driven spectral blueprint.")
    parser.add_argument("--transition-grid-bars", type=int, default=16, help="Grid size for detecting safe source transition boundaries.")
    parser.add_argument("--pre-break-groove-bars", type=int, default=32, help="Developed Suno groove bars before breakdown in suno-blocks mode.")
    parser.add_argument("--post-drop-groove-bars", type=int, default=48, help="Post-break/drop groove length in bars for club-second-half mode.")
    parser.add_argument("--second-half-extra-bars", type=int, default=0, help="Extra post-drop groove bars to append in club-second-half mode, e.g. 32 for a longer second half.")
    parser.add_argument("--preserve-source-bars", type=int, default=None, help="Prebreak diagnostic: exact number of source bars to preserve before appended sections.")
    parser.add_argument("--preserve-source-start-bars", type=int, default=0, help="Zero-based source bar to start preserving from, useful for deleting bad leading Suno material before adding a clean DJ intro.")
    parser.add_argument("--pre-break-source-start-bars", type=int, default=None, help="Prebreak diagnostic: zero-based source bar where the developed phrase starts.")
    parser.add_argument("--pre-break-source-bars", type=int, default=16, help="Prebreak diagnostic: exact source phrase length in bars for the developed phrase.")
    parser.add_argument("--breakdown-source-start-bars", type=int, default=None, help="Prebreak diagnostic: zero-based source bar where the breakdown source phrase starts.")
    parser.add_argument("--breakdown-source-bars", type=int, default=16, help="Prebreak diagnostic: exact breakdown source/render length in bars.")
    parser.add_argument("--post-drop-source-start-bars", type=int, default=None, help="Club second half: optional zero-based source bar where the post-drop groove source window starts; omit for FFT/RMS selection.")
    parser.add_argument("--post-drop-source-bars", type=int, default=None, help="Club second half: optional source window length for the post-drop groove. Allows a developed source window to repeat for a longer rendered second half.")
    parser.add_argument("--percussion-reference-input-dir", default=None, help="Optional folder of pre-separated kick/snare/hihats/cymbals/toms stems to render through the same arrangement as Ableton reference guides only.")
    args = parser.parse_args()

    try:
        payload = arrange_continuation(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            target_duration=args.target_duration,
            continue_from=args.continue_from,
            bpm=args.bpm,
            phrase_bars=args.phrase_bars,
            include_vocals=args.include_vocals,
            blueprint_audio=args.blueprint_audio,
            intro_bars=args.intro_bars,
            source_intro_bars=args.source_intro_bars,
            prepend_intro_bars=args.prepend_intro_bars,
            source_end_trim_bars=args.source_end_trim_bars,
            breakdown_bars=args.breakdown_bars,
            breakdown_drum_mode=args.breakdown_drum_mode,
            outro_bars=args.outro_bars,
            blueprint_breakdown_bars=args.blueprint_breakdown_bars,
            blueprint_outro_bars=args.blueprint_outro_bars,
            drum_substems=args.drum_substems,
            arrangement_mode=args.arrangement_mode,
            transition_grid_bars=args.transition_grid_bars,
            pre_break_groove_bars=args.pre_break_groove_bars,
            post_drop_groove_bars=args.post_drop_groove_bars,
            second_half_extra_bars=args.second_half_extra_bars,
            preserve_source_bars=args.preserve_source_bars,
            preserve_source_start_bars=args.preserve_source_start_bars,
            pre_break_source_start_bars=args.pre_break_source_start_bars,
            pre_break_source_bars=args.pre_break_source_bars,
            breakdown_source_start_bars=args.breakdown_source_start_bars,
            breakdown_source_bars=args.breakdown_source_bars,
            post_drop_source_start_bars=args.post_drop_source_start_bars,
            post_drop_source_bars=args.post_drop_source_bars,
            percussion_reference_input_dir=args.percussion_reference_input_dir,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": {"message": str(exc)}}, indent=2), file=sys.stdout)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
