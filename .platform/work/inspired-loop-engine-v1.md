---
stream_id: stream-inspired-loop-engine-v1
slug: inspired-loop-engine-v1
type: feature
status: in-progress
agent_owner: claude-code
domain_slugs: [composition-engine, audio-analysis, llm-midi-generation, local-orchestration, juce-plugin]
repo_ids: [repo-primary]
base_branch: main
git_branch: feature/inspired-loop-engine-v1
created_at: 2026-04-28
updated_at: 2026-04-30
closure_approved: false
---

# inspired-loop-engine-v1

## Scope

- **In scope:** Phase 1 (result contract reframe — add `composition` object) + Phase 2 (deterministic composition engine — generate bass/drums/chords/melody/full_loop MIDI + summary.json + prompt.txt stub)
- **In scope:** Update Node passthrough, JUCE display, tests
- **Out of scope:** Phase 3 (better ML analysis), Phase 4 (Gemini SUNO prompt), Phase 5 (full UI redesign beyond result display), Phase 6 (full test suite beyond composition engine basics)

## Done criteria

- [ ] `analysis/composition.py` exists and generates all 5 MIDI files + summary.json + prompt.txt
- [ ] `exports/midi/bass.mid`, `drums.mid`, `chords.mid`, `melody.mid`, `full_loop.mid` are produced
- [ ] `exports/summary.json` written with composition metadata
- [ ] Python result includes top-level `composition` key
- [ ] Node passes `composition` + `export_dir` through to job result
- [ ] JUCE `summarizeResult()` shows generated loop package (not raw midi_assets)
- [ ] `python3 -m unittest analysis/test_feature_extraction.py` passes
- [ ] `npm test` passes
- [ ] Python compile check passes
- [ ] Node syntax check passes
- [ ] `.platform/memory/log.md` appended

## Key decisions

2026-04-28 — composition.py is dependency-free stdlib only — consistency with rest of analysis pipeline
2026-04-28 — SUNO prompt is a stub in Phase 2; Phase 4 will add Gemini call — keep phases independent
2026-04-28 — full_loop.mid uses MIDI format type 1 — standard for multi-track DAW import

## Resume state
_Overwritten by `ab checkpoint` — the compact payload the next agent reads first. Keep this block under ~10 lines._

- **Last updated:** 2026-04-30 by danilulmashev
- **What just happened:** Added local traceability for generation runs: candidate manifests, JSONL run registry, feedback recorder CLI, and default all-candidates/await-user-selection ACE behavior instead of automatic final candidate selection.
- **Current focus:** —
- **Next action:** User can give per-level feedback for the Movements candidates; record picks/notes in listen-tests and, for future runs, candidate-manifest feedback records.
- **Blockers:** none

## Progress log

2026-04-30 08:21 — Added local traceability for generation runs: candidate manifests, JSONL run registry, feedback recorder CLI, and default all-candidates/await-user-selection ACE behavior instead of automatic final candidate selection.

2026-04-30 08:01 — Added medium-low and medium-high similarity levels, generated both Movements intermediate test runs into project tmp, and recorded accepted feedback for the corrected four-level v2 run.

2026-04-30 07:38 — Generated all four Movements v2 similarity levels into project tmp with corrected ACE mapping.

2026-04-30 07:05 — Recorded user feedback that four similarity levels sounded too similar; fixed ACE level mapping so low uses text2music style conditioning, medium/high/near-identical use separated source strengths, and prompts preserve micro-percussion/vocal-chop roles.

2026-04-30 06:57 — Generated Movements high and near-identical ACE-Step runs with locked groove-led tech house direction; recorded both in listen-tests log.

2026-04-30 06:38 — Generated Movements low-similarity ACE run at /tmp/prompt2midi-movements-low-v1/exports using locked groove-led tech house/minimal-deep-tech/Mood Child style label; auto-selected candidate-3; recorded run in listen log; fixed composition style classifier so explicit tech-house directions are not mislabeled as hip-hop/trap due to words like funky; corrected this run's prompt.txt.

2026-04-30 06:25 — Recorded corrected Movements feedback: medium result worked for house/tech-house lane but should not be treated as a globally accepted bassline solution; researched Manda Moor style classification.

2026-04-30 06:20 — Recorded positive Movements medium feedback, fixed direct CLI MP3 preparation by reusing backend ffmpeg decode, and verified CLI help plus focused tests.

2026-04-30 06:11 — Added ACE candidate override support, fixed prompt contamination for medium/low similarity, generated Movements medium test at /tmp/prompt2midi-movements-medium-v2/exports, and started structured listen-test log.

2026-04-30 00:15 — User identified Smooth Criminal high-v5 candidate 2 as the better high-similarity result; copied it over sample.wav for that run and added a generic CLI/manual candidate override so future runs can promote whichever candidate wins listening review.

## Open questions

_None._

---

## 🔍 Audit — 2026-04-28

> Run via Stream / Feature Analysis Protocol — 1 parallel agent (sonnet).

### ⚡ Scorecard

| | 🖥️ Python | 🎛️ Node | 🎹 JUCE |
|---|:---:|:---:|:---:|
| **Implementation** | 🟡 | 🟢 | 🟢 |
| **Tests** | 🟡 | 🟡 | — |
| **Security** | 🟢 | 🟢 | — |
| **Code Quality** | 🟡 | 🟢 | 🟡 |

**Bottom line:** Functionally complete, all tests pass. One quality bug (wrong GM program change on chords/melody MIDI) blocks clean closure.

### 🔴 Must Fix
1. `midi_extraction.py:70` — `\xc0\x20` (GM Acoustic Bass program change) inserted in all `include_meta=True` tracks. `chords.mid` and `melody.mid` open with wrong instrument in GM-aware DAWs.

### 🟡 Should Fix Soon
2. `composition.py:25` — `evidence: dict` dead parameter (accepted, never read)
3. `test_composition.py:44` — bass range assertion `<= 55` is root=38 specific; no clamp in code; would fail for key B
4. `test_composition.py:214` — `test_major_key_generates_major_chords` checks file existence only
5. `analyze.py:127` — `midi_notes` describes old transcription artifacts, not composition outputs
6. `server.test.js` — missing: prompt-only `composition: null` test + `export_dir` assertion

### ⚪ Known Limitations
- `_stub_suno_prompt` is a Phase 4 placeholder by design
- Melody stays in one octave (root to root+10) — sparse by spec
- `exports/` shared between `_promote_exports` and composition engine — no collision, implicit coupling

### 🎯 Close Checklist
- [ ] Fix GM program change in `midi_extraction.py:70`
- [ ] Fix bass range test or add note clamp
- [ ] Add Node tests: composition=null + export_dir
- [ ] Remove dead `evidence` param
- [ ] Remove stale `midi_notes` strings
- [ ] Owner signs off → closure
