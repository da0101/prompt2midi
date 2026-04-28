---
domain_id: dom-local-orchestration
slug: local-orchestration
status: active
repo_ids: [prompt2midi]
related_domain_slugs: [audio-analysis, juce-plugin, llm-midi-generation]
created_at: 2026-04-28
updated_at: 2026-04-28
---

# local-orchestration

## What this domain does

This domain covers the local Node.js backend that connects the JUCE plugin, Python analysis engine, and LLM interpretation layer. It should provide stable job APIs, progress reporting, aggregation, and local error handling.

## Backend / source of truth

- Implemented REST endpoints from `promt.md`:
  - `POST /analyze`
  - `GET /status`
  - `GET /result`
- Node owns job queue/state, MP3/WAV boundary validation, FFmpeg MP3 decoding, Python process invocation, deterministic prompt generation, and result aggregation.
- Node passes through `midi_files` and structured `midi_assets` from Python, including generated sketches, optional model transcription, and heuristic fallbacks.
- Development scripts include `npm run dev:refresh` for rebuild + backend restart + live logs and `npm run setup:transcription` for the optional Basic Pitch engine.
- WebSocket or streaming progress remains deferred; MVP uses polling.
- Keep orchestration separate from signal processing.

## Frontend / clients

- JUCE plugin submits work and reads progress/results.
- Python engine is called by Node, not directly by JUCE.
- Local LLM layer receives structured analysis from Node.

## API contract locked

- Requests identify local audio files and/or prompt text.
- Long jobs return a job id quickly.
- Status endpoint must represent queued/running/succeeded/failed/cancelled states.
- Result endpoint returns analysis JSON, generated prose/prompt, local MIDI asset paths, and structured MIDI metadata when available. Clients must tolerate optional MIDI files because deeper extraction is capability-dependent.

## Key files

- `promt.md`
- `package.json`
- `backend/server.js`
- `backend/lib/audioInput.js`
- `backend/lib/jobs.js`
- `backend/lib/pythonRunner.js`
- `backend/lib/promptGenerator.js`
- `backend/test/server.test.js`
- `docs/local-backend.md`
- `docs/manual-verification.md`

## Decisions locked

- The backend runs locally first.
- Node is the API gateway and aggregation layer.
- Job status/progress are product features, not internal logs.
- The plugin should be able to recover gracefully if the local backend is not running.
