# Feature Brief — prompt2midi

> Read this first — every session, every agent (Claude, Codex, Gemini).
> 30-second orientation: what we're building, why, and where we stand.

**Feature:** Local AI co-producer for Ableton
**Status:** Planning
**Stream file:** `work/vertical-slice-mvp.md`

---

## What we're building

prompt2midi is both a prompt-to-MIDI tool and a full audio-track analysis assistant. The product vision in `promt.md` is the source of truth: users work inside Ableton, drop in a reference track or enter a prompt, and receive structured music analysis, MIDI assets, and AI-ready generation prompts.

The architecture is local-first: JUCE plugin UI, local Node orchestrator, Python analysis engine, and local LLM interpretation layer.

## Why

The goal is to give producers a practical AI co-producer that translates songs and ideas into reusable production knowledge without forcing them out of their DAW.

## What done looks like

- Ableton/JUCE plugin accepts an audio file or natural-language prompt without blocking the DAW.
- Local backend runs analysis jobs and returns progress/results reliably.
- Python engine returns structured BPM/key/energy/loudness first, then sections, stems, chords, and MIDI.
- LLM layer turns structured data into producer-friendly explanation and high-quality AI-music prompts.
- User can copy prompts and export MIDI/assets into their Ableton workflow.

## Architecture decisions locked

- `promt.md` is the exact execution plan unless the human owner changes it.
- Local-first is mandatory for the core workflow; cloud APIs may not be required.
- JUCE stays a UI/client layer and must not run heavy analysis on the audio thread.
- Python owns signal analysis and MIDI extraction; Node owns orchestration and job/API state.

## Current state

The repo currently contains a JUCE starter audio plugin with a prompt text box and Generate button. Backend, Python analysis, MIDI extraction, drag/drop, progress, and result UI are planned but not implemented.

See `work/ACTIVE.md` for stream status. The active planning stream is `vertical-slice-mvp`.

## Relevant context

- `.platform/domains/juce-plugin.md` — Ableton/JUCE UI and host integration.
- `.platform/domains/audio-analysis.md` — Python feature extraction, segmentation, and MIDI analysis.
- `.platform/domains/local-orchestration.md` — Node API, queue, job status, and component integration.
- `.platform/domains/llm-midi-generation.md` — LLM interpretation, prompt generation, and MIDI output.
- `.platform/architecture.md` — end-to-end topology and invariants.

**Do not load:** `Builds/MacOSX/*.xcodeproj/project.pbxproj` unless changing build settings.
**Never load:** `work/archive/*`

## Key files

- `promt.md`
- `prompt2midi.jucer`
- `Source/PluginProcessor.cpp`
- `Source/PluginProcessor.h`
- `Source/PluginEditor.cpp`
- `Source/PluginEditor.h`
