# Feature Brief — prompt2midi

> Read this first — every session, every agent (Claude, Codex, Gemini).
> 30-second orientation: what we're building, why, and where we stand.
> Replace entirely when the active feature changes. Keep ≤60 lines.

**Feature:** source-aware-transcription-v1
**Status:** in-progress
**Stream file:** `work/source-aware-transcription-v1.md`

---

## What we're building

Build the next accuracy step after `audio-intelligence-v1`: a source-aware transcription path that can outperform the current full-mix bass heuristic. The goal is not a polished UI; it is a materially better local MIDI extraction foundation with honest labels and tests.

## Why

The user already caught that generated/heuristic MIDI can be far from the reference track. The product needs a credible path from real audio reference to editable Ableton MIDI, while staying local-first and clear about confidence.

## What done looks like

- A local transcription approach is selected with documented tradeoffs.
- Bass extraction becomes more musically useful than the current heuristic on fixtures and the provided MP3 smoke case.
- The backend/JUCE result contract keeps generated sketches, heuristic output, and source-aware transcription clearly separated.

## Architecture decisions locked

- Keep the existing JUCE → Node → Python contract from the previous streams.
- Core workflow stays local-first; no mandatory cloud APIs.
- Do not present MIDI as source-aware transcription unless the extraction path actually supports that claim.

## Current state

The repo now supports prompt/WAV/MP3 jobs, FFmpeg MP3 decoding, BPM/key confidence, `reference-sketch.mid`, and optional experimental `bass-transcription.mid`. The remaining accuracy gap is source-aware extraction: separating or modeling musical parts before producing MIDI.

See `work/ACTIVE.md` for stream status.

## Relevant context

> Only load the files listed here. Everything else is out of scope for this feature.
> Prefer `.platform/domains/<name>.md` files (cross-layer, focused) over repo-wide files.
> Repo files (`backend.md`, `admin.md`, etc.) are conventions — load only if you need to understand patterns.

- `.platform/domains/audio-analysis.md` — relevant domain for this stream
- `.platform/domains/llm-midi-generation.md` — relevant domain for this stream
- `.platform/domains/local-orchestration.md` — relevant domain for this stream
- `.platform/domains/juce-plugin.md` — relevant domain for this stream


**Do not load:** `.platform/work/archive/*` unless auditing a closed stream.
**Never load:** `work/archive/*`

## Key files

- `analysis/bass_transcription.py`
- `analysis/feature_extraction.py`
- `analysis/midi_extraction.py`
- `analysis/analyze.py`
- `backend/lib/pythonRunner.js`
- `backend/lib/promptGenerator.js`
- `Source/LocalApiClient.h`
- `docs/manual-verification.md`
