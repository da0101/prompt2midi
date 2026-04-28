---
domain_id: dom-llm-midi-generation
slug: llm-midi-generation
status: active
repo_ids: [prompt2midi]
related_domain_slugs: [audio-analysis, local-orchestration, juce-plugin]
created_at: 2026-04-28
updated_at: 2026-04-28
---

# llm-midi-generation

## What this domain does

This domain covers turning structured musical analysis and user prompts into producer-facing explanations, AI-music prompts, and MIDI assets. It bridges technical analysis and creative output.

## Backend / source of truth

- Local LLM layer takes structured JSON from Python via Node.
- It returns producer insights, genre/style breakdowns, and AI-generation prompts.
- MIDI extraction/generation should produce local `.mid` paths consumable in Ableton.
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
- MIDI output should include named asset paths such as bass, melody, or chords when available.
- The local workflow cannot require external AI APIs.

## Key files

- `promt.md`
- Planned: LLM prompt templates/service
- Planned: MIDI export module
- Planned: result schema shared with JUCE

## Decisions locked

- Structured analysis is the input to LLM prompting.
- Keep prompt output concise, specific, and reproducible.
- MIDI export is a first-class producer workflow, not an afterthought.
- Cloud LLMs can be optional later but must not be mandatory.
