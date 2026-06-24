# Music Generation Style Contract

Last updated: 2026-05-25

This project currently targets a narrow electronic music lane:

> underground house, minimal house, deep tech, minimal tech house, raw house, and related underground techno-adjacent club music.

All LLM providers working on ACE prompts, Suno prompts, generation settings, calibration notes, UI copy, or product defaults must preserve this taste boundary unless the owner explicitly asks for another genre.

## Default Target Sound

Use language that points models toward:

- underground house and minimal/deep tech-house
- dry drum room
- organic percussion
- muted hats
- rounded sub bass
- warm stabs
- low-pass synth texture
- subtle dub delays
- short plate reverb
- vinyl/noise bed
- dark warehouse atmosphere
- stripped-back but rolling groove
- DJ-friendly intro, groove development, breakdown/return, and outro
- restrained transitions
- non-melodic FX and atmosphere layered over the groove

The output should feel like an underground club record, not a festival record.

## Forbidden Default Direction

Do not steer generation toward these unless the owner explicitly requests them:

- EDM
- trance
- big room
- festival house
- dubstep
- hardstyle
- commercial pop dance
- cinematic trailer builds
- cheesy supersaws
- bright pluck leads
- rave lead synths
- random arpeggios
- vocal hooks or surprise vocals
- glossy radio-edit pop structures
- over-bright harsh highs
- glitch noise as a genre effect
- novelty instruments

Avoid words that tend to trigger those styles in text-to-music models:

- festival
- big drop
- epic
- massive
- anthem
- supersaw
- rave
- cinematic
- explosive
- powerful build
- EDM
- trance
- club-ready, if it causes festival-style outputs

## ACE Prompt Rules

ACE is used to make a local proxy/demo, not the final master. The prompt should preserve the reference-inspired structure and production world while avoiding copied compositions.

Default ACE prompt intent:

- same tempo and key area as the reference
- preserve groove pocket, drum room, percussion density, low-end pressure, ambience, and arrangement flow
- keep bassline different unless the owner asks for near-identical
- keep breaks and transitions non-melodic unless the reference clearly contains a melodic section
- no random lead melodies, random arps, vocal-like hooks, off-key notes, empty gaps, or awkward pauses

When asking for more effects, prefer:

```text
non-melodic noise sweeps, filtered sweeps, dub delays, reverb tails, short impacts, background air, percussion FX, drum fills, and atmospheric texture layered over the groove
```

Avoid asking ACE to "maximize FX" without constraints; that caused random melodies in breaks during Dikka calibration.

## Suno Prompt Rules

Suno finishing prompts should be stricter about sound palette than ACE prompts. Suno tends to turn generic "club", "risers", "impacts", "energy", and "FX" language into festival/trance/EDM timbres.

Current best Suno baseline:

```text
Original underground house track from the uploaded proxy inspiration. Preserve the proxy's tempo, key area, DJ-friendly arrangement, rolling groove, deep kick, rounded sub bass, dry drum room, organic percussion, muted hats, warm stabs, low-pass synth texture, subtle dub delays, short plate reverb, vinyl noise bed, dark warehouse atmosphere. Keep the groove continuous and stripped-back, with restrained transitions and no vocals. Bass should differ from the proxy but stay stable and in-key. No female voice, no vocals, no trance leads, no supersaws, no festival EDM, no big-room drops, no bright plucks, no rave synths, no cinematic builds, no harsh highs, no random melodies.
```

Current best Suno settings baseline:

```text
Mode: Inspo
Weirdness: 8-12%
Style Influence: 75-85%
Audio Influence: 35-45%
Lyrics Mode: Manual
Lyrics: [Instrumental]
```

If Suno sounds too festival/EDM, do not add more "club energy". Lower audio influence first and strengthen dry/warm/muted/warehouse wording.

If Suno gets too flat or loses quality, return toward the baseline above instead of adding EDM-adjacent words.

## Calibration Discipline

When calibrating, change one major axis at a time:

- ACE source conditioning: `PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH`
- ACE cover noise/source start: `PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH`
- prompt sound palette
- Suno mode/settings

Log every useful run in `.platform/memory/generation-run-log.md` with:

- reference track
- output folder
- ACE settings
- Suno settings, if used
- prompt summary
- listening notes
- whether it is a keeper, rejected, or calibration boundary

## Producer-Friendly Language

When writing UI labels or prompts for the owner, use producer/taste language:

- closer/farther from reference
- dry/warm/muted/warehouse
- rolling bass
- restrained transition
- non-melodic FX
- copied bass hook
- random break melody

Avoid backend/model language in user-facing suggestions unless explaining debugging details.
