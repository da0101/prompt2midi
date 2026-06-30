---
domain_id: dom-audio-analysis
slug: audio-analysis
status: active
repo_ids: [prompt2midi]
related_domain_slugs: [local-orchestration, llm-midi-generation, juce-plugin]
created_at: 2026-04-28
updated_at: 2026-06-30
---

# audio-analysis

## What this domain does

This domain covers the Python audio intelligence engine: extracting musical facts from WAV/MP3 files and returning structured JSON. It is the foundation for producer insights, arrangement understanding, MIDI export, and AI prompt generation.

## Backend / source of truth

- Implemented Phase 1 modules: `analysis/core/feature_extraction.py`, `analysis/analyze.py`, `analysis/midi/midi_extraction.py`, `analysis/midi/bass_transcription.py`, and `analysis/midi/source_transcription.py`.
- Full Arrangement / Arrangement Lock analysis now uses `analysis/arrangement/full_arrangement.py`, `analysis/arrangement/arrangement_sections.py`, `analysis/arrangement/arrangement_reports.py`, `analysis/arrangement/arrangement_lock.py`, and `analysis/arrangement/arrangement_lock_reports.py` to write `arrangement-map.json`, `arrangement-lock-report.json`, `structure-debug.json`, `analysis-report.md`, `suno-structure-prompt.md`, and `full-arrangement-guide.mid`.
- Section construction keeps major detected boundaries, merges tiny transition fragments, and splits overlong spans into phrase-sized producer sections so radio edits do not collapse into one giant intro.
- Beat/downbeat evidence is compared across optional All-In-One output, the local librosa fallback in `analysis/core/beat_grid.py`, structure-provided downbeats, and estimated BPM bars. `structure-debug.json` includes `bar_grid_candidates` so mismatches are auditable.
- Phase 2 output: BPM/key estimates with confidence, energy curve, loudness, spectral features, warnings, a `reference-sketch.mid` path, optional Basic Pitch model MIDI, optional Demucs stem-aware bass MIDI, and optional experimental `bass-transcription.mid`.
- Python still analyzes PCM WAV; MP3 is decoded by Node/FFmpeg before invoking Python.
- Current weak area: stem splitting and MIDI mapping are useful evidence, but not yet production-grade. Phase 1 now writes an ACE-output role map, but Demucs-style stems can still bleed, full-mix transcription can overgenerate, and bass/drum/chord/melody ownership still needs stronger cleanup.
- Next phases: add stem repair/recombination QA, source-aware MIDI mapping, quantization, note filtering, register selection, and DAW-ready confidence labels.
- For `stems-splitting-midi-mapping`, reusable stems and MIDI must come from ACE-generated output, not the original reference track.
- Stem roles must be detected dynamically from audio content. A track with only drums+pads should not emit bass/guitar MIDI; a track with only bass+guitar should not emit drums/pads MIDI.
- `analysis/midi/ace_stem_mapping.py` is the first ACE-output contract: it preserves only active generated-audio stem roles, records omitted roles, and writes planned/context-only MIDI targets without creating fake MIDI.
- House bass mapping must not depend only on generic polyphonic transcription. Bouncy sub bass needs a dedicated lane: low-frequency onset/envelope tracking, monophonic F0 estimation, optional Basic Pitch cross-check, key/register constraints, beat-grid quantization, and house-groove interpretation of 4-to-the-floor, offbeats, syncopation, rests, and sidechain gaps.
- House stabs need a separate transient harmonic lane over `other/guitar/piano` stems: detect short chord/stab onsets, estimate chord/register when confidence allows, and otherwise export rhythm/stab placeholders with limitations rather than invented voicings.
- Demucs stem separation is an optional isolated engine in `.venv-stems`; dependency-free analysis and Basic Pitch full-mix analysis must still work when it is absent.
- Drum-stem analysis computes onset rates per bar for kick, mid percussion, and high percussion. Long-track drum density must not be normalized by unique 16th-grid positions over the whole song; dense mid/high onset rates are promoted as `percussion_character: tribal_percussion` so ACE/SUNO prompts preserve conga/bongo/shaker-style movement.
- All-In-One-Fix can run in an optional Docker worker for the fragile NATTEN/torch structure model path. Enable it with `PROMPT2MIDI_ENABLE_ALLIN1_DOCKER=1` or `--allin1-docker`; it is bounded by `PROMPT2MIDI_ALLIN1_DOCKER_TIMEOUT_SECONDS` (default 300s) and falls back to the internal librosa/heuristic arrangement analyzer on timeout or failure.
- The Docker worker reuses precomputed stems from `<output_dir>/stems` when present, so Docker does not rerun local Demucs separation unless no stems are available.
- Python should return structured JSON only; interpretation/prose belongs to Node/LLM.
- ACE-Step cannot reliably render a single generation past ~6:10 (370 seconds). `_reference_sample_duration` in `analysis/analyze.py` enforces `ACE_STEP_MAX_DURATION_SECONDS = 370.0` as a hard ceiling on every single-render request (`--duration`/`--sample-duration`, including `full`/`reference`), independent of source track length or the UI's hardware-tier `PROMPT2MIDI_REFERENCE_SAMPLE_MAX_DURATION` override. Full-arrangement section-by-section rendering (`analysis/generation/full_guide_audio.py`) is not affected since each stitched section is already short.

## Frontend / clients

- JUCE displays BPM/key, energy curve, structure, instrument tags, chords, and export buttons derived from analysis output.
- Node orchestrator owns job lifecycle and invokes Python modules.

## API contract locked

- Phase 1 JSON shape starts with:
  - `bpm: number`
  - `bpm_confidence: number`
  - `key: string`
  - `key_confidence: number`
  - `energy_curve: array`
  - `loudness: number`
  - `warnings: array`
- Future analysis data should extend the contract without breaking existing UI fields.
- MIDI extraction fields must continue to expose method, confidence, and limitations. Do not present extracted MIDI as final arrangement material unless the source-aware path actually supports that confidence.
- Full Arrangement output includes `full_arrangement.arrangement_lock`, `blueprint_fidelity`, section `locked_bar_range`, `transition_in/out`, `boundary_confidence`, and generated report/debug paths.
- Arrangement Lock preserves short/radio-edit references as valid inputs via `reference_version.kind`, repairs sparse long-song maps into phrase sections when possible, and reports low-severity `phrase_subdivision_used` provenance when it does.
- Extended/club references with stable beat grids are normalized toward 8/16/32-bar producer phrases and report low-severity `phrase_grid_normalized` provenance. This is the preferred SUNO control shape because it avoids odd-length repeated groove fragments.
- Errors must be structured enough for the plugin to show actionable states.

## Key files

- `promt.md`
- `analysis/analyze.py`
- `analysis/midi/bass_transcription.py`
- `analysis/core/feature_extraction.py`
- `analysis/midi/midi_extraction.py`
- `analysis/midi/source_transcription.py`
- `analysis/midi/ace_stem_mapping.py`
- `analysis/arrangement/arrangement_lock.py`
- `analysis/arrangement/arrangement_lock_reports.py`
- `analysis/arrangement/arrangement_reports.py`
- `analysis/arrangement/arrangement_sections.py`
- `analysis/core/beat_grid.py`
- `analysis/arrangement/full_arrangement.py`
- `analysis/tests/test_feature_extraction.py`
- Planned: `analysis/segmentation.py`

## Decisions locked

- Analysis must be modular so phases can land independently.
- Start with basic but useful analysis before stems/chords/MIDI.
- Use deterministic outputs for tests and LLM prompts.
- Treat large audio files as normal input; design for progress and memory limits.
- Basic Pitch is an optional isolated engine; dependency-free analysis must still work when it is absent.
- Demucs is the first optional source-separation strategy for bass-stem MIDI; it must degrade to warnings, not job failure.
- Stems and MIDI maps are currently weak evidence paths. Improving their accuracy is planned feature work, not a solved architecture concern.
- ACE-output stem/MIDI mapping is a separate contract from reference analysis. Reference traits can guide generation, but reusable MIDI/stems must be derived from generated material.
- All-In-One structure analysis is optional and explicit opt-in via `PROMPT2MIDI_ENABLE_ALLIN1=1` or `PROMPT2MIDI_ALLIN1`. A local `.venv-allin1` can be discovered after opt-in, but if model/runtime dependencies fail, the pipeline must still emit the librosa beat-grid fallback and a warning instead of failing the job.
- Docker is only for the All-In-One-Fix/NATTEN structure analyzer path that is unreliable on macOS. The reliable default remains native local analysis plus beat/downbeat fallback; Docker is a secondary comparison lane, not a required core dependency.
- Arrangement Lock confidence scores timing/map quality. Vocal-hook or ACE/SUNO generation risk is still reported, but it must not lower the structure confidence by itself.
