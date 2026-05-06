# API Conventions

Last updated: 2026-05-06

## Scope

Applies to the local API between JUCE and Node.

## Required endpoints

- `POST /analyze` starts a job and returns a job id.
- `GET /status` returns job state and progress.
- `GET /result` returns the finished analysis, prompt output, and generated asset paths.

## Contract rules

- Long-running work must not block the request that starts it.
- Every response should be JSON.
- Use stable top-level fields for `job_id`, `status`, `progress`, `error`, and `result`.
- Status values should cover queued, running, succeeded, failed, and cancelled.
- Result shape must preserve Phase 1 fields even as later phases add sections, instruments, chords, and MIDI files.
- Result shape must include confidence/provenance for MIDI assets. Weak stem or transcription evidence must be labeled as review-needed rather than final.
- Optional Gemini/ACE/ML outputs may be absent; clients must tolerate missing optional fields.

## Error rules

- Errors must be displayable in the plugin without exposing stack traces.
- Include a machine-readable code and a short user-facing message.
- Missing backend, invalid path, unsupported format, analysis failure, and LLM failure should be distinguishable.
