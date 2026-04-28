---
domain_id: dom-juce-plugin
slug: juce-plugin
status: active
repo_ids: [prompt2midi]
related_domain_slugs: [local-orchestration, audio-analysis, llm-midi-generation]
created_at: 2026-04-28
updated_at: 2026-04-28
---

# juce-plugin

## What this domain does

This domain covers the Ableton-facing plugin: file/prompt input, progress display, result rendering, and export controls. JUCE is the user's main product surface but should stay a client/UI layer over local services.

## Backend / source of truth

- Source files currently live in `Source/PluginProcessor.*` and `Source/PluginEditor.*`.
- `Prompt2midiAudioProcessor` is currently template pass-through audio processing.
- `Prompt2midiAudioProcessorEditor` currently owns a multiline prompt input and Generate button.
- The plugin should call a local API for long-running work rather than doing analysis inside the plugin.
- Keep host/audio-thread stability as the primary invariant.

## Frontend / clients

- The plugin UI should eventually support drag/drop track input, Analyze, progress, BPM/key, structure, instrument breakdown, energy curve, prompt generation, and MIDI export.
- Producer-facing copy should be clear and DAW-native: no backend jargon in the UI.
- Result UI should remain responsive while jobs run.

## API contract locked

- Plugin submits local file paths/prompts to the local orchestrator.
- Plugin polls or subscribes to job progress rather than blocking.
- Plugin displays structured JSON fields and generated text/assets from Node.
- Do not require cloud credentials in the plugin for the core path.

## Key files

- `prompt2midi.jucer`
- `Builds/MacOSX/prompt2midi.xcodeproj/project.pbxproj`
- `Source/PluginProcessor.h`
- `Source/PluginProcessor.cpp`
- `Source/PluginEditor.h`
- `Source/PluginEditor.cpp`

## Decisions locked

- JUCE is the Ableton-facing UI/client, not the analysis engine.
- Do not perform heavy analysis, subprocess work, HTTP blocking, or file-heavy processing in `processBlock`.
- Start macOS/Ableton-first, using the existing JUCE/Xcode exporter.
- Keep UI controls mapped to producer workflows: analyze, copy prompt, export MIDI, re-analyze.
