# Feature Brief — prompt2midi

> Read this first — every session, every agent (Claude, Codex, Gemini).
> 30-second orientation: what we're building, why, and where we stand.
> Replace entirely when the active feature changes. Keep ≤60 lines.

**Feature:** stream cleanup / blocked follow-ups
**Status:** no active in-progress feature stream
**Stream file:** `work/ACTIVE.md`

---

## What we're building

No feature stream is currently in active execution. The previous `full-arrangement-proxy-v1` and `inspired-loop-engine-v1` streams were accepted by the owner and archived on 2026-05-05.

## Why

The workflow state was cleaned up so future sessions do not resume completed work or mix fine-tuning tasks into already accepted streams.

## What done looks like

- `ab doctor` passes.
- `ACTIVE.md` lists only real open streams.
- Completed streams stay in `work/archive/`.
- New config fine-tuning work starts as a fresh, scoped stream.

## Architecture decisions locked

- Completed streams should be archived instead of kept open for vague tuning.
- `.platform/work/` should contain only active, blocked, or awaiting-verification stream files.
- Supporting logs belong in `.platform/memory/`, not `.platform/work/`.

## Current state

Open stream is currently blocked follow-up:

- `gemini-suno-prompt-v1` — blocked on real Gemini API smoke test with a WAV.

`deep-analysis-v1` was closed as superseded on 2026-05-05 after audit. The code exists, but the original done criteria were never verified as written; open a fresh verification stream if real-audio deep-analysis QA becomes the next priority.

See `work/ACTIVE.md` for stream status.

## Relevant context

> Only load the files listed here. Everything else is out of scope for this feature.
> Prefer `.platform/domains/<name>.md` files (cross-layer, focused) over repo-wide files.
> Repo files (`backend.md`, `admin.md`, etc.) are conventions — load only if you need to understand patterns.

- `.platform/work/ACTIVE.md` — current stream registry
- `.platform/domains/llm-midi-generation.md` — relevant domain for the remaining Gemini SUNO prompt stream
- `.platform/domains/composition-engine.md` — relevant domain for composition context passed into Gemini
- `.platform/domains/local-orchestration.md` — relevant domain for Node job orchestration and smoke-test flow
- `.platform/memory/log.md` — closure and cleanup log
- `.platform/memory/listen-tests.md` — listening feedback log moved out of workstream directory


**Do not load:** unrelated JUCE/Xcode files unless a new implementation stream starts.
**Never load:** `work/archive/*`

## Key files

- `.platform/work/ACTIVE.md`
- `.platform/work/gemini-suno-prompt-v1.md`
- `.platform/work/archive/deep-analysis-v1.md`
- `.platform/work/archive/full-arrangement-proxy-v1.md`
- `.platform/work/archive/inspired-loop-engine-v1.md`
