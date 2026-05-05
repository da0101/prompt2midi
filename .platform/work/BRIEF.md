# Feature Brief — prompt2midi

> Read this first — every session, every agent (Claude, Codex, Gemini).
> 30-second orientation: what we're building, why, and where we stand.
> Replace entirely when the active feature changes. Keep ≤60 lines.

**Feature:** full-arrangement-proxy-v1
**Status:** in-progress
**Stream file:** `work/full-arrangement-proxy-v1.md`

---

## What we're building

Full-song reference-inspired proxy generation for SUNO. The workflow should analyze an entire reference track, detect the bar-aligned arrangement structure, generate original ACE proxy audio section by section, let the user audition candidates, then stitch/export a full-length guide and prompt package.

## Why

The user wants SUNO to follow a known song arrangement instead of inventing cheesy or unrelated structure. A strong full-length proxy should preserve genre, BPM, key area, groove, energy curve, breaks, drops, hooks, silences, and section proportions while staying original and copyright-safe.

## What done looks like

- Full reference analysis produces a reliable `arrangement-map.json`, `analysis-report.md`, and `suno-structure-prompt.md`.
- Full Arrangement mode cuts bar-aligned sections, generates ACE candidates per section, lets the user select/rerun sections, and stitches a full guide.
- The existing 30-second ACE sample lane remains clean and unchanged for fast testing.

## Architecture decisions locked

- Use section-by-section full-song generation as the default; do not rely on one-shot ACE full-song rendering.
- Use a bar-grid contract: every generated section has target start/end bars, role, energy, duration, and transition metadata.
- MIDI/stem extraction is optional evidence/debug for this stream, not the main audio output path.

## Current state

Phase 1 Arrangement Lock analysis is implemented: `arrangement-map.json` now includes blueprint fidelity, section transition metadata, lock confidence, and review gating; `arrangement-lock-report.json` and `structure-debug.json` are written beside the report/prompt. It is not yet product-ready because it still needs real-reference validation, section cutting, section audition, candidate selection, beat-safe stitching, continuity checks, per-section prompt tuning, and ACE failure prediction.

See `work/ACTIVE.md` for stream status.

## Relevant context

> Only load the files listed here. Everything else is out of scope for this feature.
> Prefer `.platform/domains/<name>.md` files (cross-layer, focused) over repo-wide files.
> Repo files (`backend.md`, `admin.md`, etc.) are conventions — load only if you need to understand patterns.

- `.platform/domains/audio-analysis.md` — relevant domain for this stream
- `.platform/domains/composition-engine.md` — relevant domain for this stream
- `.platform/domains/llm-midi-generation.md` — relevant domain for this stream
- `.platform/domains/local-orchestration.md` — relevant domain for this stream
- `.platform/domains/juce-plugin.md` — relevant domain for this stream


**Do not load:** unrelated JUCE/Xcode files unless the stream reaches UI/plugin integration.
**Never load:** `work/archive/*`

## Key files

- `analysis/external_analyzers.py`
- `analysis/full_arrangement.py`
- `analysis/full_guide_audio.py`
- `analysis/analyze.py`
- `analysis/ace_step_generation.py`
- `scripts/ace-proxy-ui.js`
- `scripts/run-suno-proxy-pipeline.js`
- `docs/ace-mj-working-pipeline.md`
