# Node.js Conventions

Last updated: 2026-05-06

## Scope

Applies to the implemented local Node orchestrator.

## Rules

- Node owns orchestration, job state, API contracts, Python invocation, and LLM result aggregation.
- Keep analysis algorithms out of Node; call Python modules for signal processing.
- API handlers should be thin and delegate to services.
- Long-running work must be job-based: return quickly with a job id, then expose status/result.
- Represent failures with structured errors the plugin can display.
- Keep local file paths explicit and validate them before passing to Python.
- Preserve local-first behavior when optional Gemini, ACE, or ML engines fail.
- Pass through MIDI provenance/limitations so clients do not overstate stem-splitting or transcription quality.

## Suggested shape

- `backend/server.js` for local API
- `backend/lib/jobs.js` for queue/state
- `backend/lib/pythonRunner.js` for Python process calls
- `backend/lib/promptGenerator.js` and `backend/lib/geminiPromptGenerator.js` for prompt generation
- future schema module if response contracts grow
