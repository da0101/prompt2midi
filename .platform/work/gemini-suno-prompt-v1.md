---
stream_id: stream-gemini-suno-prompt-v1
slug: gemini-suno-prompt-v1
type: feature
status: in-progress
agent_owner: claude-code
domain_slugs: [llm-midi-generation, composition-engine, local-orchestration]
repo_ids: [repo-primary]
base_branch: main
git_branch: feature/gemini-suno-prompt-v1
created_at: 2026-04-28
updated_at: 2026-04-28
closure_approved: false
---

# gemini-suno-prompt-v1

## Scope

- **In scope:** Phase 4 — `backend/lib/geminiPromptGenerator.js` calls Gemini 2.5 Pro with structured analysis + composition JSON and returns a rich SUNO prompt; Node wires it into the job pipeline; fallback to Python stub if unavailable
- **Out of scope:** Phase 3 (better ML analysis), Phase 5 (UI reframe), Gemini audio input

## Done criteria

- [ ] `backend/lib/geminiPromptGenerator.js` exists and calls Gemini with structured JSON
- [ ] `suno_prompt.text` in job result is Gemini-generated when key is set
- [ ] Falls back gracefully to Python stub when GEMINI_API_KEY absent or call fails
- [ ] Pipeline logs show `gemini suno prompt` stage
- [ ] `npm test` passes (Gemini call mocked in tests)
- [ ] Real smoke test: run with a WAV and verify `exports/prompt.txt` contains a real Gemini prompt
- [ ] `.platform/memory/log.md` appended

## Key decisions

2026-04-28 — suno_prompt shape stays { text, path } — JUCE already reads this; no downstream changes
2026-04-28 — Gemini call is injectable (options.sunoGenerator) for testability
2026-04-28 — GEMINI_API_KEY from env; PROMPT2MIDI_GEMINI_MODEL overrides model ID

## Resume state

- **Last updated:** 2026-04-28 — by claude-code
- **What just happened:** Stream registered, plan presented
- **Current focus:** Implementation
- **Next action:** Execute after user approval
- **Blockers:** none

## Progress log

2026-04-28 — Stream registered

## Open questions

_None._

---

## 🔍 Audit Report

_Status: not yet run_
