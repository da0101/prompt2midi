#!/usr/bin/env python3
"""Producer-oriented arrangement section construction."""
from __future__ import annotations


def build_arrangement_sections(analysis: dict, duration: float, total_bars: int, bar_seconds: float) -> dict:
    raw_sections = ((analysis.get("structure") or {}).get("sections") or [])
    if raw_sections:
        sections = _sections_from_analysis(raw_sections, duration, bar_seconds)
        sections = _merge_micro_sections(sections, min_seconds=max(bar_seconds * 2.0, 4.0))
        normalized_sections = _normalize_phrase_grid(sections, duration, total_bars, bar_seconds)
        sections = normalized_sections or _split_overlong_sections(sections, max_bars=32, min_tail_bars=8)
        method = f"{(analysis.get('structure') or {}).get('method', 'structure_analysis')}+bar_alignment"
        limitations = [
            "Section boundaries are aligned to the detected BPM grid.",
            "Tiny transition fragments are merged toward the nearest useful producer section.",
            "Long club references are normalized toward 8/16/32-bar producer phrases when the beat grid is stable.",
            "Overlong detected spans are split into phrase-sized sections so full-song rendering can preserve the arrangement arc.",
            "Labels are producer-role labels inferred from energy, position, and available structure labels.",
        ]
    else:
        sections = _fallback_sections(duration, total_bars, bar_seconds)
        method = "fallback_bar_grid"
        limitations = [
            "No external full-song structure model was available, so sections were estimated from duration and bar grid.",
            "Install All-In-One Music Structure Analyzer for stronger beat, downbeat, and functional section labels.",
        ]

    _repair_section_edges(sections, total_bars, duration, bar_seconds)
    _annotate_sections(sections)
    return {"sections": sections, "method": method, "limitations": limitations}


def _sections_from_analysis(raw_sections: list[dict], duration: float, bar_seconds: float) -> list[dict]:
    sections: list[dict] = []
    for index, raw in enumerate(raw_sections):
        start = max(0.0, _number(raw.get("start"), 0.0))
        end = max(start + 0.1, min(duration, _number(raw.get("end"), duration)))
        sections.append(
            {
                "id": f"section_{index + 1}",
                "source_label": str(raw.get("label") or chr(65 + min(index, 25))),
                "source_kind": str(raw.get("source") or "structure"),
                "detected_start_seconds": round(start, 3),
                "detected_end_seconds": round(end, 3),
                "start_seconds": round(start, 3),
                "end_seconds": round(end, 3),
                "start_bar": max(1, round(start / bar_seconds) + 1),
                "end_bar": max(1, round(end / bar_seconds)),
                "energy": _number(raw.get("energy"), 0.0),
                "source_confidence": _number(raw.get("confidence"), 0.65 if raw.get("source") == "allin1" else 0.5),
            }
        )
    return sections


def _merge_micro_sections(sections: list[dict], min_seconds: float) -> list[dict]:
    if len(sections) <= 1:
        return sections
    output: list[dict] = []
    pending: list[dict] = []
    for section in sections:
        if _duration(section) < min_seconds:
            pending.append(dict(section))
            continue
        current = dict(section)
        if pending:
            if output and _duration(output[-1]) > _duration(current) * 1.25:
                _absorb_cluster(current, pending, at_start=True)
            elif output:
                _absorb_cluster(output[-1], pending, at_start=False)
            else:
                _absorb_cluster(current, pending, at_start=True)
            pending = []
        output.append(current)
    if pending:
        if output:
            _absorb_cluster(output[-1], pending, at_start=False)
        else:
            output.extend(pending)
    return output


def _split_overlong_sections(sections: list[dict], max_bars: int, min_tail_bars: int) -> list[dict]:
    split: list[dict] = []
    original_count = len(sections)
    for index, section in enumerate(sections):
        bars = _bar_count(section)
        if bars <= max_bars:
            split.append(dict(section))
            continue
        chunks = _phrase_chunks(bars, max_bars=max_bars, min_tail_bars=min_tail_bars, is_first=index == 0)
        cursor = int(section["start_bar"])
        for chunk_index, chunk_bars in enumerate(chunks):
            item = dict(section)
            item["start_bar"] = cursor
            item["end_bar"] = cursor + chunk_bars - 1
            item["start_seconds"] = round(_number(section["start_seconds"], 0.0) + (cursor - int(section["start_bar"])) * _section_bar_seconds(section), 3)
            item["end_seconds"] = round(item["start_seconds"] + chunk_bars * _section_bar_seconds(section), 3)
            item["detected_start_seconds"] = item["start_seconds"]
            item["detected_end_seconds"] = item["end_seconds"]
            item["source_kind"] = "phrase_subdivision"
            item["source_confidence"] = min(_number(section.get("source_confidence"), 0.5), 0.48)
            item["source_label"] = _subdivision_label(index, original_count, chunk_index, len(chunks), str(section.get("source_label") or ""))
            item["structural_role_hint"] = item["source_label"]
            split.append(item)
            cursor += chunk_bars
    return split


def _normalize_phrase_grid(sections: list[dict], duration: float, total_bars: int, bar_seconds: float) -> list[dict] | None:
    if total_bars < 96 or len(sections) < 4:
        return None
    plan = _best_phrase_plan(sections, total_bars)
    if not plan:
        return None
    output: list[dict] = []
    cursor = 1
    for index, chunk_bars in enumerate(plan):
        start_bar = cursor
        end_bar = min(total_bars, start_bar + chunk_bars - 1)
        source = _dominant_source_for_bars(sections, start_bar, end_bar)
        item = dict(source)
        item["id"] = f"section_{index + 1}"
        item["source_kind"] = "phrase_grid_normalized"
        item["source_confidence"] = max(_number(source.get("source_confidence"), 0.5), 0.72)
        item["start_bar"] = start_bar
        item["end_bar"] = end_bar
        item["start_seconds"] = round((start_bar - 1) * bar_seconds, 3)
        item["end_seconds"] = round(min(duration, end_bar * bar_seconds), 3)
        item["source_detected_start_seconds"] = round(_number(source.get("detected_start_seconds"), item["start_seconds"]), 3)
        item["source_detected_end_seconds"] = round(_number(source.get("detected_end_seconds"), item["end_seconds"]), 3)
        item["detected_start_seconds"] = item["start_seconds"]
        item["detected_end_seconds"] = item["end_seconds"]
        item["source_label"] = _phrase_label(index, len(plan), int(chunk_bars), str(source.get("source_label") or ""))
        item["structural_role_hint"] = item["source_label"]
        output.append(item)
        cursor = end_bar + 1
    return output


def _best_phrase_plan(sections: list[dict], total_bars: int) -> list[int] | None:
    observed_intro = _bar_count(sections[0])
    observed_outro = _bar_count(sections[-1])
    best: tuple[float, list[int]] | None = None
    for intro in (8, 16, 32):
        if intro >= total_bars - 24:
            continue
        for outro in range(8, 33):
            body_bars = total_bars - intro - outro
            if body_bars < 16:
                continue
            body = _body_phrase_chunks(body_bars)
            if not body:
                continue
            plan = [intro] + body + [outro]
            score = abs(intro - observed_intro) * 0.35
            score += abs(outro - observed_outro) * 0.12
            if total_bars >= 128 and intro < 16:
                score += 0.8
            score += sum(0.08 for bars in body if bars == 16)
            score += len(plan) * 0.015
            if best is None or score < best[0]:
                best = (score, plan)
    return best[1] if best else None


def _body_phrase_chunks(total_bars: int) -> list[int] | None:
    best: tuple[int, int, list[int]] | None = None
    for count_32 in range(total_bars // 32, -1, -1):
        remaining = total_bars - count_32 * 32
        if remaining % 16 != 0:
            continue
        count_16 = remaining // 16
        chunks = [32] * count_32 + [16] * count_16
        if not chunks:
            continue
        score = (count_16, len(chunks), chunks)
        if best is None or score < best:
            best = score
    return best[2] if best else None


def _dominant_source_for_bars(sections: list[dict], start_bar: int, end_bar: int) -> dict:
    best = sections[0]
    best_overlap = -1
    for section in sections:
        overlap = min(end_bar, int(section.get("end_bar") or end_bar)) - max(start_bar, int(section.get("start_bar") or start_bar)) + 1
        if overlap > best_overlap:
            best = section
            best_overlap = overlap
    return best


def _phrase_label(index: int, count: int, bars: int, source_label: str) -> str:
    lower = source_label.lower()
    if index == 0:
        return "intro"
    if index == count - 1:
        return "outro"
    if "break" in lower:
        return "breakdown"
    if bars == 16 and index > 1:
        return "variation"
    return "groove"


def _phrase_chunks(total_bars: int, max_bars: int, min_tail_bars: int, is_first: bool) -> list[int]:
    chunks: list[int] = []
    remaining = total_bars
    if is_first and remaining > max_bars:
        chunks.append(min(16, remaining - min_tail_bars))
        remaining -= chunks[-1]
    while remaining > max_bars:
        next_chunk = max_bars
        if remaining - next_chunk < min_tail_bars:
            next_chunk = max(min_tail_bars, remaining // 2)
        chunks.append(next_chunk)
        remaining -= next_chunk
    if remaining > 0:
        chunks.append(remaining)
    return [max(1, int(item)) for item in chunks]


def _fallback_sections(duration: float, total_bars: int, bar_seconds: float) -> list[dict]:
    if total_bars <= 32:
        ranges = [(1, total_bars, "main")]
    elif total_bars <= 80:
        intro = min(16, total_bars // 4)
        outro = min(16, total_bars // 5)
        ranges = [(1, intro, "intro"), (intro + 1, total_bars - outro, "main"), (total_bars - outro + 1, total_bars, "outro")]
    else:
        intro = 16
        groove_a = min(64, max(32, total_bars // 3))
        breakdown_start = min(total_bars - 32, max(groove_a + 1, round(total_bars * 0.55)))
        breakdown_end = min(total_bars - 17, breakdown_start + 16)
        outro_start = max(breakdown_end + 17, total_bars - 15)
        ranges = [
            (1, intro, "intro"),
            (intro + 1, groove_a, "groove"),
            (groove_a + 1, breakdown_start - 1, "variation"),
            (breakdown_start, breakdown_end, "breakdown"),
            (breakdown_end + 1, outro_start - 1, "drop"),
            (outro_start, total_bars, "outro"),
        ]
    return [_section_from_range(index, start, end, label, duration, bar_seconds) for index, (start, end, label) in enumerate(ranges)]


def _section_from_range(index: int, start_bar: int, end_bar: int, label: str, duration: float, bar_seconds: float) -> dict:
    start = (start_bar - 1) * bar_seconds
    end = min(duration, end_bar * bar_seconds)
    return {
        "id": f"section_{index + 1}",
        "source_label": label,
        "source_kind": "fallback_grid",
        "structural_role_hint": label,
        "detected_start_seconds": round(start, 3),
        "detected_end_seconds": round(end, 3),
        "start_seconds": round(start, 3),
        "end_seconds": round(end, 3),
        "start_bar": start_bar,
        "end_bar": max(start_bar, end_bar),
        "energy": _fallback_energy(label),
        "source_confidence": 0.35,
    }


def _repair_section_edges(sections: list[dict], total_bars: int, duration: float, bar_seconds: float) -> None:
    cursor = 1
    for section in sections:
        length = max(1, int(section["end_bar"]) - int(section["start_bar"]) + 1)
        section["start_bar"] = cursor
        section["end_bar"] = min(total_bars, cursor + length - 1)
        section["start_seconds"] = round((section["start_bar"] - 1) * bar_seconds, 3)
        section["end_seconds"] = round(min(duration, section["end_bar"] * bar_seconds), 3)
        cursor = section["end_bar"] + 1
    if sections and sections[-1]["end_bar"] < total_bars:
        sections[-1]["end_bar"] = total_bars
        sections[-1]["end_seconds"] = round(duration, 3)
    for index, section in enumerate(sections):
        section["id"] = f"section_{index + 1}"


def _annotate_sections(sections: list[dict]) -> None:
    energies = [float(section.get("energy") or 0.0) for section in sections]
    max_energy = max(energies) if energies else 1.0
    min_energy = min(energies) if energies else 0.0
    span = max(0.001, max_energy - min_energy)
    previous_level = "low"
    for index, section in enumerate(sections):
        normalized = (float(section.get("energy") or 0.0) - min_energy) / span
        level = "high" if normalized >= 0.66 else "medium" if normalized >= 0.33 else "low"
        role = _role_for_section(index, len(sections), level, previous_level, section)
        section["energy_level"] = level
        section["role"] = role
        section["active_roles"] = _active_roles(role, level)
        section["description"] = _section_description(role, level)
        previous_level = level


def _role_for_section(index: int, count: int, level: str, previous_level: str, section: dict) -> str:
    lower = f"{section.get('structural_role_hint') or ''} {section.get('source_label') or ''}".lower()
    for role in ("intro", "breakdown", "drop", "outro", "bridge"):
        if role in lower:
            return role
    if index == 0:
        return "intro"
    if index == count - 1:
        return "outro"
    if level == "low" and previous_level in {"medium", "high"}:
        return "breakdown"
    if level == "high" and previous_level == "low":
        return "drop"
    for role in ("groove", "variation", "chorus", "verse"):
        if role in lower:
            return "groove" if role in {"chorus", "verse"} else role
    if level == "high":
        return "groove"
    return "variation"


def _active_roles(role: str, level: str) -> list[str]:
    roles = {
        "intro": ["kick", "bass hint", "filtered percussion"],
        "groove": ["kick", "bass", "clap/snare", "hats", "percussion", "main stab"],
        "variation": ["kick", "bass", "percussion fills", "FX movement"],
        "breakdown": ["pads", "FX tails", "filtered stab", "reduced drums"],
        "drop": ["full drums", "bass", "hats", "percussion", "main hook/stab"],
        "outro": ["kick", "reduced bass", "hats", "DJ-friendly tail"],
        "bridge": ["pads", "transition FX", "reduced groove"],
    }.get(role, ["kick", "bass", "percussion"])
    if level == "low" and "reduced drums" not in roles:
        roles = [item for item in roles if item not in {"full drums", "main hook/stab"}]
    return roles


def _section_description(role: str, level: str) -> str:
    descriptions = {
        "intro": "establish timing and mood without revealing every element",
        "groove": "main dancefloor groove with stable low-end and percussion drive",
        "variation": "same pocket with fills, sound movement, and controlled changes",
        "breakdown": "reduce drums and low-end, leave tension, space, pads, and FX",
        "drop": "return with the strongest drum/bass energy and clearest hook role",
        "outro": "strip elements for a DJ-friendly ending while keeping tempo locked",
        "bridge": "connect sections with lower density and transition FX",
    }
    return f"{descriptions.get(role, 'maintain the reference role balance')} ({level} energy)"


def _absorb_cluster(target: dict, cluster: list[dict], at_start: bool) -> None:
    if not cluster:
        return
    all_sections = cluster + [target] if at_start else [target] + cluster
    start = min(_number(item.get("start_seconds"), 0.0) for item in all_sections)
    end = max(_number(item.get("end_seconds"), start) for item in all_sections)
    total = max(0.001, sum(_duration(item) for item in all_sections))
    target["start_seconds"] = round(start, 3)
    target["end_seconds"] = round(end, 3)
    target["detected_start_seconds"] = round(min(_number(item.get("detected_start_seconds"), start) for item in all_sections), 3)
    target["detected_end_seconds"] = round(max(_number(item.get("detected_end_seconds"), end) for item in all_sections), 3)
    target["start_bar"] = min(int(item.get("start_bar") or 1) for item in all_sections)
    target["end_bar"] = max(int(item.get("end_bar") or target["start_bar"]) for item in all_sections)
    target["source_label"] = "+".join(str(item.get("source_label") or "") for item in all_sections if item.get("source_label"))
    target["energy"] = round(sum(_number(item.get("energy"), 0.0) * _duration(item) for item in all_sections) / total, 4)

def _subdivision_label(section_index: int, original_count: int, chunk_index: int, chunk_count: int, label: str) -> str:
    lower = label.lower()
    if section_index == 0 and chunk_index == 0:
        return "intro"
    if section_index == original_count - 1 and chunk_index == chunk_count - 1:
        return "outro"
    if "break" in lower:
        return "breakdown" if chunk_index == 0 else "drop"
    if chunk_index == 0:
        return "groove"
    if chunk_index == chunk_count - 1:
        return "variation"
    return "groove"

def _section_bar_seconds(section: dict) -> float:
    return _duration(section) / max(1, _bar_count(section))

def _bar_count(section: dict) -> int:
    return max(1, int(section.get("end_bar") or 1) - int(section.get("start_bar") or 1) + 1)

def _duration(section: dict) -> float:
    return max(0.0, _number(section.get("end_seconds"), 0.0) - _number(section.get("start_seconds"), 0.0))


def _fallback_energy(label: str) -> float:
    return {"intro": 0.35, "main": 0.75, "groove": 0.8, "variation": 0.7, "breakdown": 0.2, "drop": 0.95, "outro": 0.4}.get(label, 0.6)


def _number(value, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
