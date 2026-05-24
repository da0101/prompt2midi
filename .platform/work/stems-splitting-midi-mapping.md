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
updated_at: 2026-05-24
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

- **Last updated:** 2026-05-24 by danilulmashev
- **What just happened:** debugged full-track auto fallback failure; found Dikka continuation seed failed at 0.56/0.30 while prior successful run used 0.56/0.20; capped UI and fallback continuation source controls to 0.56/0.20
- **Current focus:** —
- **Next action:** restart web UI/API and rerun Dikka full-track; verify fallback logs lowered controls and produces a 120s seed before full-track extension
- **Blockers:** none

## Progress log
_Append-only. `ab checkpoint` prepends a dated line and auto-trims to the last 10 entries. Format: `YYYY-MM-DD HH:MM — <what happened>`._

2026-05-24 16:40 — debugged full-track auto fallback failure; found Dikka continuation seed failed at 0.56/0.30 while prior successful run used 0.56/0.20; capped UI and fallback continuation source controls to 0.56/0.20

2026-05-24 13:24 — debugged ACE UI full-track failure where long references submitted over-limit generation; capped full-source sample duration via PROMPT2MIDI_REFERENCE_SAMPLE_MAX_DURATION and updated UI copy

2026-05-05 22:56 — fixed ACE candidate packaging so --map-stems builds stem/MIDI assets for every generated candidate; added house-aware bass-stem cleanup that keeps sub notes and writes per-candidate stem-bass.mid

2026-05-05 22:36 — confirmed drum MIDI failure was fallback onset hallucination; changed ambiguous house/electro fallback to conservative 4/4 kick-clap-offbeat-hat pattern and kept it debug-only

2026-05-05 22:20 — ran Yello 30s/2-candidate ACE stem+MIDI QA from 40s start; fixed --map-stems boolean parsing and added dependency-free drum onset fallback so generated ACE output produces stem-drums.mid plus stem-bass.mid

2026-05-05 21:33 — researched stem separation and MIDI mapping approach; implemented ACE-output role map, flexible Demucs stem preservation, proxy --map-stems hook, and dynamic role tests

2026-05-05 21:20 — registered new feature stream for ACE-output stem splitting and dynamic MIDI mapping; branch feature/stems-splitting-midi-mapping created from develop; decisions recorded in stream/domain/memory

2026-05-06 00:00 — registered stream for ACE-output stem splitting and dynamic MIDI mapping; branch created from `develop`
2026-05-06 01:10 — Phase 1 implementation added flexible Demucs stem preservation, ACE-output role mapping JSON, proxy-run `--map-stems` hook, and regression tests
2026-05-06 01:25 — refined Phase 3 around house-aware bouncy sub-bass mapping, 4-to-the-floor interpretation, percussion/stab extraction, and grid/key-constrained MIDI cleanup
## Open questions
_Things blocked on user input. Remove when resolved._

- Which local/AI listening model should be considered acceptable for role detection beyond DSP heuristics?
