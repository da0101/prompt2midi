# C++ / JUCE Conventions

Last updated: 2026-04-28

## Scope

Applies to `Source/`, `prompt2midi.jucer`, and generated Xcode project changes when touching plugin behavior.

## Rules

- Keep audio-thread code deterministic, allocation-conscious, and non-blocking.
- Never run HTTP requests, subprocesses, model inference, file scanning, or long analysis in `processBlock`.
- Keep `PluginProcessor` focused on host/audio state and `PluginEditor` focused on UI.
- Use JUCE async patterns for backend calls and UI updates.
- Treat Ableton stability as a product requirement: no blocking UI, no unhandled backend errors, no assumptions that the backend is already running.
- Preserve JUCE naming/style around existing classes unless there is a deliberate refactor.

## UI

- Build producer workflows directly: drag/drop, Analyze, progress, results, copy prompt, export MIDI, re-analyze.
- Avoid exposing implementation terms like subprocess, JSON, queue, or LLM runtime in user-facing UI.
- Prefer clear component ownership over a giant editor file as the UI grows.

## Build

- Current project source of truth is `prompt2midi.jucer` with Xcode Mac exporter.
- Avoid hand-editing `Builds/MacOSX/prompt2midi.xcodeproj/project.pbxproj` unless a build setting cannot be represented elsewhere.
