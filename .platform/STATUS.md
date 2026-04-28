# prompt2midi — Current Status

Last updated: 2026-04-28

prompt2midi is a local-first AI co-producer for Ableton Live. The current repo is a JUCE audio plugin shell; `promt.md` is the product and execution source of truth for building the full system: JUCE plugin, Node orchestrator, Python analysis engine, and local LLM interpretation/prompt generation.

---

## Feature areas

| Area | Status | Last touched | Notes |
|---|---|---|---|
| JUCE plugin shell | 🔵 Exists | 2026-04-28 | Editor now has file choose/drop, prompt input, async local API polling, result display, and copy prompt. JUCE is installed at `/Applications/JUCE`; Projucer regenerated the Xcode project and Debug builds pass. |
| Audio track ingestion | 🔵 Exists | 2026-04-28 | Plugin accepts WAV/WAVE/MP3 paths; backend decodes MP3 locally with FFmpeg before Python WAV analysis. |
| Python analysis engine | 🔵 Exists | 2026-04-28 | Dependency-free PCM WAV analyzer returns BPM/key estimates with confidence, energy curve, loudness, spectral basics, and warnings. |
| Node orchestrator | 🔵 Exists | 2026-04-28 | Local stdlib Node API has `/analyze`, `/status`, `/result`, job state, Python bridge, and prompt package generation. |
| MIDI extraction/export | 🔵 Exists | 2026-04-28 | Python writes `reference-sketch.mid` from estimated BPM/key and can also write experimental `bass-transcription.mid` from monophonic low-frequency tracking. Full source separation, melody, and chord extraction remain pending. |
| Local LLM interpretation | 🔵 Exists | 2026-04-28 | Deterministic local prompt generator turns structured analysis into producer summary and AI music prompt. Real local model runtime remains deferred. |
| Ableton UX | 🔵 Exists | 2026-04-28 | Functional MVP UI exists and builds as standalone/AU/VST3. It is accepted as temporary; full UI polish and in-host Ableton verification remain follow-ups. |

**Legend:**
- ✓ Done — shipped, tested, merged
- 🔵 Exists — in place but may need review
- ⧗ Pending — planned, not started
- ⚠ Flagged — known issue that needs attention
- 🔴 Deferred — decided to punt (reference `decisions.md` entry)

## Immediate priorities

1. **Verify and close audio-intelligence-v1** — MP3 support, confidence metadata, honest sketch labeling, and first-pass bass transcription are implemented.
2. **Plan deeper transcription** — next meaningful leap is source-aware bass/chord/melody extraction rather than full-mix heuristic tracking.
3. **Choose local LLM runtime** — deterministic prompt generation still needs replacement with the selected local model path.

## Open decisions

| # | Question | Deadline |
|---|---|---|
| 1 | Which local LLM runtime/model is the first supported target? | Before Phase 5 implementation |
| 2 | Should Node/Python live inside this repo or be split into sibling repos later? | Before backend grows beyond MVP |
| 3 | What exact Ableton plugin format is release-critical first: AU, VST3, or standalone? | Before release packaging |

## Release blocklist

Things that must be resolved before this project ships / goes live:

- [x] JUCE generated support files restored so Xcode builds.
- [ ] JUCE plugin can run in Ableton without blocking the audio thread.
- [x] Local backend startup, health check, job status, and failure states are handled from the plugin/backend contract.
- [x] Phase 1 analysis has repeatable accuracy checks for BPM/key on fixture tracks.
- [ ] No secrets, cloud-only assumptions, or raw user audio uploads are required for core use.

## Known gotchas (pinned)

Things that will bite every new session if not flagged upfront.

- **`promt.md` is the execution plan** — do not treat the current JUCE starter code as the full intended scope.
- **The processor is intentionally pass-through** — the MVP integration lives in the editor/backend path and does not process audio in `processBlock`.
- **Local-first is a hard product constraint** — design backend and LLM integrations so the main workflow works without cloud APIs.
- **Audio-thread safety matters** — never do network/process/file-heavy work in `processBlock`.
- **JUCE build depends on local generated files** — `JuceLibraryCode/` is generated locally by Projucer and ignored by git, so rerun Projucer if a clean checkout cannot build.

## File size violations

> Global rule: max ~300 lines per file. Track known offenders here so they get split before being added to.

- _None yet_

---

For focused context, start with `.platform/work/BRIEF.md` and the domain files under `.platform/domains/`.
