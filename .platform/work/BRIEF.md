# Feature Brief — prompt2midi

> Read this first every session. Keep <=60 lines.

**Feature:** stems-splitting-midi-mapping
**Status:** planning
**Stream file:** `work/stems-splitting-midi-mapping.md`

## What We're Building

Accurate stem splitting and source-aware MIDI mapping from generated ACE output. The reusable music source is the ACE-generated audio, not the original reference track.

## Why

The current stem/MIDI path is useful evidence but weak. For production use, the system must listen to generated material, detect which musical roles actually exist, split those sources as well as possible, and emit only justified MIDI maps with honest confidence labels.

## Current State

- Branch: `feature/stems-splitting-midi-mapping` from `develop`.
- New stream is in planning; do architecture/research before implementation.
- `gemini-suno-prompt-v1` remains blocked on a real Gemini API smoke test.
- `main` is release-only; merge feature PRs into `develop`.

## Done Looks Like

- ACE/generated output is the input to stem splitting and MIDI extraction.
- Stem roles are dynamically detected, not hardcoded.
- If generated audio only has drums+pads, only those stems/MIDI assets are emitted.
- If generated audio only has bass+guitar, only those stems/MIDI assets are emitted.
- Every emitted stem/MIDI asset includes source, method, confidence, and limitations.
- Tests and at least one listening QA run prove the mapping is not fake/static.

## Locked Decisions

- Reference audio is inspiration/evidence only, not the reusable music source.
- Default music generation taste is underground house/minimal-deep tech-house, not generic electronic/EDM. Follow `.platform/conventions/music-generation-style.md`.
- Do not claim perfect transcription; label uncertainty.
- Optional AI/listening models must be local-first where possible and fail soft.
- JUCE remains client/UI; Python/Node own analysis and mapping.

## Relevant Context

- `.platform/work/stems-splitting-midi-mapping.md` — active stream
- `.platform/architecture.md` — current system architecture
- `.platform/domains/audio-analysis.md` — stem/MIDI limitations and contracts
- `.platform/domains/local-orchestration.md` — Node job/result contracts
- `.platform/domains/composition-engine.md` — generated MIDI vs evidence distinction
- `.platform/conventions/music-generation-style.md` — strict ACE/Suno prompt and genre/taste rules
- `.platform/domains/juce-plugin.md` — UI/client display constraints
- `analysis/midi/`, `analysis/generation/`, `analysis/arrangement/`, `analysis/reference/`

**Do not load:** archived streams unless needed for historical rationale.
**Never load:** `work/archive/*`
