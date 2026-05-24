---
domain_id: dom-local-orchestration
slug: local-orchestration
status: active
repo_ids: [prompt2midi]
related_domain_slugs: [audio-analysis, juce-plugin, llm-midi-generation]
created_at: 2026-04-28
updated_at: 2026-05-06
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
- Node passes through `midi_files` and structured `midi_assets` from Python, including generated sketches, optional Basic Pitch model transcription, optional Demucs stem-aware bass transcription, and heuristic fallbacks.
- Development scripts include `npm run dev:refresh`, `npm run web:dev`, pipeline runners under `scripts/pipelines/*`, setup scripts under `scripts/setup/*`, and packaging helpers under `scripts/packaging/*`.
- `scripts/pipelines/run-suno-proxy-pipeline.js --map-stems` runs the ACE-output stem/MIDI mapping contract on the selected generated proxy audio and writes `ace-stem-midi-map/ace-stem-midi-map.json`; it is explicit because stem separation can be slow.
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
- Result metadata must make weak stem/MIDI evidence explicit so JUCE and web tooling can show review-needed labels instead of implying finished transcription.
- ACE-output stem/MIDI mapping results should identify the generated audio source path, detected roles, emitted MIDI paths, omitted roles, confidence, and limitations.

## Key files

- `promt.md`
- `package.json`
- `backend/server.js`
- `backend/lib/audioInput.js`
- `backend/lib/jobs.js`
- `backend/lib/pythonRunner.js`
- `backend/lib/promptGenerator.js`
- `backend/test/server.test.js`
- `docs/backend/local-backend.md`
- `docs/qa/manual-verification.md`
- `requirements/demucs.txt`
- `scripts/setup/setup-stem-engine.sh`

## Decisions locked

- The backend runs locally first.
- Node is the API gateway and aggregation layer.
- Job status/progress are product features, not internal logs.
- The plugin should be able to recover gracefully if the local backend is not running.
- Optional engines and cloud prompt calls must fail soft and preserve the base local analysis/composition path.
