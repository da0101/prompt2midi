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
- **What just happened:** Reran last-best ACE MJ proxy approach with prompt-order fix; produced four 30s candidates in tmp/mj-inspired-proxy-best-rerun-v1 and packaged candidate 2 for Suno. Also researched ElevenLabs Music API via agent.
- **Current focus:** —
- **Next action:** User auditions candidates; decide whether to refine ACE prompt/profile or test ElevenLabs text-to-music API as a non-local paid option.
- **Blockers:** none

## Progress log

2026-05-01 21:01 — Reran last-best ACE MJ proxy approach with prompt-order fix; produced four 30s candidates in tmp/mj-inspired-proxy-best-rerun-v1 and packaged candidate 2 for Suno. Also researched ElevenLabs Music API via agent.

2026-05-01 20:31 — Ran 15s ACE MJ rhythm/bass test from MJ-testing reference section at 8s. First run exposed a prompt-order bug where user production detail was buried/truncated behind analysis text; patched audio_generation._condition_prompt to keep user direction before groove fingerprint. Reran corrected ACE test under tmp/ace-mj-15s-rhythm-bass-test-v2-prompt-lock/exports; candidate 1 passed level gate and candidate 2 failed quality floor. Stopped ACE API.

2026-05-01 19:55 — User rejected v5 clean bass-proxy/scaffold path because ace-control-scaffold.wav sounded chaotic/not tempo-key locked. Patched ACE pipeline so bass-proxy is diagnostic-only, skipped automatically for rich/vocal references unless PROMPT2MIDI_ALLOW_EXPERIMENTAL_RICH_BASS_PROXY=1, and scaffold files are labeled internal/non-listenable.

2026-05-01 19:36 — User feedback on v4: bass notes changed but bass tone sounded gross/unstable like puking, not a professional groove. Patched bass-proxy source so the control scaffold uses a clean rounded bass guide voice for ACE conditioning, lowered guide level in proxy mix, added prompt guard against gurgling/growling/wobbling bass artifacts, and generated v5 2x15s candidates under tmp/mj-bass-calibration-15s-v5-clean-bass-proxy/exports. Stopped ACE API.

2026-05-01 19:22 — User rejected v2 because all candidates still copied original MJ bass notes. Added --bass-proxy-source mode: ACE conditioning now can use high-passed real reference percussion/upper energy plus generated in-key replacement bass guide, so raw original bass pitch is removed before ACE hears it. Pure scaffold source timed out; bass-proxy source completed 2x15s candidates under tmp/mj-bass-calibration-15s-v4-bass-proxy-source/exports. Global harmonic guard remains in place.

2026-05-01 17:48 — Generated MJ 15s v2 different-bass-notes ACE calibration at tmp/mj-bass-calibration-15s-v2-different-notes/exports; recorded user feedback that v1 candidates 1 and 2 had the right percussion/bass presence and MJ spirit but copied bass pitch notes; patched global harmonic guard so ACE prompts require in-key, tonal, resolved bass/hooks/stabs/fills/effects and forbid out-of-tune/off-key artifacts.

2026-05-01 17:33 — Ran 15s one-passage ACE calibration from original local MJ reference WAV at 8s, focused on capturing both drum rhythm/percussion and audible melodic/rhythmic bassline in the initial generation. Produced 4 candidates under tmp/mj-bass-calibration-15s-v1/exports and stopped ACE.

2026-05-01 17:24 — Deleted failed bass refinement outputs and reran v8 liked candidates 1-3 through ACE with source-conditioned high profile, lower source lock, higher noise, and explicit significantly audible bass instruction. Generated two variants per source candidate under ace-refine-bass-v3 and stopped ACE API.

2026-05-01 17:02 — Refined v8 liked candidates 1-3 through ACE itself after rejecting synthetic bass overlay approach. Generated two ACE bass-refinement variants per source candidate under ace-refine-bass, stopped local ACE API, and recorded feedback rule: no random post-generated musical notes.

2026-05-01 16:43 — Recorded v8 feedback: user liked candidates 1-3 drum/percussion layers, rejected candidate 4, and identified missing bassline as the blocker. Added reusable bassline_overlay refinement and exported bass-forward-v2 versions plus Suno packages for candidates 1-3.

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
