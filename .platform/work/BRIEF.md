# Feature Brief — prompt2midi

> Read this first every session. Keep <=60 lines.

**Feature:** project-cleanup-restructure-v1
**Status:** in-progress
**Stream file:** `work/project-cleanup-restructure-v1.md`

## What We're Building

Production-readiness cleanup and repository restructuring before the next coding push.

## Why

The repo grew through fast experiments. We need clearer ownership boundaries, fewer runtime artifacts in git, and stable commands before production preparation continues.

## Done Looks Like

- `analysis/` is grouped by responsibility and uses direct package imports.
- Confirmed dead/generated tracked files are removed and ignored.
- Node/Python entry points use stable commands and `python -m analysis...`.
- Docs, scripts, requirements, and Agentboard references match the new layout.
- Verification is green after file moves.

## Locked Decisions

- No importer-only shim files.
- Keep local-first architecture: JUCE client -> Node orchestration -> Python analysis/generation.
- Keep Python structured JSON contracts stable during module splits.

## Current State

- `project-cleanup-restructure-v1` — active cleanup stream, implementation and verification green; final audit/commit pending.
- `gemini-suno-prompt-v1` — blocked on real Gemini API smoke test with a WAV.
- `deep-analysis-v1` — closed as superseded on 2026-05-05; open a fresh verification stream if real-audio deep-analysis QA becomes next priority.

See `work/ACTIVE.md` for stream status.

## Relevant Context

- `.platform/work/ACTIVE.md` — stream registry
- `.platform/work/project-cleanup-restructure-v1.md` — current cleanup stream
- `.platform/domains/audio-analysis.md` — `analysis/` layout
- `.platform/domains/local-orchestration.md` — backend/scripts flow
- `.platform/domains/composition-engine.md` — composition context
- `.platform/domains/llm-midi-generation.md` — Gemini/SUNO follow-up
- `.platform/domains/juce-plugin.md` — plugin/exporter boundaries
- `.platform/memory/log.md` — chronological cleanup log

**Do not load:** archived streams unless needed for historical rationale.
**Never load:** `work/archive/*`

## Key Files

- `analysis/`
- `backend/`
- `scripts/`
- `Source/`
