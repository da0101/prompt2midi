# Python Audio Conventions

Last updated: 2026-05-06

## Scope

Applies to the implemented Python analysis, MIDI, composition, arrangement, and generation packages.

## Rules

- Python returns structured JSON only; no producer-facing prose from analysis modules.
- Keep feature extraction, segmentation, and MIDI extraction as separate modules.
- Design for large audio files: stream or chunk where practical, report progress, avoid loading avoidable duplicate copies.
- Make outputs deterministic enough for tests and LLM prompts.
- Include confidence or caveat fields when detection is uncertain.
- Keep command-line/module interfaces stable so Node can call them reliably.
- Treat stem splitting and MIDI mapping as imperfect evidence. Include method/confidence/limitations for every extracted MIDI path.
- Optional ML engines must fail soft with warnings so the dependency-free path still works.

## Phase order

1. BPM, key, energy curve, loudness, spectral features.
2. Section segmentation and transition/energy analysis.
3. Stem/instrument analysis.
4. Chords, melody/bass extraction, MIDI export.
5. Next production push: stronger source-aware stem cleanup, MIDI ownership mapping, quantization, register selection, and DAW-ready labels.
