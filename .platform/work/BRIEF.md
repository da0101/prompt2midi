# Feature Brief — prompt2midi

> Read this first — every session, every agent (Claude, Codex, Gemini).
> 30-second orientation: what we're building, why, and where we stand.
> Replace entirely when the active feature changes. Keep ≤60 lines.

**Feature:** audio-intelligence-v1
**Status:** planning
**Stream file:** `work/audio-intelligence-v1.md`

---

## What we're building

Audio-intelligence v1 improves the musical usefulness of the MVP pipeline. The first vertical slice proved the JUCE → Node → Python → MIDI/result contract; this stream makes the analysis and MIDI behavior less misleading and more useful on real reference tracks.

## Why

The current `bassline.mid` is only a deterministic placeholder sketch, and the user has already flagged that it is far from the reference track. Before adding polish, the product needs honest, testable music intelligence and clear limits.

## What done looks like

- Placeholder MIDI is either removed/relabelled or replaced with a tested first extraction path.
- BPM/key/energy outputs have confidence/warnings backed by fixtures.
- MP3 support is implemented or explicitly deferred with a chosen decoder path.
- Existing backend/Python/JUCE build gates stay green.

## Architecture decisions locked

- Keep the local-first Node/Python/JUCE contract from `vertical-slice-mvp`.
- Do not require cloud APIs for the core workflow.
- Do not present generated MIDI as transcription unless the analysis actually supports it.

## Current state

The MVP can submit prompt/WAV jobs, run dependency-free Python WAV analysis, generate deterministic producer prompts, and write a simple bassline MIDI sketch. The next work is accuracy and product honesty, not a UI redesign.

See `work/ACTIVE.md` for stream status.

## Relevant context

> Only load the files listed here. Everything else is out of scope for this feature.
> Prefer `.platform/domains/<name>.md` files (cross-layer, focused) over repo-wide files.
> Repo files (`backend.md`, `admin.md`, etc.) are conventions — load only if you need to understand patterns.

- `.platform/domains/audio-analysis.md` — relevant domain for this stream
- `.platform/domains/llm-midi-generation.md` — relevant domain for this stream
- `.platform/domains/local-orchestration.md` — relevant domain for this stream
- `.platform/domains/juce-plugin.md` — relevant domain for this stream


**Do not load:** `.platform/work/archive/*` unless explicitly auditing the closed MVP.
**Never load:** `work/archive/*`

## Key files

- `analysis/feature_extraction.py`
- `analysis/midi_extraction.py`
- `backend/server.js`
- `backend/lib/promptGenerator.js`
- `backend/test/server.test.js`
- `docs/manual-verification.md`
