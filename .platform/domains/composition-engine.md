---
domain_id: dom-composition-engine
slug: composition-engine
status: active
repo_ids: [repo-primary]
related_domain_slugs: [audio-analysis, llm-midi-generation, local-orchestration, juce-plugin]
created_at: 2026-04-28
updated_at: 2026-04-28
---

# composition-engine

Owns the deterministic composition layer: takes analysis facts and evidence and produces a new, original inspired loop package (bass/drums/chords/melody/full_loop MIDI + summary.json + prompt.txt).

## Backend / source of truth

- `analysis/composition.py` — main entry `generate_inspired_loop(analysis, evidence, output_dir, bars)` → composition dict
- `analysis/midi_extraction.py` — dependency-free MIDI I/O, extended with `write_multitrack_midi()` for full_loop.mid
- `analysis/analyze.py` — calls composition engine after analysis, integrates `composition` key into Python result

## Frontend / clients

- `Source/LocalApiClient.h` — `summarizeResult()` reads `result.composition` to display generated loop package
- JUCE plugin shows: style, BPM, key, bars, all 5 MIDI paths, SUNO prompt

## API contract locked

- Python result includes a `composition` top-level key alongside `analysis`
- `composition.midi` paths are all relative to `export_dir/midi/`
- All 5 files (bass.mid, drums.mid, chords.mid, melody.mid, full_loop.mid) must exist on success
- `exports/summary.json` and `exports/prompt.txt` must exist on success

## Key files

- `analysis/composition.py`
- `analysis/midi_extraction.py`
- `analysis/analyze.py`
- `backend/lib/pythonRunner.js`
- `backend/server.js`
- `Source/LocalApiClient.h`

## Decisions locked

- Composition engine is deterministic and dependency-free (stdlib only); no ML deps in this layer
- Generated MIDI = product; extracted MIDI = evidence only; do not expose raw transcription as final output
- SUNO prompt is a stub until Phase 4 (Gemini integration)
- 32-bar loop is the default; bars parameter is configurable
- Multi-track full_loop.mid uses MIDI format type 1 (multiple MTrk chunks)
