---
stream_id: stream-vertical-slice-mvp
slug: vertical-slice-mvp
type: feature
status: in-progress
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

- [x] JUCE/plugin-side client can submit a prompt or local audio file path without blocking the audio thread.
- [x] Local Node API can create a job, report status, invoke Python, and return structured result JSON.
- [x] Python Phase 1 engine returns BPM, key, energy curve, and loudness for a supported audio file.
- [x] LLM/prompt layer can generate producer-facing explanation and AI-generation prompt from fixed structured input.
- [x] Manual vertical-slice verification is documented.
- [x] JUCE project regenerates from `/Applications/JUCE` and Debug Xcode builds pass.
- [x] `.platform/memory/log.md` appended.
- [x] `decisions.md` updated if any architectural choices were made.

## Key decisions

- 2026-04-28 — Use `promt.md` as execution plan — Owner confirmed it is the exact plan.
- 2026-04-28 — Start with a shallow vertical slice — It proves component contracts before adding advanced music intelligence.
- 2026-04-28 — Keep the first backend dependency-free — Node stdlib and Python stdlib make the local contract runnable before choosing FastAPI, MP3, or local model dependencies.

## Resume state
_Overwritten by `ab checkpoint` — the compact payload the next agent reads first. Keep this block under ~10 lines._

- **Last updated:** 2026-04-28 by danilulmashev
- **What just happened:** Cleaned up JUCE editor UI after visual smoke feedback: removed fake analyzer widgets, header pills, waveform strip, metric tiles, flow rail, and grid overlay; restored a neat single-column plugin layout and rebuilt standalone/AU/VST3 successfully.
- **Current focus:** Source/PluginEditor.cpp
- **Next action:** Quit and reopen the standalone app for human visual smoke test; if layout is clean, proceed to final audit and commit.
- **Blockers:** Musical accuracy remains MVP-level placeholder MIDI until the audio-intelligence stream.

## Progress log

2026-04-28 12:30 — Cleaned up JUCE editor UI after visual smoke feedback: removed fake analyzer widgets, header pills, waveform strip, metric tiles, flow rail, and grid overlay; restored a neat single-column plugin layout and rebuilt standalone/AU/VST3 successfully.

2026-04-28 12:24 — Pushed JUCE editor UI into a modern dark audio-tool layout with custom theme, waveform strip, metric tiles, signal header, cleaner file labels, and warning-free processor stub; full Debug app/AU/VST3 build and backend/Python tests pass.

2026-04-28 12:16 — Refreshed the JUCE editor UI with a modern dark music-tool layout, extracted theme helpers, regenerated Projucer/Xcode files, and rebuilt standalone/AU/VST3.

2026-04-28 11:50 — Audited the stream, fixed HTTP boundary validation and generated-file hygiene, and reran backend/Python/Xcode verification.

2026-04-28 11:04 — Audit pass fixed invalid JSON/audio-path validation, ignored generated Python bytecode, and confirmed Python, Node, Agentboard, and Xcode builds are green.

2026-04-28 10:52 — Wired project to /Applications/JUCE, regenerated Projucer/Xcode support, and confirmed Debug standalone/AU/VST3 builds pass.

2026-04-28 10:24 — Implemented the first vertical slice: Node local job API, Python WAV analyzer/MIDI writer, deterministic prompt generation, and async JUCE editor client.

2026-04-28 10:11 — (auto) 434f7e0: Activate Agentboard project context

2026-04-28 10:09 — Activated project from promt.md and created the vertical-slice MVP planning stream.

- 2026-04-28 10:00 — Created planning stream during project activation.

## Open questions

- Which local LLM runtime/model should Phase 5 target first?
- Which plugin format must be verified first in Ableton: AU or VST3?
- Should cloud mode keep Node as orchestration gateway or move the public API to FastAPI?

---

## Audit Report

_Status: green for vertical-slice MVP; UI accepted as temporary and slated for later redesign._

- Code review: PASS after cleaning unused UI helper code, `/analyze` async error handling, audio path validation, and generated-file hygiene.
- Security pass: PASS for local MVP; no secrets or shell-string execution found. Backend rejects invalid JSON, non-absolute paths, unsupported extensions, missing files, non-files, and oversized WAVs before Python analysis.
- Test coverage: PASS for backend/Python contract tests. Client-error coverage exists for invalid JSON and unsupported audio paths.
- Build: PASS for `prompt2midi - Shared Code` and full Debug `prompt2midi - All`.
- QA: PASS with caveat. Human visual review rejected the over-designed UI pass; the final UI was simplified back to a clean functional layout and accepted for now. In-host Ableton verification remains a release-packaging follow-up, not a blocker for this MVP stream.
