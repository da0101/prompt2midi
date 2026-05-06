---
stream_id: stream-inspired-loop-engine-v1
slug: inspired-loop-engine-v1
type: feature
status: done
agent_owner: claude-code
domain_slugs: [composition-engine, audio-analysis, llm-midi-generation, local-orchestration, juce-plugin]
repo_ids: [repo-primary]
base_branch: main
git_branch: feature/inspired-loop-engine-v1
created_at: 2026-04-28
updated_at: 2026-05-05
closure_approved: true
---

# inspired-loop-engine-v1

## Scope

- **In scope:** Phase 1 (result contract reframe — add `composition` object) + Phase 2 (deterministic composition engine — generate bass/drums/chords/melody/full_loop MIDI + summary.json + prompt.txt stub)
- **In scope:** Update Node passthrough, JUCE display, tests
- **Out of scope:** Phase 3 (better ML analysis), Phase 4 (Gemini SUNO prompt), Phase 5 (full UI redesign beyond result display), Phase 6 (full test suite beyond composition engine basics)

## Done criteria

- [x] `analysis/composition.py` exists and generates all 5 MIDI files + summary.json + prompt.txt
- [x] `exports/midi/bass.mid`, `drums.mid`, `chords.mid`, `melody.mid`, `full_loop.mid` are produced
- [x] `exports/summary.json` written with composition metadata
- [x] Python result includes top-level `composition` key
- [x] Node passes `composition` + `export_dir` through to job result
- [x] JUCE `summarizeResult()` shows generated loop package (not raw midi_assets)
- [x] `python3 -m unittest analysis/test_feature_extraction.py` passes
- [x] `npm test` passes
- [x] Python compile check passes
- [x] Node syntax check passes
- [x] `.platform/memory/log.md` appended

## Key decisions

2026-04-28 — composition.py is dependency-free stdlib only — consistency with rest of analysis pipeline
2026-04-28 — SUNO prompt is a stub in Phase 2; Phase 4 will add Gemini call — keep phases independent
2026-04-28 — full_loop.mid uses MIDI format type 1 — standard for multi-track DAW import

## Resume state
_Overwritten by `ab checkpoint` — the compact payload the next agent reads first. Keep this block under ~10 lines._

- **Last updated:** 2026-05-05 by codex
- **What just happened:** Owner confirmed this stream is in good shape; remaining config/tuning work should be tracked separately.
- **Current focus:** Closed.
- **Next action:** Archived.
- **Blockers:** none

## Progress log

2026-05-05 — Owner confirmed stream is in good shape; closed and archived during Agentboard cleanup. Remaining fine-tuning belongs in a follow-up stream.

2026-05-05 — Cleanup audit: preserved prior notes but reset current next action to the original inspired-loop closure checklist; ACE diagnostic UI work should be tracked under proxy/full-arrangement work, not this stream.

2026-05-05 00:06 — Temporarily disabled the Raw reconstruction diagnostic/second pipeline at UI and proxy entry points: 100% diagnostic preset options are commented out, the UI always sends reconstructionDiagnostic=false, and the proxy ignores stale diagnostic flags while preserving the normal 1/1 clone downgrade guard.

2026-05-04 23:58 — Fixed accidental clone path: unchecking Raw reconstruction diagnostic from 100% presets now switches Vue controls to normal near-identical 0.42/0.20 seed -1; proxy also downgrades stale non-diagnostic 1/1 requests and logs a warning.

2026-05-04 23:46 — Ran split ab-review audit with UI and backend agents. Verdict is REQUEST CHANGES: stale embedded ACE UI lacks reconstruction/preset controls, full Python feature test file fails two assertions, seed/batch/env clamp behavior lacks coverage, web/dist artifact should be ignored.

2026-05-04 23:22 — Adjusted clone preset calibration after listening feedback: non-100 presets now use random seed -1 so candidates vary; 75 moved to 0.56/0.30, 50 to 0.36/0.14, 25 to 0.20/0.06; diagnostic 75 now uses strong source-guided wording.

2026-05-04 23:11 — Recalibrated 25/50/75 preset source-conditioning values because ACE treated 0.70/0.50 as near-copy; 75 now uses 0.42/0.18, 50 0.28/0.10, 25 0.16/0.04.

2026-05-04 22:56 — Adjusted raw reconstruction diagnostic so it respects closeness sliders: 100% remains closest reconstruction, while 75/50/25 use diagnostic bypass without asking ACE for a literal reconstruction.

2026-05-04 22:29 — Added raw ACE reconstruction diagnostic mode that can bypass Gemini/preflight/anti-copy prompt guards when explicitly enabled, while keeping normal creative presets unchanged.

2026-05-04 21:55 — Replaced ACE preset list with eight percentage presets: 25/50/75/100 close and matching tribal-drum variants that apply a tribal percussion prompt.

2026-05-04 21:51 — Added ACE preset selector for safe inspired, close test, stronger close test, and max diagnostic slider/seed recipes.

2026-05-04 21:43 — Rewrote ACE form tooltip copy into simpler producer-facing explanations and verified the web build.

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
- [x] Fix GM program change in `midi_extraction.py:70`
- [x] Fix bass range test or add note clamp
- [x] Add Node tests: composition=null + export_dir
- [x] Remove dead `evidence` param
- [x] Remove stale `midi_notes` strings
- [x] Owner signs off → closure

## Cleanup Note — 2026-05-05

This stream was accepted by the owner and closed. The 2026-05-04/05 ACE reconstruction diagnostic entries are historical context from proxy UI work and should not drive any future loop-engine action.
