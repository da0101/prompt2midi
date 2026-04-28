# Feature Brief — prompt2midi

> Read this first — every session, every agent (Claude, Codex, Gemini).
> 30-second orientation: what we're building, why, and where we stand.
> Replace entirely when the active feature changes. Keep ≤60 lines.

**Feature:** none active
**Status:** ready for next stream
**Stream file:** none

---

## What we're building

The last stream, `source-aware-transcription-v1`, is closed. The project now has a local source-aware bass path: Demucs separates a bass stem, Basic Pitch transcribes it, and the backend exposes `source-bass-transcription.mid` as a distinct MIDI asset.

## Why

The user needs a credible path from real audio reference to editable Ableton MIDI, while staying local-first and clear about confidence.

## What done looks like

- Select the next stream from `promt.md`.
- Keep generated sketches, heuristic output, model transcription, and source-aware transcription clearly separated.
- Preserve local-first operation and graceful fallback when optional engines are absent.

## Architecture decisions locked

- Keep the existing JUCE → Node → Python contract from the previous streams.
- Core workflow stays local-first; no mandatory cloud APIs.
- Do not present MIDI as source-aware transcription unless the extraction path actually supports that claim.

## Current state

The repo supports prompt/WAV/MP3 jobs, FFmpeg MP3 decoding, BPM/key confidence, `reference-sketch.mid`, optional Basic Pitch `model-transcription.mid`, optional Demucs-assisted `source-bass-transcription.mid`, full-mix `model-bass-transcription.mid`, and experimental heuristic `bass-transcription.mid`.

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
