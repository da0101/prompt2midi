---
stream_id: stream-project-cleanup-restructure-v1
slug: project-cleanup-restructure-v1
type: chore
status: archived
agent_owner: codex
domain_slugs: [audio-analysis, composition-engine, local-orchestration, llm-midi-generation, juce-plugin]
repo_ids: [repo-primary]
base_branch: develop
git_branch: develop
created_at: 2026-05-05
updated_at: 2026-05-06
closure_approved: true
---

# project-cleanup-restructure-v1

_Metadata rules: `stream_id` must be `stream-<slug>`, `slug` must match the filename, `status` must match `work/ACTIVE.md`, and `updated_at` should change whenever ownership or state changes._

## Scope
- Audit the repository for dead code, stale experiments, duplicated utilities, runtime artifacts, unclear ownership boundaries, and files that should be archived or removed.
- Propose a production-oriented folder structure, starting with `analysis/`, that groups files by responsibility instead of historical implementation order.
- Identify import, script, test, and documentation changes required before any folder moves.
- Keep local-first product constraints intact: no network/runtime work in JUCE audio thread, Node owns orchestration, Python returns structured JSON, producer-facing UX language stays clean.
- Out of scope: changing product behavior, reducing local-first guarantees, or collapsing prompt-to-MIDI and audio-track analysis into one narrower product.

## Done criteria
- [x] Parallel audit covers `analysis/`, backend/scripts/orchestration, JUCE/plugin/exporter files, docs/platform/runtime artifacts, and test/import risk.
- [x] Cleanup candidates are classified as remove, archive, keep, or refactor with evidence.
- [x] Proposed folder layout includes migration order and direct import rewrite strategy.
- [x] Verification plan lists exact tests/checks to run after each restructuring phase.
- [x] User approves file moves and no importer-only shim files.
- [x] First restructuring pass lands with tests green.
- [x] `.platform/memory/log.md` appended
- [x] `decisions.md` updated if any architectural choices were made

## Key decisions
_Append-only. Format: `2026-05-05 — <decision> — <rationale>`_

2026-05-05 — Audit before restructuring — project is preparing for production, so file moves and deletions need evidence, sequencing, and verification before implementation.
2026-05-05 — Direct package imports, no shims — user requested no importer-only middleman files, so moved Python modules are called through their real package paths and Node uses `python -m ...`.

## Resume state
_Overwritten by `ab checkpoint` — the compact payload the next agent reads first. Keep this block under ~10 lines._

- **Last updated:** 2026-05-06 by codex
- **What just happened:** cleanup stream was committed, merged through PR #1, branch deleted, and archived during platform documentation refresh
- **Current focus:** —
- **Next action:** none; stream closed
- **Blockers:** none

## Progress log
_Append-only. `ab checkpoint` prepends a dated line and auto-trims to the last 10 entries. Format: `2026-05-05 HH:MM — <what happened>`._

2026-05-05 19:38 — final stream audit passed: ab doctor clean, staged and unstaged diff checks clean, stale moved-path sweep clean, brief back under 60 lines

2026-05-05 19:29 — expanded restructure complete: grouped scripts into dev/setup/pipelines/packaging/feedback/services, moved requirements into requirements/, grouped docs into backend/pipelines/qa, preserved npm command names, updated internal paths/docs/platform notes, fixed All-In-One Docker adapter moved wrapper path, verification green

2026-05-05 19:16 — second layout audit complete: no more production-code moves recommended in this pass; scripts is the only remaining folder worth a future grouping pass; ignored generation/listening JSONL runtime logs and removed local __pycache__ directories

2026-05-05 19:04 — terminal QA generated two full-length ACE candidates from Yello reference at high/0.52 similarity with tribal percussion; fixed companion prompt regression that mislabeled long similarity instructions and requested lead vocals for instrumental hook proxies

2026-05-05 18:50 — first cleanup pass complete: analysis package layout, direct imports, dead/generated file removal, docs/platform updates, tests green

2026-05-05 — Registered stream and dispatched parallel read-only audit agents.
2026-05-05 — Completed parallel audits and began approved restructuring without compatibility shim files.
2026-05-05 — Finished first restructuring pass: moved `analysis/` by responsibility, removed dead/generated tracked files, updated docs/platform paths, and verified checks.

## Open questions
_Things blocked on user input. Remove when resolved._

_None yet._

---

## Audit Report

### Summary
- `analysis/` was a flat 45-file namespace with direct imports like `from feature_extraction import ...`; folder moves require direct package imports and `python -m` entry points.
- Clearly removable/generated tracked files: `web/dist/*`, `web/src/lib/dropPath.js`, and unreferenced `analysis/instrument_analysis.py`.
- Archive, not delete yet: old deterministic groove render experiment files, because tests still cover `groove_to_midi.py`.
- Backend/scripts have duplicated orchestration and ACE UI/API code; that needs a later split after this Python/package pass.
- JUCE source is live, but `Builds/` is missing and docs/scripts need a clean Projucer regeneration path before production packaging.

### First Pass Plan
- Move `analysis/` into responsibility folders: `core`, `detectors`, `midi`, `arrangement`, `reference`, `composition`, `generation`, `packaging`, `tests`, and `archive`.
- Rewrite imports to direct package paths. Do not create compatibility shim files.
- Update Node callers from file execution to `python -m analysis...`.
- Remove tracked generated UI output and confirmed dead helpers.
- Verify with Python compile, Python tests, Node tests, web build, and `ab doctor`.
