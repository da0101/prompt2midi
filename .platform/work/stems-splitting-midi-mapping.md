---
stream_id: stream-stems-splitting-midi-mapping
slug: stems-splitting-midi-mapping
type: feature
status: planning
agent_owner: codex
domain_slugs: [audio-analysis, composition-engine, local-orchestration, juce-plugin]
repo_ids: [prompt2midi]
base_branch: develop
git_branch: feature/stems-splitting-midi-mapping
created_at: 2026-05-06
updated_at: 2026-05-05
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

## Resume state
_Overwritten by `ab checkpoint` — the compact payload the next agent reads first. Keep this block under ~10 lines._

- **Last updated:** 2026-05-05 by danilulmashev
- **What just happened:** registered new feature stream for ACE-output stem splitting and dynamic MIDI mapping; branch feature/stems-splitting-midi-mapping created from develop; decisions recorded in stream/domain/memory
- **Current focus:** —
- **Next action:** inspect current ACE output artifacts, stem separation code, MIDI extraction code, and result asset contracts; then propose phased implementation architecture before coding
- **Blockers:** none

## Progress log
_Append-only. `ab checkpoint` prepends a dated line and auto-trims to the last 10 entries. Format: `YYYY-MM-DD HH:MM — <what happened>`._

2026-05-05 21:20 — registered new feature stream for ACE-output stem splitting and dynamic MIDI mapping; branch feature/stems-splitting-midi-mapping created from develop; decisions recorded in stream/domain/memory

2026-05-06 00:00 — registered stream for ACE-output stem splitting and dynamic MIDI mapping; branch created from `develop`

## Open questions
_Things blocked on user input. Remove when resolved._

- Which ACE output format(s) should be the first supported source: stitched full proxy WAV, individual section candidates, or both?
- Which local/AI listening model should be considered acceptable for role detection beyond DSP heuristics?
