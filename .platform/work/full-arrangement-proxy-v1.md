---
stream_id: stream-full-arrangement-proxy-v1
slug: full-arrangement-proxy-v1
type: feature
status: in-progress
agent_owner: codex
domain_slugs: [audio-analysis, composition-engine, llm-midi-generation, local-orchestration, juce-plugin]
repo_ids: [repo-primary]
base_branch: main
git_branch: feature/full-arrangement-proxy-v1
created_at: 2026-05-02
updated_at: 2026-05-05
closure_approved: false
---

# full-arrangement-proxy-v1

_Metadata rules: `stream_id` must be `stream-<slug>`, `slug` must match the filename, `status` must match `work/ACTIVE.md`, and `updated_at` should change whenever ownership or state changes._

## Scope
- Build a full-song Arrangement Lock proxy workflow for SUNO: analyze the whole reference, copy its arrangement blueprint, generate section-level proxy audio with ACE, stitch a full-length guide on the same bar grid, and export the prompt/package.
- Product goal: preserve the reference section order, section lengths, transition timing, drops/breakdowns, and energy arc as the hard blueprint. Allow variation inside sections: new bass notes, fills, hook/melody contour, timbre, percussion details, and vocal identity.
- Preserve the existing 30-second ACE clean sample lane exactly as the fast testing path. This stream adds a separate Full Arrangement mode instead of replacing the working recipe.
- In scope: structure analysis, bar/downbeat grid, section detection, arrangement-lock confidence scoring, section cutting, per-section ACE candidate generation, candidate audition/selection, beat-safe stitching, progress UI, and export package.
- In scope: prediction/flagging when ACE is likely to struggle, especially dense vocal-rich/pop references, long melodic hooks, unusual tempo drift, weak section detection, or copyright-risky near-copy settings.
- Out of scope for this stream: Ableton manual work, Python-generated bassline overlays, production MIDI extraction as the primary proxy, YuE/Runpod as the default path, and fully automatic no-audition final selection.

## Arrangement Lock Contract

Full Arrangement mode must treat the reference arrangement as a locked blueprint, not just a style prompt.

Hard invariants:
- Same total duration target, within one beat unless the user trims or extends.
- Same section order and approximate section count.
- Same bar-aligned section starts and ends, with starts within one bar of the reference intent.
- Same macro energy curve: intros, grooves, breakdowns, buildups, drops, bridges, and outros happen in the same places.
- Same transition behavior at the arrangement level: pauses, filter-downs, risers, drop returns, and outro strip-downs are represented even when the exact sound design changes.

Allowed variation:
- New bass pitches and melodic contours.
- New hook/vocal identity and original lyrics or instrumental hook proxy.
- Different percussion fills, sound palette, synth patches, FX, and mix treatment.
- Per-section creative feedback such as more bass, less copy, more percussion, cleaner hook, or less glitch.

The UI should call this mode "Full Arrangement / Arrangement Lock", not "100% clone". Clone language is reserved for short sample testing presets.

## Done criteria
- [ ] Full Arrangement mode writes `arrangement-map.json`, `analysis-report.md`, `suno-structure-prompt.md`, section reference cuts, section candidate folders, and `full-arrangement-guide.wav`.
- [ ] The analyzer detects or estimates full reference BPM, key area, beat grid, downbeats, section boundaries, section roles, section energy, vocal/hook role, transition behavior, and warnings with explicit confidence.
- [ ] `arrangement-map.json` includes a blueprint fidelity block: total duration delta, section start deltas, section length deltas, confidence, and warnings before any ACE rendering starts.
- [ ] Sections are aligned to musical bars and exported with exact intended durations, pre-roll/tail policy, transition metadata, and locked target bar ranges.
- [ ] ACE generation is section-aware: each section receives a role-specific prompt and safe profile controls derived from the section and user direction.
- [ ] The stitcher trims/pads generated sections to the target bar grid, applies short crossfades, normalizes loudness, and reports drift/continuity warnings.
- [ ] UI supports Analyze Structure -> Generate Sections -> Audition Candidates -> Stitch Selected -> Export SUNO Package.
- [ ] The pipeline can run a 3-6 minute electronic/house reference end to end without drift or missing sections; manual listening confirms the proxy follows the reference arrangement blueprint, not only its general style.
- [ ] Tests pass: `npm test`, Node syntax checks for orchestration/UI files, Python compile check for changed `analysis/*.py`, and focused unit tests for section mapping/stitch metadata.
- [ ] Manual verification documented against at least two references: one house/tech-house track and one vocal/electro-pop track.
- [ ] `.platform/memory/log.md` appended
- [ ] `decisions.md` updated if any architectural choices were made

## Key decisions
_Append-only. Format: `2026-05-02 — <decision> — <rationale>`_

2026-05-02 — Use section-by-section full-song generation, not one-shot full-track ACE generation — ACE can make strong local proxies, but it does not guarantee full-song arrangement timing or continuity without external section control.
2026-05-02 — Keep the 30-second ACE sample lane separate — it is the validated fast test path and should not inherit full-song complexity.
2026-05-02 — Full-song proxy quality depends on a bar-grid contract — every section must have target start/end bars, duration, role, energy, and transition metadata before rendering.
2026-05-02 — Do not solve bassline gaps by overlaying Python note guesses — previous tests showed that synthetic overlays create off-key/off-tempo artifacts; ACE must be conditioned by real audio sections and better prompts.
2026-05-05 — Frame the feature as Arrangement Lock, not generic inspiration — the user wants the reference arrangement copied as a blueprint, with variation inside each section rather than a newly invented song structure.
2026-05-05 — Do not render audio before validating the arrangement map — if section boundaries, downbeats, or total duration are wrong, ACE output quality cannot rescue the full-song proxy.
2026-05-05 — Keep Docker optional and scoped to fragile analyzers — the native librosa/heuristic Arrangement Lock path is the reliable default; Docker is only a bounded All-In-One-Fix/NATTEN comparison lane and must degrade to warnings.

## Inline Research Findings

### External tools worth using

- All-In-One Music Structure Analyzer is the strongest first upgrade for this use case. Its published README says it predicts tempo, beats, downbeats, functional segment boundaries, and labels such as intro, verse, chorus, bridge, and outro. It returns JSON with BPM, beat arrays, downbeats, beat positions, and `segments`. Source: https://github.com/mir-aidj/all-in-one
- MSAF is useful as a research/fallback framework for structural segmentation algorithms and evaluation, but it is older and less directly product-ready than All-In-One for our needs. Source: https://msaf.readthedocs.io/en/latest/
- Librosa can support deterministic fallback segmentation using beat-synchronous CQT/MFCC features, recurrence matrices, path similarity, and spectral clustering. It is useful when All-In-One is missing or when we need a sanity-check second opinion. Source: https://librosa.org/doc/latest/auto_examples/plot_segmentation.html
- Essentia MusicExtractor is useful for producer descriptors: rhythm, tonal, low-level, loudness, and high-level classifiers. It should improve analysis reports and prompts, but it is not the main section detector. Source: https://essentia.upf.edu/reference/std_MusicExtractor.html

### Current repo status

- Existing code already has the start of this system:
  - `analysis/external_analyzers.py` can call All-In-One and Essentia when installed.
  - `analysis/full_arrangement.py` writes `arrangement-map.json`, `analysis-report.md`, `suno-structure-prompt.md`, and `full-arrangement-guide.mid`.
  - `analysis/full_guide_audio.py` can cut sections, call ACE per section, and concatenate a `full-arrangement-guide.wav` when explicitly enabled.
- The current implementation is a prototype, not a reliable product workflow:
  - It auto-selects the first ACE result for each section.
  - It does not expose section-level audition/selection in the UI.
  - It concatenates WAVs but does not yet enforce drift checks, exact bar-length repair, transition crossfade policy, or continuity scoring.
  - Section prompts are generic and not yet tuned from the successful ACE sample recipe.
  - It has no quality gate that says "ACE will probably fail on this reference; use another route or reduce similarity."

## Roadmap

## 2026-05-05 Docker Reliability Lane

- Added an optional `allin1-worker` Docker Compose service for All-In-One-Fix 2.0.4, Torch 2.7.1 CPU, madmom, ffmpeg, and a small image-time NATTEN CPU import patch.
- Added `scripts/run-allin1-docker.sh` and `--allin1-docker` runner support. The Docker analyzer is opt-in and bounded by `PROMPT2MIDI_ALLIN1_DOCKER_TIMEOUT_SECONDS` (default 300 seconds), then the pipeline falls back to the internal beat-grid/section analyzer.
- The Docker runner reuses `<output_dir>/stems` when available and passes All-In-One-Fix `--stems-from-dir ... --no-demucs`, so Docker does not redo source separation when the native pipeline already made stems.
- Verification: Docker image builds; `allin1fix --help` works in the container; Torch/NATTEN/All-In-One-Fix import smoke passes. A real 3:30 CPU smoke timed out at 300 seconds even with stems, so this lane is available for experiments/comparison but is not reliable enough to become the default on this Mac.

### Phase 0 - Freeze The Working Sample Lane

Why: the current 30-second ACE recipe finally gives repeatable usable results. Full-song work should not destabilize it.

Work:
- Keep `scripts/run-suno-proxy-pipeline.js` and `scripts/ace-proxy-ui.js` as the clean sample lane.
- Label the UI mode as Sample Proxy and add a separate Full Arrangement mode later.
- Keep MIDI/stems/full-guide rendering bypassed in sample mode.

Acceptance:
- Existing 30-second MJ/Tiga/house commands still work.
- No new full-song controls appear in sample mode unless explicitly switching modes.

### Phase 1 - Arrangement Blueprint Analysis Contract

Why: full-song proxy needs exact musical structure before generation. SUNO needs arrangement guidance, and ACE needs clean reference windows. For Arrangement Lock, this phase is the product foundation: a wrong map means a wrong song.

Work:
- Install/integrate All-In-One as the preferred full-structure analyzer.
- Use All-In-One outputs for BPM, beats, downbeats, beat positions, and functional segments.
- Add a deterministic fallback using current energy curve plus librosa beat-synchronous recurrence segmentation.
- Merge/repair segments into producer-usable sections: intro, groove, verse, hook, break, buildup, drop, outro.
- Align every boundary to bars/downbeats.
- Preserve the detected section order and original time proportions unless confidence is low and repair is explicitly reported.
- Detect transition behavior around each boundary: silence/pause, riser, filter-down, drum fill, drop return, breakdown entry, outro strip.
- Add an arrangement-lock score before generation. If confidence is low, UI must show "structure needs review" and let the user edit/approve boundaries before rendering.
- Add confidence and warnings:
  - weak beat/downbeat confidence
  - too many short fragments
  - tempo drift
  - no clear section labels
  - section boundary confidence below threshold
  - transition behavior uncertain
  - dense copyrighted vocal hook risk
  - ACE-risk score

Artifacts:
- `arrangement-map.json`
- `structure-debug.json`
- `arrangement-lock-report.json`
- `analysis-report.md`
- `suno-structure-prompt.md`
- optional visual/CSV section map

### Phase 2 - Section Cutter

Why: ACE should receive musically meaningful windows, not arbitrary 30-second cuts.

Work:
- Cut reference sections on bar-aligned boundaries with FFmpeg.
- Add configurable section max length. Long sections can be split into 16/32/64-bar chunks with shared role metadata.
- Add pre-roll/tail policy:
  - small pre-roll for groove continuity
  - short tail for transition feel
  - final exported section still trims to exact target duration
- Name cuts deterministically: `section-03_drop_bars-65-96_reference.wav`.

Artifacts:
- `sections/reference/*.wav`
- `sections/section-manifest.json`

### Phase 3 - Arrangement-Locked Section ACE Generation

Why: the same ACE settings should not be used for intro, drop, breakdown, hook, and outro.

Work:
- Build a section prompt from:
  - global analysis: genre, BPM, key, mood, energy, vocal role, bass/drum language
  - section role: intro/drop/break/hook/outro
  - locked bar range and target duration
  - transition-in and transition-out behavior
  - user direction
  - safe similarity profile
  - working ACE rules from the successful MJ/Tiga setup
- Prompt every section as "follow this section's arrangement role and timing, create original musical content inside it".
- Tune profile controls per section:
  - near-identical/high: stronger reference hold, lower variation
  - medium/medium-high: preserve groove and energy, change notes/hooks/palette
  - low: preserve tempo/key/style/energy/role map, but use lower direct reference hold and stronger originality guard
- Always generate multiple candidates per section.
- Do not auto-select final unless user enables auto mode.
- Store the original reference cut next to generated candidates so the user can A/B each section.

Artifacts:
- `sections/generated/section-03/candidate-1.wav` etc.
- `sections/reference/section-03_drop_reference.wav`
- `sections/generated/section-03/prompt.txt`
- `sections/generated/section-03/ace-request.json`
- `sections/generated/section-03/quality.json`

### Phase 4 - Audition And Candidate Selection

Why: full-song quality depends on human taste. Auto-picking candidates is why weak sections can ruin the whole guide.

Work:
- UI shows arrangement timeline with sections and candidates.
- Timeline first shows the reference arrangement map and requires approval when confidence is low.
- User can play reference section, play candidates, mark selected candidate, rerun one section, or lock a section.
- Allow per-section feedback: "more bass", "less copy", "more percussion", "less glitch", "keep vocal role", "instrumental only".
- Store feedback in `listen-feedback.jsonl` and feed it into reruns.

Acceptance:
- User can regenerate only one bad section without rerunning the full song.

### Phase 5 - Beat-Safe Stitcher

Why: separate ACE sections will not automatically sync. We need hard timing repair.

Work:
- Trim/pad each selected candidate to exact target section duration.
- Align section boundaries to the locked reference bar grid.
- Add short crossfades and optional transition silence preservation.
- Normalize loudness and low-end continuity.
- Report drift, repair actions, and per-section duration error.
- Export both full mix and debug stems if available from ACE output.

Artifacts:
- `full-arrangement-guide.wav`
- `full-arrangement-guide.mp3`
- `stitch-report.json`
- `arrangement-fidelity-report.json`
- `suno-package/`

### Phase 6 - SUNO Export Package

Why: final goal is not just audio; it is the best possible package for SUNO.

Work:
- Export:
  - full proxy guide audio
  - concise SUNO prompt under platform limits
  - long technical prompt/report for our records
  - arrangement map
  - selected-candidate manifest
- Include copyright-safe language:
  - original song
  - no copied lyrics/hooks/vocal identity
  - preserve arrangement role/timing/energy/groove behavior

### Phase 7 - Validation Matrix

Why: one successful track is not enough.

Test references:
- simple tech-house/minimal house
- vocal electronic/dance-pop
- pop/funk vocal-heavy reference
- track with breakdown/drop/silence
- track with unusual percussion swing

Metrics:
- same total duration within 1 beat
- section count/section roles match expected map
- section starts within 1 bar of reference intent
- breakdowns, drops, buildups, and outro happen at the same bars as the reference
- no obvious drift at stitched boundaries
- no random off-key/glitch artifacts in accepted sections
- user can replace a bad section without rerunning all sections

## Implementation Notes

- The safest path is not "generate a 6-minute song in one ACE call." The safer path is "analyze full structure, render controlled sections, audition, stitch."
- The arrangement map is the product contract. Do not start expensive ACE section rendering until the map has a usable confidence score or the user approves manual corrections.
- Full-song one-shot can be a later experiment for simple house tracks, but it should not be the default because it gives us little control over arrangement and failures are expensive.
- ACE should remain in the pipeline for the section audio because it produced the strongest free/local-ish proxy samples so far.
- YuE is not the default for this stream because tests produced poor MJ-style results and cost money on Runpod.
- MIDI/stem extraction should remain optional evidence/debug for this stream, not the main output path.

## Resume state
_Overwritten by `ab checkpoint` — the compact payload the next agent reads first. Keep this block under ~10 lines._

- **Last updated:** 2026-05-05 by danilulmashev
- **What just happened:** Renamed web UI to Inspiria and removed ACE/clone wording from user-facing UI copy, replacing it with local generator/reference-inspired language.
- **Current focus:** —
- **Next action:** Refresh the web UI and run a quick visual pass to confirm Inspiria branding and generation wording are visible.
- **Blockers:** none

## Progress log
_Append-only. `ab checkpoint` prepends a dated line and auto-trims to the last 10 entries. Format: `2026-05-02 HH:MM — <what happened>`._

2026-05-05 16:06 — Renamed web UI to Inspiria and removed ACE/clone wording from user-facing UI copy, replacing it with local generator/reference-inspired language.

2026-05-05 15:12 — Surfaced the SUNO optimized prompt in the Vue run sheet with preview/copy/open actions; expanded SUNO proxy prompt generation from 1000 to 2000 chars with detailed full-track structure/groove guidance.

2026-05-05 14:50 — Applied full-track render mode to the Vue web UI FormPanel; default mode now sends renderMode=full-track and duration=null to the ACE proxy API, with Ref start shown as auto and Duration shown as full reference.

2026-05-05 14:36 — Applied one-shot full-track duration mode to ACE proxy UI and SUNO proxy packaging; UI full-track now sends duration=full, forces ACE cover mode, and package step preserves the full generated proxy.

2026-05-05 14:00 — fixed CLI ACE wait spam by shortening long task labels, slowing wait-state animation to 5s, and tightening line width so wrapped terminals do not print hundreds of spinner frames; verified node check, npm test, and diff check

2026-05-05 13:36 — tested one-shot full-song ACE cover mode for Gruuving: skipped section splitting, rendered one 360.12s candidate in 6m30s at task=cover reference_guidance=0.18 audio_start_amount=0.08; output is tmp/gruuving-one-shot-full-cover-v1/exports/candidate-1.wav

2026-05-05 12:38 — debugged apparent CLI hang after Hugging Face warning; added deep-analysis progress for CLAP import/audio prep/model load/inference plus chord and structure substeps; verified python compile, node check, npm test, python unittest, and diff check

2026-05-05 12:35 — made CLI active progress visibly animate with a moving in-bar marker while keeping completed step lines stable; verified node check, npm test, and git diff check

2026-05-05 12:32 — Restored moving CLI spinner with a throttled one-second redraw interval, fixed-column formatting, and an env kill switch PROMPT2MIDI_PROGRESS_ANIMATION=0 to avoid high-frequency terminal pollution.

2026-05-05 12:30 — Adjusted CLI progress formatting: restored a safe static running spinner marker, moved elapsed time into a fixed column, reduced bar width, and aligned icon/bar/percent/time/label columns without reintroducing animation spam.

## Open questions
_Things blocked on user input. Remove when resolved._

- Should Full Arrangement mode default to manual section candidate selection, or should auto-select be allowed only after each section passes a quality gate?
- What is the first validation reference when implementation starts: a house track, Tiga, or MJ-style vocal pop?

---

## 🔍 Audit Report

> **Required:** After every audit request, paste the full standardized report here.
> Do NOT leave the audit only in chat — it must be anchored here so the next session has it.
> Format: `.platform/workflow.md` → Stream / Feature Analysis Protocol → Step 4 template.
> After a clean re-audit (all 🟢), remove this section before stream closure.

_Status: not yet run_
