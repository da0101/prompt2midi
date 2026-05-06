# Node.js Conventions

Last updated: 2026-04-28

## Scope

Applies once the local orchestrator is introduced.

## Rules

- Node owns orchestration, job state, API contracts, Python invocation, and LLM result aggregation.
- Keep analysis algorithms out of Node; call Python modules for signal processing.
- API handlers should be thin and delegate to services.
- Long-running work must be job-based: return quickly with a job id, then expose status/result.
- Represent failures with structured errors the plugin can display.
- Keep local file paths explicit and validate them before passing to Python.

## Suggested shape

- `server` or `backend` entrypoint for local API
- `jobs` module for queue/state
- `analysis` bridge for Python process calls
- `llm` module for interpretation/prompt generation
- `schemas` module for request/response contracts
