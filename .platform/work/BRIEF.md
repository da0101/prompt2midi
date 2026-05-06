# Feature Brief — prompt2midi

> Read this first every session. Keep <=60 lines.

**Feature:** gemini-suno-prompt-v1
**Status:** blocked
**Stream file:** `work/gemini-suno-prompt-v1.md`

## What We're Building

Real Gemini SUNO prompt verification remains the only active stream. Documentation/platform refresh is happening on `develop` to align README, architecture, domains, conventions, branch flow, and release ownership.

## Why

The repo now has a working local vertical slice plus optional generation/proxy paths. Agent memory must match the current architecture before more coding or release work.

## Current State

- `develop` is the default integration branch.
- `main` is release-only for tagged releases.
- `project-cleanup-restructure-v1` is closed and archived after PR #1.
- `gemini-suno-prompt-v1` is blocked on a real `GEMINI_API_KEY` + WAV smoke test.
- Stem splitting and MIDI mapping are useful but weak evidence paths; the next feature work should improve them.
- Full JUCE AU/VST integration and DAW host QA are upcoming production-readiness work.

## Done Looks Like For Active Stream

- Real-key Gemini smoke test succeeds.
- Result includes `result.suno_prompt.path`.
- `exports/prompt.txt` contains a real Gemini paragraph, not the Python stub.
- Fallback behavior remains safe when Gemini is disabled/missing/fails.

## Locked Decisions

- Core workflow stays local-first.
- JUCE remains UI/client; no heavy work in `processBlock`.
- Node owns orchestration and aggregation.
- Python returns structured JSON and local file paths.
- `develop` is default; `main` is release-only.
- Open-source contributions are welcome, but extracted MIDI must be labeled honestly.

## Relevant Context

- `.platform/work/ACTIVE.md` — stream registry
- `.platform/work/gemini-suno-prompt-v1.md` — active blocked stream
- `.platform/architecture.md` — current system architecture
- `.platform/conventions/git-flow.md` — branch/release flow
- `.platform/domains/audio-analysis.md` — stem/MIDI limitations
- `.platform/domains/local-orchestration.md` — backend flow
- `.platform/domains/juce-plugin.md` — AU/VST/JUCE boundaries
- `.platform/domains/llm-midi-generation.md` — Gemini/SUNO follow-up

**Do not load:** archived streams unless needed for historical rationale.
**Never load:** `work/archive/*`
