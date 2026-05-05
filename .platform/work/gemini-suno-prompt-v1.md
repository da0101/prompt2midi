---
stream_id: stream-gemini-suno-prompt-v1
slug: gemini-suno-prompt-v1
type: feature
status: blocked
agent_owner: claude-code
domain_slugs: [llm-midi-generation, composition-engine, local-orchestration]
repo_ids: [repo-primary]
base_branch: main
git_branch: feature/gemini-suno-prompt-v1
created_at: 2026-04-28
updated_at: 2026-05-05
closure_approved: false
---

# gemini-suno-prompt-v1

## Scope

- **In scope:** Phase 4 — `backend/lib/geminiPromptGenerator.js` calls Gemini 2.5 Pro with structured analysis + composition JSON and returns a rich SUNO prompt; Node wires it into the job pipeline; fallback to Python stub if unavailable
- **Out of scope:** Phase 3 (better ML analysis), Phase 5 (UI reframe), Gemini audio input

## Done criteria

- [x] `backend/lib/geminiPromptGenerator.js` exists and calls Gemini with structured JSON
- [x] `suno_prompt.text` in job result is Gemini-generated when key is set
- [x] Falls back gracefully to Python stub when GEMINI_API_KEY absent or call fails
- [x] Pipeline logs show `gemini suno prompt` stage
- [x] `npm test` passes (Gemini call mocked in tests)
- [ ] Real smoke test: run with a WAV and verify `exports/prompt.txt` contains a real Gemini prompt
- [ ] `.platform/memory/log.md` appended

## Key decisions

2026-04-28 — suno_prompt shape stays { text, path } — JUCE already reads this; no downstream changes
2026-04-28 — Gemini call is injectable (options.sunoGenerator) for testability
2026-04-28 — GEMINI_API_KEY from env; PROMPT2MIDI_GEMINI_MODEL overrides model ID

## Resume state

- **Last updated:** 2026-05-05 — by codex
- **What just happened:** Parallel audit confirmed implementation and mocked tests exist, but live Gemini API smoke and prompt-file overwrite are untested.
- **Current focus:** Blocked on real Gemini smoke test.
- **Next action:** Run with `GEMINI_API_KEY` and a WAV; verify `exports/prompt.txt` contains a real Gemini prompt, then move to awaiting-verification.
- **Blockers:** Needs real Gemini API smoke verification.

## Progress log

2026-05-05 — Parallel audit confirmed stream should remain blocked: implementation and mocked tests exist, but live Gemini API smoke and prompt-file overwrite are untested.

2026-05-05 — Cleanup audit: Gemini integration exists, mocked/fallback paths pass under `npm test`, but real API smoke is still missing; marked blocked instead of falsely active.

2026-04-28 — Stream registered

## Open questions

_None._

---

## 🔍 Audit Report

2026-05-05 — Parallel audit: keep blocked. `backend/lib/geminiPromptGenerator.js` builds structured JSON and calls `@google/generative-ai`; `backend/server.js` injects/calls `sunoGenerator`; fallback paths are tested. Missing evidence: real `GEMINI_API_KEY` job with `PROMPT2MIDI_DISABLE_SUNO` unset, returned `result.suno_prompt.path`, and `exports/prompt.txt` containing a real Gemini paragraph rather than the Python stub.
