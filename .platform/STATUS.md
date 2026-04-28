# prompt2midi — Current Status

Last updated: 2026-04-28

prompt2midi is a local-first AI co-producer for Ableton Live. The current repo is a JUCE audio plugin shell; `promt.md` is the product and execution source of truth for building the full system: JUCE plugin, Node orchestrator, Python analysis engine, and local LLM interpretation/prompt generation.

---

## Feature areas

| Area | Status | Last touched | Notes |
|---|---|---|---|
| JUCE plugin shell | 🔵 Exists | 2026-04-28 | Starter processor/editor compile surface exists with prompt input and Generate button. |
| Audio track ingestion | ⧗ Pending | — | Needs drag/drop file handling from the plugin into the local backend. |
| Python analysis engine | ⧗ Pending | — | Phase 1 target: BPM, key, spectral features, energy curve, loudness JSON. |
| Node orchestrator | ⧗ Pending | — | Needs local REST API, job queue, progress status, Python process bridge, and LLM handoff. |
| MIDI extraction/export | ⧗ Pending | — | Later phase: bassline/melody/chord MIDI generation and Ableton-friendly export. |
| Local LLM interpretation | ⧗ Pending | — | Must transform structured JSON into producer insights and AI-music prompts. |
| Ableton UX | ⧗ Pending | — | Needs progress, results panels, waveform/sections, prompt copy, and export buttons. |

**Legend:**
- ✓ Done — shipped, tested, merged
- 🔵 Exists — in place but may need review
- ⧗ Pending — planned, not started
- ⚠ Flagged — known issue that needs attention
- 🔴 Deferred — decided to punt (reference `decisions.md` entry)

## Immediate priorities

1. **Define the vertical-slice MVP** — JUCE plugin can submit a local audio file or prompt, Node can run a job, Python returns basic analysis, and UI displays results.
2. **Build Phase 1 analysis contract** — stable JSON for BPM, key, energy curve, and loudness before adding segmentation, stems, or MIDI.
3. **Keep JUCE non-blocking** — all backend calls and file processing must happen off the audio thread and must not freeze Ableton.

## Open decisions

| # | Question | Deadline |
|---|---|---|
| 1 | Which local LLM runtime/model is the first supported target? | Before Phase 5 implementation |
| 2 | Should Node/Python live inside this repo or be split into sibling repos later? | Before backend grows beyond MVP |
| 3 | What exact Ableton plugin format is release-critical first: AU, VST3, or standalone? | Before release packaging |

## Release blocklist

Things that must be resolved before this project ships / goes live:

- [ ] JUCE plugin can run in Ableton without blocking the audio thread.
- [ ] Local backend startup, health check, job status, and failure states are handled from the plugin.
- [ ] Phase 1 analysis has repeatable accuracy checks for BPM/key on fixture tracks.
- [ ] No secrets, cloud-only assumptions, or raw user audio uploads are required for core use.

## Known gotchas (pinned)

Things that will bite every new session if not flagged upfront.

- **`promt.md` is the execution plan** — do not treat the current JUCE starter code as the full intended scope.
- **The plugin is currently only a shell** — processor code is template pass-through and the Generate button has no integration yet.
- **Local-first is a hard product constraint** — design backend and LLM integrations so the main workflow works without cloud APIs.
- **Audio-thread safety matters** — never do network/process/file-heavy work in `processBlock`.

## File size violations

> Global rule: max ~300 lines per file. Track known offenders here so they get split before being added to.

- _None yet_

---

For focused context, start with `.platform/work/BRIEF.md` and the domain files under `.platform/domains/`.
