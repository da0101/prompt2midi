---
stream_id: stream-source-aware-transcription-v1
slug: source-aware-transcription-v1
type: feature
status: in-progress
agent_owner: codex
domain_slugs: [audio-analysis, llm-midi-generation, local-orchestration, juce-plugin]
repo_ids: [prompt2midi]
base_branch: feature/audio-intelligence-v1
git_branch: feature/source-aware-transcription-v1
created_at: 2026-04-28
updated_at: 2026-04-28
closure_approved: false
---

# source-aware-transcription-v1

_Metadata rules: `stream_id` must be `stream-<slug>`, `slug` must match the filename, `status` must match `work/ACTIVE.md`, and `updated_at` should change whenever ownership or state changes._

## Scope
- Research and choose the first source-aware local transcription path that can materially outperform full-mix low-frequency heuristics.
- Implement a narrow prototype for better bass extraction on real references, ideally via local model inference or source separation plus pitch tracking.
- Preserve the existing local Node/Python/JUCE contract and keep outputs explicit about confidence and limitations.
- Add fixture tests and one real-file smoke path for the provided fake-music reference.
- Out of scope: cloud-only transcription, full arrangement generation, polished UI redesign, installer/notarization, and claiming production-grade accuracy before verification.

## Done criteria
- [x] A documented local transcription approach is selected with tradeoffs and dependency implications.
- [x] Bass extraction output is measurably more musically useful than the current heuristic on at least one controlled fixture and the provided MP3 smoke case.
- [x] Result contract distinguishes source-aware transcription from heuristic or generated sketch output.
- [x] Tests pass: `python3 -m unittest analysis/test_feature_extraction.py`, `npm test`, Python compile check, Node syntax checks, and JUCE Debug build if client output changes.
- [x] Manual verification documents behavior on the provided fake-music MP3 and at least one synthetic fixture.
- [x] `.platform/memory/log.md` appended
- [x] `decisions.md` updated if any architectural choices were made

## Key decisions
_Append-only. Format: `2026-04-28 — <decision> — <rationale>`_

- 2026-04-28 — Start from the audio-intelligence-v1 contract — Existing outputs are honest and tested; this stream should improve transcription accuracy without breaking the plugin/backend shape.
- 2026-04-28 — Use optional Basic Pitch first — It provides a real local audio-to-MIDI model now while leaving source separation and mandatory dependencies for later.
- 2026-04-28 — Use optional Demucs bass stems before Basic Pitch bass MIDI — It adds a real source-aware path while keeping dependency-free and full-mix fallback behavior.

## Resume state
_Overwritten by `ab checkpoint` — the compact payload the next agent reads first. Keep this block under ~10 lines._

- **Last updated:** 2026-04-28 by danilulmashev (auto)
- **What just happened:** (auto) 08eebd4: Add stem-aware bass transcription
- **Current focus:** —
- **Next action:** (auto-saved from commit — update next action manually)
- **Blockers:** none

## Progress log
_Append-only. `ab checkpoint` prepends a dated line and auto-trims to the last 10 entries. Format: `2026-04-28 HH:MM — <what happened>`._

2026-04-28 16:14 — (auto) 08eebd4: Add stem-aware bass transcription

2026-04-28 15:38 — (auto) Add visual pipeline logging

2026-04-28 15:13 — (auto) Add model-backed MIDI transcription

2026-04-28 14:11 — (auto) Close audio intelligence stream

2026-04-28 15:20 — Added optional Basic Pitch model transcription. Real MP3 smoke produced `model-transcription.mid`, `model-bass-transcription.mid`, `reference-sketch.mid`, and heuristic `bass-transcription.mid`; BPM now normalizes half-time 60 to producer-facing 120 with low confidence.

2026-04-28 15:35 — Added color-coded terminal pipeline logs for dev runs: validation, decode, Python/model analysis, prompt packaging, aggregation, warnings, MIDI paths, note counts, and timings.

2026-04-28 14:15 — Created stream for the next accuracy step: source-aware transcription beyond the experimental full-mix bass tracker.

## Open questions
_Things blocked on user input. Remove when resolved._

---

## 🔍 Audit Report

> **Required:** After every audit request, paste the full standardized report here.
> Do NOT leave the audit only in chat — it must be anchored here so the next session has it.
> Format: `.platform/workflow.md` → Stream / Feature Analysis Protocol → Step 4 template.
> After a clean re-audit (all 🟢), remove this section before stream closure.

_Status: not yet run_
