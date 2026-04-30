---
stream_id: stream-analysis-ui-v1
slug: analysis-ui-v1
type: feature
status: in-progress
agent_owner: claude-code
domain_slugs: [audio-analysis, composition-engine, juce-plugin]
repo_ids: [repo-primary]
base_branch: main
git_branch: feature/analysis-ui-v1
created_at: 2026-04-28
updated_at: 2026-04-29
closure_approved: false
---

# analysis-ui-v1

## Scope

- **In scope:** Phase 3 (librosa BPM/key, genre heuristics, groove estimation) + Phase 5 (composition progress messages, clean JUCE display)
- **Out of scope:** madmom, essentia TF models, drum stem onset extraction

## Done criteria

- [ ] `analysis/enhanced_analysis.py` exists with librosa BPM/key (optional), genre heuristics, groove
- [ ] `analysis/analyze.py` enriches result with `genre` + `groove` + better BPM/key when librosa available
- [ ] `analysis/composition.py` emits per-step progress messages
- [ ] `Source/LocalApiClient.h` shows genre, groove, user-friendly warnings, clean layout
- [ ] All tests pass
- [ ] `.platform/memory/log.md` appended

## Key decisions

2026-04-28 — librosa is optional: try-import, fall back to existing analysis if absent
2026-04-28 — genre + groove added to analysis dict, fed into Gemini via composition.style

## Resume state
_Overwritten by `ab checkpoint` — the compact payload the next agent reads first. Keep this block under ~10 lines._

- **Last updated:** 2026-04-29 by danilulmashev
- **What just happened:** Added local 30-second sample.wav preview rendering to composition outputs; Python and Node tests pass; smoke sample generated at /tmp/prompt2midi-smoke-job/exports/sample.wav
- **Current focus:** —
- **Next action:** Close stale streams by resolving remaining audit items and updating Agentboard active state; decide whether to wire a real neural MusicGen provider behind composition.audio later
- **Blockers:** none

## Progress log

2026-04-29 15:24 — Added local 30-second sample.wav preview rendering to composition outputs; Python and Node tests pass; smoke sample generated at /tmp/prompt2midi-smoke-job/exports/sample.wav

2026-04-28 — Stream registered, executing

## Open questions

_None._

---

## 🔍 Audit Report

## 🔍 Audit — 2026-04-28

> Run via Stream / Feature Analysis Protocol — 3 parallel agents (Python, Node, JUCE).

### ⚡ Scorecard
| | 🐍 Python | 🎛️ Node | 🎹 JUCE |
|---|:---:|:---:|:---:|
| **Implementation** | 🟡 | 🟡 | 🟡 |
| **Tests** | 🟡 | 🟡 | N/A |
| **Security** | 🟢 | 🟢 | 🟢 |
| **Code Quality** | 🟡 | 🟡 | 🟡 |

**All 5 phases implemented and tests passing. 4 must-fix quality bugs before closure.**

### 🔴 Must Fix
1. `geminiPromptGenerator.js:51` — `fs.writeFileSync` blocks event loop in async function
2. `geminiPromptGenerator.js:48` — No timeout on Gemini call; job can stall indefinitely
3. `LocalApiClient.h:57` — `confidenceLabel()` leaks raw float ("0.82 high"); Phase 5 requires word only
4. `composition.py:61` — chord description always says "minor seventh stabs" regardless of mode

### 🟡 Should Fix Soon
5. `enhanced_analysis.py:14,36` — `import os` inside function body
6. `composition.py:117` — `clamp` lambda defined inside loop on every iteration
7. No test: `sunoGenerator` throws → catch branch
8. No test: `DISABLE_LIBROSA=1` → librosa fallback path
9. No test: `_infer_style` with pre-populated `genre` dict
10. `server.test.js:118,156` — weak `assert.ok(text)` truthy check

### ⚪ Known Limitations
- librosa confidence values hardcoded (0.82 BPM, 0.55 key floor)
- `write_reference_sketch_midi` ignores `bars` param — always 4 bars
- Progress jumps 35→75% with no intermediate update

### 🎯 Close Checklist
- [ ] Fix fs.writeFileSync → fs.promises.writeFile
- [ ] Add Gemini timeout
- [ ] Fix confidenceLabel raw float
- [ ] Fix mode-aware chord description
- [ ] Add 3 missing tests
- [ ] Move import os / clamp lambda
- [ ] Owner signs off
