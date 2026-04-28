---
stream_id: stream-audio-intelligence-v1
slug: audio-intelligence-v1
type: feature
status: in-progress
agent_owner: codex
domain_slugs: [audio-analysis, llm-midi-generation, local-orchestration, juce-plugin]
repo_ids: [prompt2midi]
base_branch: feature/vertical-slice-mvp
git_branch: feature/audio-intelligence-v1
created_at: 2026-04-28
updated_at: 2026-04-28
closure_approved: false
---

# audio-intelligence-v1

_Metadata rules: `stream_id` must be `stream-<slug>`, `slug` must match the filename, `status` must match `work/ACTIVE.md`, and `updated_at` should change whenever ownership or state changes._

## Scope
- Improve Phase 1 musical usefulness beyond the vertical-slice placeholder: more honest BPM/key confidence, clearer warnings, and less misleading MIDI output.
- Add a better audio-import path decision and implementation plan for MP3 or explicit WAV-only UX, starting from the open decoder question.
- Replace the placeholder bassline behavior with either a clearly labeled sketch generator or a first real extraction path that can be tested against fixtures.
- Keep the existing local-first Node/Python/JUCE architecture and avoid cloud-only dependencies.
- Out of scope: polished UI redesign, release installer/notarization, full stem separation, and production-grade chord/melody transcription.

## Done criteria
- [x] Reference-track analysis no longer presents placeholder MIDI as if it were accurate transcription.
- [x] BPM/key/energy outputs have documented confidence/warnings and fixture-backed regression tests.
- [x] MP3 support is either implemented with a chosen decoder or intentionally deferred with a clear product/API reason.
- [x] Backend and Python tests pass: `npm test`, `python3 -m unittest analysis/test_feature_extraction.py`, and Python compile check.
- [x] JUCE Debug `prompt2midi - All` still builds after any UI/client contract changes.
- [x] Manual verification documents behavior on at least one WAV reference and the current fake-music fixture path if retained.
- [x] `.platform/memory/log.md` appended
- [x] `decisions.md` updated if any architectural choices were made

## Key decisions
_Append-only. Format: `2026-04-28 — <decision> — <rationale>`_

- 2026-04-28 — Build on vertical-slice MVP — The local Node/Python/JUCE contract is now proven; this stream should improve musical validity, not re-platform the app.
- 2026-04-28 — Use FFmpeg as the MP3 boundary adapter — Keep Python analysis WAV-only while allowing common reference-track imports locally.

## Resume state
_Overwritten by `ab checkpoint` — the compact payload the next agent reads first. Keep this block under ~10 lines._

- **Last updated:** 2026-04-28 by danilulmashev (auto)
- **What just happened:** (auto) bb6752b: Implement audio intelligence v1
- **Current focus:** —
- **Next action:** (auto-saved from commit — update next action manually)
- **Blockers:** none

## Progress log
_Append-only. `ab checkpoint` prepends a dated line and auto-trims to the last 10 entries. Format: `2026-04-28 HH:MM — <what happened>`._

2026-04-28 13:07 — (auto) bb6752b: Implement audio intelligence v1

2026-04-28 13:07 — Implemented audio-intelligence v1: MP3 boundary decoding via FFmpeg, BPM/key confidence and warnings, reference-sketch MIDI labeling, JUCE MP3 picker support, docs/tests/platform updates, and manual smoke on the provided MP3.

2026-04-28 12:46 — (auto) 9be99d0: Checkpoint audio intelligence stream

2026-04-28 13:00 — Implemented MP3 boundary decoding and renamed generated MIDI to a reference sketch.
2026-04-28 13:05 — Verified backend, Python, manual MP3 smoke, and full JUCE Debug build.

2026-04-28 12:46 — Started the audio-intelligence-v1 stream after closing vertical-slice MVP.

2026-04-28 12:45 — (auto) 5344af4: Start audio intelligence stream

2026-04-28 12:45 — Created stream after closing vertical-slice MVP.

## Open questions
_Things blocked on user input. Remove when resolved._

- Resolved for this pass: do all three narrowly. MP3 uses FFmpeg, BPM/key expose confidence/warnings, and MIDI is labelled as a generated reference sketch.

---

## 🔍 Audit Report

> **Required:** After every audit request, paste the full standardized report here.
> Do NOT leave the audit only in chat — it must be anchored here so the next session has it.
> Format: `.platform/workflow.md` → Stream / Feature Analysis Protocol → Step 4 template.
> After a clean re-audit (all 🟢), remove this section before stream closure.

_Status: not yet run_
