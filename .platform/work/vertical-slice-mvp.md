---
stream_id: stream-vertical-slice-mvp
slug: vertical-slice-mvp
type: feature
status: planning
agent_owner: codex
domain_slugs: [juce-plugin, audio-analysis, local-orchestration, llm-midi-generation]
repo_ids: [prompt2midi]
base_branch: main
git_branch: feature/vertical-slice-mvp
created_at: 2026-04-28
updated_at: 2026-04-28
closure_approved: false
---

# vertical-slice-mvp

## Scope

- Build the first useful end-to-end slice from plugin/client request to local analysis result.
- Include JUCE UI/client behavior, local Node job API, Phase 1 Python analysis JSON, and LLM-generated producer prompt where feasible.
- Keep scope shallow: BPM, key, energy curve, loudness, and prompt generation before stems/sections/MIDI extraction depth.
- Out of scope for this stream: stem separation, melody extraction, polished installer, cloud-only APIs, and final release packaging.

## Done criteria

- [ ] JUCE/plugin-side client can submit a prompt or local audio file path without blocking the audio thread.
- [ ] Local Node API can create a job, report status, invoke Python, and return structured result JSON.
- [ ] Python Phase 1 engine returns BPM, key, energy curve, and loudness for a supported audio file.
- [ ] LLM/prompt layer can generate producer-facing explanation and AI-generation prompt from fixed structured input.
- [ ] Manual vertical-slice verification is documented.
- [ ] `.platform/memory/log.md` appended.
- [ ] `decisions.md` updated if any architectural choices were made.

## Key decisions

- 2026-04-28 — Use `promt.md` as execution plan — Owner confirmed it is the exact plan.
- 2026-04-28 — Start with a shallow vertical slice — It proves component contracts before adding advanced music intelligence.

## Resume state
_Overwritten by `ab checkpoint` — the compact payload the next agent reads first. Keep this block under ~10 lines._

- **Last updated:** 2026-04-28 by danilulmashev (auto)
- **What just happened:** (auto) 434f7e0: Activate Agentboard project context
- **Current focus:** —
- **Next action:** (auto-saved from commit — update next action manually)
- **Blockers:** none

## Progress log

2026-04-28 10:11 — (auto) 434f7e0: Activate Agentboard project context

2026-04-28 10:09 — Activated project from promt.md and created the vertical-slice MVP planning stream.

- 2026-04-28 10:00 — Created planning stream during project activation.

## Open questions

- Which local LLM runtime/model should Phase 5 target first?
- Should the first plugin integration send audio file paths only, prompt text only, or both in the first implementation pass?
- Which plugin format must be verified first in Ableton: AU or VST3?

---

## Audit Report

_Status: not yet run_
