"""Helpers for detecting explicit key-change intent in user prompts."""
from __future__ import annotations

import re

_KEY_PATTERN = r"([A-G](?:#|b)?\s*(?:major|minor|maj|min|m)?)"


def requested_target_key(prompt: str) -> str | None:
    """Return a normalized target key when the prompt explicitly asks to transpose/key-shift."""
    text = " ".join((prompt or "").replace("\n", " ").split())
    if not text:
        return None
    lowered = text.lower()
    if not re.search(r"\b(transpose|transposed|key\s*shift|keyshift|shift\s+key|change\s+key|target\s+key)\b", lowered):
        return None

    patterns = [
        rf"\b(?:to|into)\s+{_KEY_PATTERN}\b",
        rf"\btarget\s+key\s*(?:is|=|:)?\s*{_KEY_PATTERN}\b",
        rf"\btarget\s+key\s+area\s*(?:is|=|:)?\s*{_KEY_PATTERN}\b",
        rf"\brequested\s+target\s+key\s+area\s*(?:is|=|:)?\s*{_KEY_PATTERN}\b",
        rf"\b(?:new|different)\s+key\s*(?:is|=|:)?\s*{_KEY_PATTERN}\b",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if matches:
            return _normalize_key(matches[-1])
    return None


def _normalize_key(raw: str) -> str:
    compact = " ".join(str(raw or "").strip().split())
    if not compact:
        return compact
    match = re.match(r"^([A-Ga-g])([#b]?)(?:\s*)(major|minor|maj|min|m)?$", compact)
    if not match:
        return compact
    root = match.group(1).upper() + (match.group(2) or "")
    mode = (match.group(3) or "").lower()
    if mode == "maj":
        mode = "major"
    elif mode in {"min", "m"}:
        mode = "minor"
    return f"{root} {mode}".strip()
