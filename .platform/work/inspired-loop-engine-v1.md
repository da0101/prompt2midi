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
updated_at: 2026-04-28
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

- **Last updated:** 2026-04-28 by danilulmashev (auto)
- **What just happened:** (auto) eae0e55: Add deterministic composition engine and product contract reframe
- **Current focus:** —
- **Next action:** (auto-saved from commit — update next action manually)
- **Blockers:** none

## Progress log

2026-04-28 19:49 — (auto) eae0e55: Add deterministic composition engine and product contract reframe

2026-04-28 — Stream registered, plan presented, execution starting

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
