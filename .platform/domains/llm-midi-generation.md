---
domain_id: dom-llm-midi-generation
slug: llm-midi-generation
status: active
repo_ids: [prompt2midi]
related_domain_slugs: [audio-analysis, local-orchestration, juce-plugin]
created_at: 2026-04-28
updated_at: 2026-05-06
---

# llm-midi-generation

## What this domain does

This domain covers turning structured musical analysis and user prompts into producer-facing explanations, AI-music prompts, and MIDI assets. It bridges technical analysis and creative output.

## Backend / source of truth

- MVP prompt generation is deterministic Node code that takes structured JSON from Python via Node.
- Optional Gemini SUNO prompt generation is implemented in `backend/lib/geminiPromptGenerator.js`, but the active stream remains blocked until a real `GEMINI_API_KEY` smoke test proves end-to-end prompt output.
- MIDI generation writes a simple local `reference-sketch.mid`; analysis can also attach Basic Pitch `model-transcription.mid`, Demucs-assisted `source-bass-transcription.mid`, pitch-filtered `model-bass-transcription.mid`, and experimental `bass-transcription.mid`.
- Prompting should be deterministic and based on structured inputs, not vague free text.

## Frontend / clients

- JUCE displays producer explanation and prompt output.
- UI should expose copy prompt and export MIDI actions.
- Generated text should use producer-friendly terminology.

## API contract locked

- LLM output should include:
  - human-readable producer explanation
  - genre/style breakdown
  - AI-generation prompt
- MIDI output must not be presented as transcription unless the extraction engine actually supports it.
- Current MIDI output includes `reference_sketch` plus structured `midi_assets` explaining kind, method, confidence, and limitations. Source-aware bass MIDI is allowed only when a separated stem feeds the model; full-mix model MIDI must still warn that it needs ear correction.
- Stem splitting and MIDI mapping remain weak. Text output must describe these files as editable evidence or starting points, not final tracks.
- Low-confidence BPM/key must be phrased as possible/unverified, not as firm producer facts.
- The local workflow cannot require external AI APIs.

## Key files

- `promt.md`
- `backend/lib/promptGenerator.js`
- `analysis/midi/midi_extraction.py`
- `analysis/midi/source_transcription.py`
- `analysis/midi/stem_separation.py`
- `Source/LocalApiClient.h`
- Planned: local LLM runtime integration
- Planned: source-aware melody/chord/bass extraction modules

## Decisions locked

- Structured analysis is the input to LLM prompting.
- Keep prompt output concise, specific, and reproducible.
- MIDI export is a first-class producer workflow, not an afterthought.
- Cloud LLMs can be optional later but must not be mandatory.
- Next feature work should improve stem-aware MIDI mapping before increasing claims in producer-facing prompt/output copy.
