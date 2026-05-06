# Security / Privacy Conventions

Last updated: 2026-05-06

## Scope

Applies to local file handling, backend APIs, model integrations, prompts, logs, and generated assets.

## Rules

- Core workflow is local-first and must not require cloud upload.
- Never commit API keys, model tokens, user audio, generated private assets, or local absolute secrets.
- Treat audio files and prompts as user content.
- Do not log full prompts, file contents, or sensitive paths unless explicitly needed for debugging and approved.
- Validate local file paths before analysis; avoid accepting arbitrary remote URLs in the MVP.
- Bind the local API to localhost by default.
- If optional cloud LLM support is added later, require explicit opt-in and environment-based secrets.
- Optional Gemini prompt generation is cloud-backed and must remain opt-in via environment key. Core analysis/composition cannot depend on it.
- Do not log full local audio paths or prompt contents in persistent logs unless explicitly needed for debugging.

## Threats to keep in mind

- Accidental upload of copyrighted/private audio.
- Plugin calling an unintended local service.
- Backend exposing local file paths broadly.
- Large audio files causing memory or disk pressure.
