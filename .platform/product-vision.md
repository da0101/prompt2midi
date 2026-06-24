# prompt2midi — Product Vision

Last updated: 2026-05-25

## North Star

prompt2midi should become a local-first AI co-producer that turns a reference house track into a new, original, full-length production starter:

1. Analyze the reference for tempo, key area, groove, arrangement, energy arc, sound-design character, and common house-track roles.
2. Generate one coherent full-track demo inspired by the reference, with a consistent drum kit, bass tone, percussion palette, ambience, and mix identity.
3. Split the generated demo, not the source reference, into producer-useful lanes such as drums, bass, percussion, chords, arps, hooks, atmospheres, and effects.
4. Export Ableton-ready audio stems and MIDI drafts for the same musical roles, locked to the detected beat grid, key area, and arrangement.
5. Produce a detailed Suno-ready prompt/package so the generated proxy can be finished or expanded without uploading the original reference.

## Genre And Taste Boundary

The current product target is narrow and intentional: underground house, minimal house, deep tech, minimal tech house, raw house, and underground techno-adjacent club music.

Do not steer ACE, Suno, Gemini, Claude, Codex, UI copy, or calibration defaults toward EDM, trance, big-room, dubstep, hardstyle, festival house, cinematic builds, supersaws, bright plucks, rave leads, random arps, surprise vocals, or pop/radio dance unless the owner explicitly asks for that direction.

The durable generation style contract is `.platform/conventions/music-generation-style.md`.

## Product Promise

The user should be able to choose a reference track and receive a usable production folder:

- full generated audio demo
- separated generated stems
- drum MIDI
- bass MIDI
- chord/arp/hook MIDI drafts when musically justified
- FX/atmosphere audio regions or markers when MIDI is the wrong abstraction
- arrangement map and section labels
- Suno optimized prompt and upload package

The exported assets should be honest. If a lane cannot be mapped with confidence, label it as a draft, debug artifact, or audio-only region instead of pretending it is precise MIDI.

## Near-Term Product Shape

The practical v0 is not perfect reconstruction. It is:

> Generate a coherent full-track proxy, then create editable Ableton production assets that preserve the reference-inspired tempo, key area, groove, energy shape, and house instrumentation.

Expected v0 quality:

| Asset | Target |
|---|---|
| Full generated audio | Coherent 4-6 minute track where local hardware allows |
| Drums stem/MIDI | Useful and beat-grid locked |
| Bass stem/MIDI | Useful when bass is clear or mostly monophonic |
| Chords/arps/hooks MIDI | Editable sketch with confidence labels |
| FX/atmospheres | Audio regions and arrangement markers first, MIDI only when justified |
| Suno prompt/package | Detailed, reference-aware, copyright-safe, built from generated proxy |

## Non-Goals

- Do not split or package the original reference as reusable production material.
- Do not claim mixed-audio transcription is exact when it is only an estimate.
- Do not make section-by-section generated audio the default path for coherent full-track output.
- Do not put long-running analysis or model work in the JUCE audio thread.

## Open Technical Questions

- What is the reliable local full-track duration ceiling for ACE on the target Mac hardware at each reference-strength profile?
- Which stem model gives the best house-lane separation beyond generic drums/bass/vocals/other?
- Which MIDI lanes should use transcription, which should use model-assisted rewriting, and which should remain audio-only?
- What validation gates make MIDI exports musically trustworthy enough for Ableton use?
