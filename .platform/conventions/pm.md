# Product / PM Conventions

Last updated: 2026-04-28

## Source of truth

`promt.md` is the exact execution plan unless the owner changes it.

## Product framing

This is a local AI co-producer for Ableton, not a generic demo. The user value is translating reference tracks and ideas into reusable production knowledge: structure, groove, style, prompts, and MIDI.

## MVP

The first useful MVP should prove the full loop at shallow depth:

- User submits an audio file or prompt from the plugin/client.
- Local backend starts a job and reports progress.
- Python returns BPM/key/energy/loudness JSON.
- LLM layer generates a producer explanation and AI prompt from that JSON.
- UI displays results and supports copy/export where available.

## Tradeoff rules

- Prefer a working vertical slice over isolated advanced analysis.
- Do not add stem separation or melody extraction before the Phase 1 contract is stable.
- Keep local-first and Ableton workflow fit above feature breadth.
