---
stream_id: stream-deep-analysis-v1
slug: deep-analysis-v1
type: feature
status: superseded
agent_owner: claude-code
domain_slugs: [audio-analysis, composition-engine]
repo_ids: [repo-primary]
base_branch: main
git_branch: feature/deep-analysis-v1
created_at: 2026-04-28
updated_at: 2026-05-05
closure_approved: true
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

- **Last updated:** 2026-05-05 — codex
- **Current focus:** Closed as superseded.
- **Next action:** If this capability still matters, open a fresh verification stream for real-audio checks: CLAP/cache behavior, chord fixture accuracy, drum-stem onset grids, structure segmentation, and composition deltas from detected chords/drums.
- **Blockers:** none

## Progress log

2026-05-05 — Parallel audit found code exists but original criteria were never verified as written; closed as superseded rather than done.

2026-05-05 — Cleanup audit: stream is stale, not listed as a live focus in `BRIEF.md`, and all done criteria remain unchecked; marked blocked rather than falsely active.

2026-04-28 — Stream registered, executing

## Open questions

_None._

---

## 🔍 Audit Report

2026-05-05 — Parallel audit: archive/close as superseded, not done. Implemented pieces exist: CLAP genre path with unavailable fallback, chroma/template chord detection, drum-stem onset grids, local structure segmentation, pipeline wiring, and composition use of detected chords/drums. Gaps: no MFCC genre fallback despite scope, no direct correctness tests for real CLAP/chords/drums/structure, Gemini receives compact selected analysis rather than the full bundle. If needed, reopen as a fresh verification stream.
