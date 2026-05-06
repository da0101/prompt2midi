# prompt2midi — Architecture

Last updated: 2026-05-06

prompt2midi is a local-first AI co-producer for Ableton Live. It analyzes reference tracks, extracts musical evidence, creates original MIDI/prompt packages, and prepares optional local audio or SUNO proxy artifacts. The core runtime is JUCE UI/client -> local Node orchestration -> Python analysis/generation -> Node aggregation -> JUCE result/export UI.

`promt.md` remains the product execution source of truth. This file describes the current architecture that agents should assume when changing code.

The project is open source. Contributions are welcome as long as they preserve local-first behavior, honest confidence labels, and the reference-inspired transformation goal.

## 1. Product Shape

The user is a producer or artist working in a DAW or preparing ideas for SUNO. They should be able to drop in a reference, add a direction, and get:

- BPM/key/energy/structure facts with confidence and warnings.
- Editable MIDI sketches and transcription evidence.
- An original inspired loop package.
- A producer-readable prompt package for SUNO or similar tools.
- Optional local proxy/sample audio for auditioning before upload.

There are two product lanes:

- DAW inspiration starter: generate ideas, MIDI, arrangement notes, and prompt language that a producer can continue in Ableton, Logic, FL Studio, Bitwig, or another DAW.
- Pre-SUNO tool: transform a reference/inspired idea into a cleaner prompt, structure guide, and optional proxy package for finishing in SUNO or continuing locally.

The product goal is reference-inspired transformation, not copying. Generated MIDI is product output; extracted/transcribed MIDI is evidence and must be labeled with limitations.

## 2. Runtime Flow

```text
Ableton / JUCE plugin
  -> localhost Node API
  -> job store + progress events
  -> FFmpeg MP3 decode when needed
  -> Python analysis package
  -> optional engines: librosa/scipy, CLAP, Basic Pitch, Demucs, All-In-One Docker
  -> composition / arrangement / local audio generation helpers
  -> Node prompt aggregation + optional Gemini SUNO prompt
  -> JUCE result display + copy/export actions
```

## 3. Components

| Layer | Current files | Responsibility |
|---|---|---|
| JUCE plugin | `Source/PluginEditor.*`, `Source/PluginProcessor.*`, `Source/LocalApiClient.h`, `Source/ModernTheme.h` | DAW-facing client only: choose/drop audio, submit jobs, poll progress, show confidence-aware results. Audio processing stays pass-through. |
| Node backend | `backend/server.js`, `backend/lib/*` | Local API, job state, MP3/WAV validation, FFmpeg decode, Python invocation, prompt aggregation, normalized errors. |
| Python analysis | `analysis/analyze.py`, `analysis/core/*`, `analysis/detectors/*` | Structured audio facts: BPM, key, loudness, energy, spectral features, chords, drums, structure, genre/groove hints. |
| MIDI/evidence | `analysis/midi/*` | MIDI writing, Basic Pitch integration, Demucs/source-aware candidates, heuristic fallbacks, provenance labels. |
| Composition | `analysis/composition/*` | Original inspired loop MIDI package: bass, drums, chords, melody, full_loop, summary, prompt. |
| Arrangement/proxy | `analysis/arrangement/*`, `analysis/reference/*`, `analysis/generation/*`, `analysis/packaging/*` | Full Arrangement / Arrangement Lock maps, guide MIDI, SUNO proxy packages, optional ACE/MusicGen local audio. |
| Web/dev tooling | `web/`, `scripts/dev/*`, `scripts/pipelines/*` | Local ACE/proxy UI, pipeline runners, setup helpers, listening feedback tooling. |
| Platform memory | `.platform/` | Agent workflow state, domains, conventions, decisions, gotchas, status. |

## 4. API Contract

Node exposes:

- `GET /health`
- `POST /analyze`
- `GET /status?id=<job_id>`
- `GET /result?id=<job_id>`

The start request returns quickly with `job_id`. Long-running analysis happens in the background. Status/results are JSON and must be safe for the plugin to display.

Result payloads include:

- `analysis`
- `composition`
- `full_arrangement`
- `suno_prompt`
- `interpretation`
- `midi_files`
- `midi_assets`
- `midi_notes`
- `export_dir`
- `export_files`

Clients must tolerate optional fields because deeper extraction depends on installed engines.

## 5. Optional Engines

Core analysis must run without optional ML services. Optional engines improve output but must degrade to warnings:

- FFmpeg for MP3 decode.
- `librosa`/`scipy` for stronger BPM/key/chord/structure analysis.
- CLAP for genre tags.
- Basic Pitch for transcription candidates.
- Demucs for stem-aware evidence.
- All-In-One Docker for fragile structure-model comparison.
- ACE-Step local API for proxy/sample audio.
- AudioCraft/MusicGen fallbacks for local sample generation.
- Gemini for higher-quality SUNO prompts when `GEMINI_API_KEY` is present.

## 6. Known Weak Areas

Stem splitting and MIDI mapping are the next major quality frontier:

- Demucs-style stems can bleed and misattribute instruments.
- Full-mix transcription can produce extra notes, bad registers, and wrong instrument ownership.
- Bass/drum/chord/melody mapping is useful evidence but not yet production-grade.
- Extracted MIDI must be auditioned and edited in Ableton before being treated as final.

The next production-readiness work should improve source-aware MIDI mapping, quantization, note filtering, confidence labels, and full JUCE AU/VST integration.

## 7. Branch / Release Model

- `develop` is the default integration branch.
- Feature branches start from `develop` and merge back into `develop`.
- `main` is release-only. Promote by merging `develop` into `main` and tagging the release.

See `.platform/conventions/git-flow.md`.

## 8. Invariants

1. Core workflow must remain local-first.
2. JUCE must not do heavy analysis, network calls, subprocesses, or file-heavy work in `processBlock`.
3. Node owns orchestration, job state, progress, and aggregation.
4. Python returns structured JSON and local file paths, not producer prose.
5. Optional engines must fail soft with warnings, not break the base workflow.
6. Producer-facing copy must be honest about confidence and limitations.
7. Cloud APIs are optional enhancements only.
8. `develop` is the default branch for work; `main` is for release merges/tags.
