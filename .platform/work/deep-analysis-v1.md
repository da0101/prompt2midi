---
stream_id: stream-deep-analysis-v1
slug: deep-analysis-v1
type: feature
status: in-progress
agent_owner: claude-code
domain_slugs: [audio-analysis, composition-engine]
repo_ids: [repo-primary]
base_branch: main
git_branch: feature/analysis-ui-v1
created_at: 2026-04-28
updated_at: 2026-04-28
closure_approved: false
---

# deep-analysis-v1

## Scope

- Genre detection: CLAP zero-shot (laion/larger_clap_music via transformers), fallback MFCCs heuristic
- Chord detection: librosa chroma per beat → template matching → progression per bar
- Drum pattern: onset detection on Demucs drum stem → kick/snare/hat 16th grid
- Track structure: laplacian segmentation → sections, energy arc
- Timbre descriptors: MFCCs + spectral → bright/dark/warm/harsh for Gemini

## Done criteria

- [ ] genre_detection.py: returns real genre label (or fallback) with confidence
- [ ] chord_detection.py: returns chord progression e.g. ["Am","F","C","G"]
- [ ] drum_analysis.py: returns kick/snare/hat onset grids from drum stem
- [ ] structure_analysis.py: returns section count + energy arc
- [ ] composition.py uses detected chords when available
- [ ] composition.py uses detected drum pattern when available
- [ ] Gemini receives full analysis bundle
- [ ] All tests pass
- [ ] `.platform/memory/log.md` appended

## Resume state

- **Last updated:** 2026-04-28 — claude-code
- **Current focus:** Implementing 4 new modules in parallel
- **Blockers:** none

## Progress log

2026-04-28 — Stream registered, executing

## Open questions

_None._

---

## 🔍 Audit Report

_Status: not yet run_
