---
domain_id: dom-audio-analysis
slug: audio-analysis
status: active
repo_ids: [prompt2midi]
related_domain_slugs: [local-orchestration, llm-midi-generation, juce-plugin]
created_at: 2026-04-28
updated_at: 2026-04-28
---

# audio-analysis

## What this domain does

This domain covers the Python audio intelligence engine: extracting musical facts from WAV/MP3 files and returning structured JSON. It is the foundation for producer insights, arrangement understanding, MIDI export, and AI prompt generation.

## Backend / source of truth

- Implemented Phase 1 modules: `analysis/feature_extraction.py`, `analysis/analyze.py`, and `analysis/midi_extraction.py`.
- Phase 2 output: BPM/key estimates with confidence, energy curve, loudness, spectral features, warnings, and a `reference-sketch.mid` path.
- Python still analyzes PCM WAV; MP3 is decoded by Node/FFmpeg before invoking Python.
- Later phases: section segmentation, stem/instrument analysis, chord progression, melody/bass MIDI extraction.
- Python should return structured JSON only; interpretation/prose belongs to Node/LLM.

## Frontend / clients

- JUCE displays BPM/key, energy curve, structure, instrument tags, chords, and export buttons derived from analysis output.
- Node orchestrator owns job lifecycle and invokes Python modules.

## API contract locked

- Phase 1 JSON shape starts with:
  - `bpm: number`
  - `bpm_confidence: number`
  - `key: string`
  - `key_confidence: number`
  - `energy_curve: array`
  - `loudness: number`
  - `warnings: array`
- Future analysis data should extend the contract without breaking existing UI fields.
- Errors must be structured enough for the plugin to show actionable states.

## Key files

- `promt.md`
- `analysis/analyze.py`
- `analysis/feature_extraction.py`
- `analysis/midi_extraction.py`
- `analysis/test_feature_extraction.py`
- Planned: `analysis/segmentation.py`

## Decisions locked

- Analysis must be modular so phases can land independently.
- Start with basic but useful analysis before stems/chords/MIDI.
- Use deterministic outputs for tests and LLM prompts.
- Treat large audio files as normal input; design for progress and memory limits.
