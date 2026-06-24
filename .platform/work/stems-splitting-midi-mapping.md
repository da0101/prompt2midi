---
stream_id: stream-stems-splitting-midi-mapping
slug: stems-splitting-midi-mapping
type: feature
status: in-progress
agent_owner: codex
domain_slugs: [audio-analysis, composition-engine, local-orchestration, juce-plugin]
repo_ids: [prompt2midi]
base_branch: develop
git_branch: feature/stems-splitting-midi-mapping
created_at: 2026-05-06
updated_at: 2026-06-23
closure_approved: false
---

# stems-splitting-midi-mapping

_Metadata rules: `stream_id` must be `stream-<slug>`, `slug` must match the filename, `status` must match `work/ACTIVE.md`, and `updated_at` should change whenever ownership or state changes._

## Scope
- Improve stem splitting and MIDI mapping for generated ACE output, not the original reference track.
- Detect stem/instrument roles dynamically from generated audio. Do not hardcode a fixed stem list or always emit bass/drums/chords/melody when the audio does not contain them.
- Build a source-aware MIDI mapping layer that listens to separated stems, identifies actual musical roles, extracts notes/events accurately, and writes only justified MIDI files.
- Surface method, confidence, limitations, and missing-role explanations so the UI can tell the producer what was actually found.
- Out of scope for the first pass: claiming perfect transcription, using copyrighted reference stems as reusable music assets, or bypassing local-first architecture.

## Done criteria
- [ ] Pipeline uses ACE/generated output as the legal source for stem splitting and MIDI extraction.
- [ ] Stem detection emits only roles that are actually present in the generated audio.
- [ ] MIDI files are role-specific and are created only for detected/justified stems.
- [ ] Each stem/MIDI asset includes method, confidence, limitations, and source path metadata.
- [ ] Tests cover at least: drums+pads only, bass+guitar only, full arrangement, missing/low-confidence stems, and no hardcoded-output regression.
- [ ] Manual QA runs against at least one ACE-generated output and audits audio/MIDI alignment by listening.
- [ ] `.platform/memory/log.md` appended.
- [ ] `decisions.md` updated for ACE-output-as-source and dynamic stem roles.

## Key decisions
_Append-only. Format: `YYYY-MM-DD — <decision> — <rationale>`_

2026-05-06 — Split and map ACE output, not reference audio — ACE output is the material the user can reuse legally; reference audio remains analysis inspiration/evidence only.
2026-05-06 — Dynamic stem roles, no fixed stem list — generated tracks may contain only drums+pads, bass+guitar, or other combinations, so the pipeline must detect present roles and only emit matching stems/MIDI.
2026-05-06 — Gemini is optional context, not the core MIDI mapper — accurate MIDI needs local source separation, source-specific transcription, onset/pitch cleanup, and confidence gates; Gemini can help label/review but should not own deterministic note extraction.
2026-05-06 — House bass mapping needs a specialized sub-bass analyzer plus musical interpreter — bouncy sub bass can be hard for generic polyphonic transcription, so the bass lane must combine monophonic F0 tracking, envelope/onset detection, beat-grid alignment, key constraints, and house-groove interpretation.

## Phased roadmap

### Phase 1 — ACE-source role map and safety rails
- Use generated ACE proxy audio as the input to stem splitting.
- Preserve only stems actually produced by the separator; do not fail when bass is missing.
- Detect active roles from stem audio and write `ace-stem-midi-map.json` with method, confidence, limitations, omitted roles, and planned MIDI targets.
- Keep MIDI export honest: planned/context-only entries are allowed, fake MIDI files are not.

### Phase 2 — Better local stem engines and repair pass
- Keep Demucs `htdemucs` as the reliable local baseline, with configurable `PROMPT2MIDI_DEMUCS_MODEL` for `htdemucs_6s` and future engines.
- Add an adapter boundary for stronger RoFormer/MDX-style separators when they are installable locally.
- Add stem recombination QA: compare sum-of-stems against the ACE mix, detect missing energy, and route residual energy to `other/residual` instead of losing it.
- Add repair tools per stem: loudness normalization, transient preservation for drums, residual blend for harmonic stems, and artifact warnings.

### Phase 3 — Role-specific MIDI extraction
- Drums: separated drum stem → onset-band MIDI with percussion labels and confidence.
- Bass: separated bass stem → house-aware sub-bass analyzer using low-frequency onset/envelope tracking, monophonic F0 tracking, optional Basic Pitch cross-check, octave/register cleanup, key constraints, and grid-aware quantization.
- Bass interpretation: classify 4-to-the-floor relation, offbeat bounce, syncopation, rests, slide/portamento suspicion, sidechain gaps, and bar-loop phrase shape before writing MIDI.
- Harmonic roles: guitar/piano/other stems → role-specific Basic Pitch or MT3-style model plus transient/chord-stab detection for short house stabs and chord/voicing cleanup.
- Emit only role-specific MIDI files for detected stems; skipped roles must include a reason.

### Phase 4 — Evaluation and manual QA loop
- Synthetic tests for role combinations plus real ACE-output QA.
- Audio/MIDI alignment reports, note-density sanity checks, recombined-stem loss checks, and producer-facing limitations.
- Promote the feature only after at least one full ACE output passes listening QA.

## Resume state
_Overwritten by `ab checkpoint` — the compact payload the next agent reads first. Keep this block under ~10 lines._

- **Last updated:** 2026-06-23 by danilulmashev
- **What just happened:** Prepared develop for continuation on another computer; committing and pushing current workflow metadata plus existing local commits.
- **Current focus:** —
- **Next action:** Continue from pushed develop on the other computer; audition the Desktop final-package-v2 folders in Ableton and use feedback to refine second-half/outro math without changing the drum export contract.
- **Blockers:** none

## Progress log
_Append-only. `ab checkpoint` prepends a dated line and auto-trims to the last 10 entries. Format: `YYYY-MM-DD HH:MM — <what happened>`._

2026-06-23 21:50 — Prepared develop for continuation on another computer; committing and pushing current workflow metadata plus existing local commits.

2026-06-23 21:48 — auto-checkpoint: Codex session ended without manual checkpoint

2026-05-29 19:03 — Regenerated Per Hammar candidate 3 and Dikka candidate 4 final packages with corrected drum packaging. Main arranged-stems keep Suno drums.wav; percussion-reference-stems contain arranged kick/snare/hihats/cymbals/toms guides from the existing better split folders. Added --percussion-reference-input-dir and tests.

2026-05-29 18:55 — Changed continuation arranger drum export contract: main arranged-stems keep original Suno drums.wav; DrumSep kick/snare/hihats/cymbals/toms are rendered through the same arrangement into percussion-reference-stems for Ableton rhythm replacement reference only. Updated tests and generation run log.

2026-05-29 12:42 — Fixed outro source rule so outro continues the same repeated post-drop groove slice with bass muted, and rendered Dikka v5

2026-05-29 12:30 — Fixed long second-half post-drop source selection so extended post-drop repeats developed bars 32-96 instead of restarting from intro

2026-05-29 12:22 — Rendered Dikka preserve-96 extra32 v3 with a longer 96-bar post-drop section so outro arrives later

2026-05-29 08:32 — Rendered Dikka preserve-96 Suno-priority arrangement after feedback that previous pass cut too much accepted Suno development

2026-05-28 23:14 — Added reusable second_half_extra_bars arranger control and rendered Dikka Suno-priority long-second-half test

2026-05-28 22:56 — Added generic reference-blueprint continuation mode, preserve_source_start_bars skip control, bar-snapped target rendering, regression tests, and rendered Dikka candidate-4 reference-blueprint v7 with source-audio copies.

## Open questions
_Things blocked on user input. Remove when resolved._

- Which local/AI listening model should be considered acceptable for role detection beyond DSP heuristics?
