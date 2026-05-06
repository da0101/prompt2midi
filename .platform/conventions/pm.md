# Product / PM Conventions

Last updated: 2026-05-06

## Source of truth

`promt.md` is the exact execution plan unless the owner changes it.

## Product framing

This is an open-source local AI co-producer, not a generic demo. The user value is translating reference tracks and ideas into reusable production knowledge: structure, groove, style, prompts, and MIDI.

There are two primary product lanes:

- DAW inspiration starter for producers who want editable ideas in Ableton, Logic, FL Studio, Bitwig, or another DAW.
- Pre-SUNO preparation tool for artists who want cleaner prompts, structure guides, and optional proxy packages before finishing a track in SUNO or locally.

## MVP

The first useful MVP should prove the full loop at shallow depth:

- User submits an audio file or prompt from the plugin/client.
- Local backend starts a job and reports progress.
- Python returns BPM/key/energy/loudness JSON.
- LLM layer generates a producer explanation and AI prompt from that JSON.
- UI displays results and supports copy/export where available.

## Tradeoff rules

- Prefer a working vertical slice over isolated advanced analysis.
- Stem splitting and MIDI mapping are now implemented but weak; improve their accuracy and labeling before positioning them as production-grade.
- Keep local-first and Ableton workflow fit above feature breadth.
- Keep open-source contribution paths clear, but preserve quality gates and honest confidence labels.
