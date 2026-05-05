---
stream_id: stream-full-arrangement-proxy-v1
slug: full-arrangement-proxy-v1
type: feature
status: planning
agent_owner: codex
domain_slugs: [audio-analysis, composition-engine, llm-midi-generation, local-orchestration, juce-plugin]
repo_ids: [repo-primary]
base_branch: main
git_branch: feature/full-arrangement-proxy-v1
created_at: 2026-05-02
updated_at: 2026-05-02
closure_approved: false
---

# full-arrangement-proxy-v1

_Metadata rules: `stream_id` must be `stream-<slug>`, `slug` must match the filename, `status` must match `work/ACTIVE.md`, and `updated_at` should change whenever ownership or state changes._

## Scope
- Build a full-song reference-inspired proxy workflow for SUNO: analyze the whole reference, map the arrangement, generate section-level proxy audio with ACE, stitch a full-length guide, and export the prompt/package.
- Preserve the existing 30-second ACE clean sample lane exactly as the fast testing path. This stream adds a separate Full Arrangement mode instead of replacing the working recipe.
- In scope: structure analysis, bar/downbeat grid, section detection, section cutting, per-section ACE candidate generation, candidate audition/selection, beat-safe stitching, progress UI, and export package.
- In scope: prediction/flagging when ACE is likely to struggle, especially dense vocal-rich/pop references, long melodic hooks, unusual tempo drift, weak section detection, or copyright-risky near-copy settings.
- Out of scope for this stream: Ableton manual work, Python-generated bassline overlays, production MIDI extraction as the primary proxy, YuE/Runpod as the default path, and fully automatic no-audition final selection.

## Done criteria
- [ ] Full Arrangement mode writes `arrangement-map.json`, `analysis-report.md`, `suno-structure-prompt.md`, section reference cuts, section candidate folders, and `full-arrangement-guide.wav`.
- [ ] The analyzer detects or estimates full reference BPM, key area, beat grid, downbeats, section boundaries, section roles, section energy, vocal/hook role, and warnings with explicit confidence.
- [ ] Sections are aligned to musical bars and exported with exact intended durations, pre-roll/tail policy, and transition metadata.
- [ ] ACE generation is section-aware: each section receives a role-specific prompt and safe profile controls derived from the section and user direction.
- [ ] The stitcher trims/pads generated sections to the target bar grid, applies short crossfades, normalizes loudness, and reports drift/continuity warnings.
- [ ] UI supports Analyze Structure -> Generate Sections -> Audition Candidates -> Stitch Selected -> Export SUNO Package.
- [ ] The pipeline can run a 3-6 minute electronic/house reference end to end without drift or missing sections; manual listening confirms the proxy follows the reference structure.
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

### Phase 0 - Freeze The Working Sample Lane

Why: the current 30-second ACE recipe finally gives repeatable usable results. Full-song work should not destabilize it.

Work:
- Keep `scripts/run-suno-proxy-pipeline.js` and `scripts/ace-proxy-ui.js` as the clean sample lane.
- Label the UI mode as Sample Proxy and add a separate Full Arrangement mode later.
- Keep MIDI/stems/full-guide rendering bypassed in sample mode.

Acceptance:
- Existing 30-second MJ/Tiga/house commands still work.
- No new full-song controls appear in sample mode unless explicitly switching modes.

### Phase 1 - Structure Analysis Contract

Why: full-song proxy needs exact musical structure before generation. SUNO needs arrangement guidance, and ACE needs clean reference windows.

Work:
- Install/integrate All-In-One as the preferred full-structure analyzer.
- Use All-In-One outputs for BPM, beats, downbeats, beat positions, and functional segments.
- Add a deterministic fallback using current energy curve plus librosa beat-synchronous recurrence segmentation.
- Merge/repair segments into producer-usable sections: intro, groove, verse, hook, break, buildup, drop, outro.
- Align every boundary to bars/downbeats.
- Add confidence and warnings:
  - weak beat/downbeat confidence
  - too many short fragments
  - tempo drift
  - no clear section labels
  - dense copyrighted vocal hook risk
  - ACE-risk score

Artifacts:
- `arrangement-map.json`
- `structure-debug.json`
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

### Phase 3 - Section-Aware ACE Generation

Why: the same ACE settings should not be used for intro, drop, breakdown, hook, and outro.

Work:
- Build a section prompt from:
  - global analysis: genre, BPM, key, mood, energy, vocal role, bass/drum language
  - section role: intro/drop/break/hook/outro
  - user direction
  - safe similarity profile
  - working ACE rules from the successful MJ/Tiga setup
- Tune profile controls per section:
  - near-identical/high: stronger reference hold, lower variation
  - medium/medium-high: preserve groove and energy, change notes/hooks/palette
  - low: preserve tempo/key/style/energy/role map, but use lower direct reference hold and stronger originality guard
- Always generate multiple candidates per section.
- Do not auto-select final unless user enables auto mode.

Artifacts:
- `sections/generated/section-03/candidate-1.wav` etc.
- `sections/generated/section-03/prompt.txt`
- `sections/generated/section-03/ace-request.json`
- `sections/generated/section-03/quality.json`

### Phase 4 - Audition And Candidate Selection

Why: full-song quality depends on human taste. Auto-picking candidates is why weak sections can ruin the whole guide.

Work:
- UI shows arrangement timeline with sections and candidates.
- User can play reference section, play candidates, mark selected candidate, rerun one section, or lock a section.
- Allow per-section feedback: "more bass", "less copy", "more percussion", "less glitch", "keep vocal role", "instrumental only".
- Store feedback in `listen-feedback.jsonl` and feed it into reruns.

Acceptance:
- User can regenerate only one bad section without rerunning the full song.

### Phase 5 - Beat-Safe Stitcher

Why: separate ACE sections will not automatically sync. We need hard timing repair.

Work:
- Trim/pad each selected candidate to exact target section duration.
- Align section boundaries to bar grid.
- Add short crossfades and optional transition silence preservation.
- Normalize loudness and low-end continuity.
- Report drift and repair actions.
- Export both full mix and debug stems if available from ACE output.

Artifacts:
- `full-arrangement-guide.wav`
- `full-arrangement-guide.mp3`
- `stitch-report.json`
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
- no obvious drift at stitched boundaries
- no random off-key/glitch artifacts in accepted sections
- user can replace a bad section without rerunning all sections

## Implementation Notes

- The safest path is not "generate a 6-minute song in one ACE call." The safer path is "analyze full structure, render controlled sections, audition, stitch."
- Full-song one-shot can be a later experiment for simple house tracks, but it should not be the default because it gives us little control over arrangement and failures are expensive.
- ACE should remain in the pipeline for the section audio because it produced the strongest free/local-ish proxy samples so far.
- YuE is not the default for this stream because tests produced poor MJ-style results and cost money on Runpod.
- MIDI/stem extraction should remain optional evidence/debug for this stream, not the main output path.

## Resume state
_Overwritten by `ab checkpoint` — the compact payload the next agent reads first. Keep this block under ~10 lines._

- **Last updated:** 2026-05-02 by danilulmashev
- **What just happened:** Created planning stream and roadmap for full-song reference-inspired proxy generation; documented structure-analysis research, section-by-section ACE plan, audition/stitch workflow, risks, and acceptance criteria.
- **Current focus:** .platform/work/full-arrangement-proxy-v1.md
- **Next action:** Start Phase 0/1 later: keep the 30-second ACE sample lane frozen, then implement/verify full-song structure analysis with All-In-One plus fallback before rendering audio.
- **Blockers:** none

## Progress log
_Append-only. `ab checkpoint` prepends a dated line and auto-trims to the last 10 entries. Format: `2026-05-02 HH:MM — <what happened>`._

2026-05-02 23:09 — Created planning stream and roadmap for full-song reference-inspired proxy generation; documented structure-analysis research, section-by-section ACE plan, audition/stitch workflow, risks, and acceptance criteria.

2026-05-02 22:55 — Created stream and roadmap for full-song arrangement proxy workflow based on repo audit and external MIR research.

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
