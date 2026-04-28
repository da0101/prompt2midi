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

- Source files currently live in `Source/PluginProcessor.*`, `Source/PluginEditor.*`, `Source/LocalApiClient.h`, and `Source/ModernTheme.h`.
- `Prompt2midiAudioProcessor` is intentionally pass-through audio processing for the MVP.
- `Prompt2midiAudioProcessorEditor` owns WAV/MP3 choose/drop, prompt input, async local API polling, result display, and copy prompt.
- `LocalApiClient.h` labels MIDI assets by confidence level and limitations: reference sketch is generated, model MIDI is Basic Pitch output, stem-aware bass is Demucs plus Basic Pitch, and heuristic bass is full-mix tracking.
- The plugin should call a local API for long-running work rather than doing analysis inside the plugin.
- Keep host/audio-thread stability as the primary invariant.

## Frontend / clients

- The plugin UI should eventually support drag/drop track input, Analyze, progress, BPM/key, structure, instrument breakdown, energy curve, prompt generation, and MIDI export.
- Producer-facing copy should be clear and DAW-native: no backend jargon in the UI.
- Result UI should remain responsive while jobs run.

## API contract locked

- Plugin submits local file paths/prompts to the local orchestrator.
- Plugin polls or subscribes to job progress rather than blocking.
- Plugin displays structured JSON fields, generated text/assets, analysis warnings, and `midi_assets` metadata from Node.
- Plugin output copy must not imply full transcription accuracy unless the backend exposes a source-aware extraction result.
- Do not require cloud credentials in the plugin for the core path.

## Key files

- `prompt2midi.jucer`
- `Builds/MacOSX/prompt2midi.xcodeproj/project.pbxproj`
- `Source/PluginProcessor.h`
- `Source/PluginProcessor.cpp`
- `Source/PluginEditor.h`
- `Source/PluginEditor.cpp`
- `Source/LocalApiClient.h`
- `Source/ModernTheme.h`

## Decisions locked

- JUCE is the Ableton-facing UI/client, not the analysis engine.
- Do not perform heavy analysis, subprocess work, HTTP blocking, or file-heavy processing in `processBlock`.
- Start macOS/Ableton-first, using the existing JUCE/Xcode exporter.
- Keep UI controls mapped to producer workflows: analyze, copy prompt, export MIDI, re-analyze.
