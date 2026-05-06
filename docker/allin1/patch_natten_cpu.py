#!/usr/bin/env python3
"""Patch NATTEN 0.17.x so CPU-only torch imports do not probe CUDA."""
from __future__ import annotations

from pathlib import Path


def main() -> int:
    target = Path("/usr/local/lib/python3.10/site-packages/natten/utils/testing.py")
    if not target.exists():
        raise SystemExit(f"NATTEN testing.py not found at {target}")

    text = target.read_text()
    old = "_IS_TRITON_SUPPORTED = get_device_cc() >= 70"
    new = "_IS_TRITON_SUPPORTED = torch.cuda.is_available() and get_device_cc() >= 70"
    if new in text:
        return 0
    if old not in text:
        raise SystemExit("NATTEN CUDA probe line not found; patch needs review")
    target.write_text(text.replace(old, new))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
