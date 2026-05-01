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
updated_at: 2026-05-01
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

- **Last updated:** 2026-05-01 by danilulmashev
- **What just happened:** Tightened Suno proxy lane for copyright-safe MJ-style testing: added reference section controls to proxy/reference runners, made proxy runner default to early-character selection, fixed audio_generation so env/CLI section strategy is honored, generated v5 from MJ-testing.m4a with explicit 8s section and forced vocal-hook ACE mode, packaged candidate 4 for Suno.
- **Current focus:** —
- **Next action:** User should audition tmp/mj-inspired-proxy-v5-start8-vocal-hook candidates and Suno package; if vocal-hook ACE output is unstable, keep ACE for groove/instrumental proxies and route vocal-rich pop/funk references to a different generator or section-by-section proxy strategy.
- **Blockers:** none

## Progress log

2026-05-01 14:42 — Tightened Suno proxy lane for copyright-safe MJ-style testing: added reference section controls to proxy/reference runners, made proxy runner default to early-character selection, fixed audio_generation so env/CLI section strategy is honored, generated v5 from MJ-testing.m4a with explicit 8s section and forced vocal-hook ACE mode, packaged candidate 4 for Suno.

2026-05-01 13:33 — Adjusted copyright-safe Suno proxy boundary from user feedback: Suno prompt is now compact under 1000 chars and asks Suno to preserve/polish the generated proxy, not invent missing layers. Updated proxy-run ACE default prompt to request a complete full-arrangement proxy with drums, bass, percussion, synth stabs, layered keys, comping, hits, transitions, and optional stable original vocal phrases; no longer forces instrumental unless --instrumental is passed.

2026-05-01 13:22 — Corrected Suno workflow around copyright-safe proxy demos: added suno_proxy_package.py, npm run suno:proxy, npm run suno:proxy-run. The new lane analyzes the source reference locally, generates ACE proxy candidates, refuses to package the original reference as proxy audio, and writes Suno upload artifacts only from generated proxy audio. Ran MJ-testing.m4a proxy test; generated 4 ACE candidates and packaged candidate 3 under tmp/mj-inspired-proxy-v1/suno-proxy-package.

2026-05-01 12:52 — Added fast Suno Cover prep lane: local reference analysis, best 30s audio seed extraction, Suno prompt/report/instructions/manifest output, npm run suno:prepare wrapper, and focused unit test. Verified on MJ-testing.m4a into tmp/suno-mj-testing-v3.

2026-05-01 10:05 — Disabled automatic ACE control-scaffold routing after listening feedback showed scaffold-conditioned ACE output was unusable; scaffold remains explicit-only behind --control-scaffold while normal bass-lock prompts return to real-reference ACE conditioning.

2026-05-01 09:40 — Added ACE control-scaffold conditioning path: pipeline renders an in-key bass/drum scaffold from analysis/groove and can route bass-lock prompts through it before ACE; generated Tiga 15s validation run at tmp/tiga-control-scaffold-v1-15s.

2026-05-01 09:18 — Added safe FFT reference groove extraction for fast ACE lane, concrete bass/kick/hat grid prompting, chord-root key correction for ACE payloads, and generated Tiga bass-lock v3 grid/key validation candidates.

2026-05-01 08:54 — Added bass rhythm/sound lock intent for ACE: detects same bass rhythm/sound with different notes, strengthens source conditioning, preserves bass tone/rhythm, moves bass-lock guard to front of ACE prompt, expands anti-glitch bass negatives, and generated Tiga bass-lock v1/v2 validation batches.

2026-05-01 08:20 — Added ACE preflight suitability/router with hidden controls, prompt-directed similarity, very-high profile, early ace-preflight export, effective similarity metadata, vocal-aware ACE payloads, and generated a Tiga prompt-directed validation batch.

2026-04-30 23:30 — Generated Tiga near-identical vocal fast ACE run, 30s, 4 candidates at tmp/tiga-fast-near-identical-vocal-v1-30s/exports; candidate 3 suggested though all candidates have timbre/noisy warnings

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
