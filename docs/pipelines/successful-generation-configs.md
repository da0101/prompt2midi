# Successful Generation Configs

This is the living config database for prompt2midi music-generation runs that produced usable results.

Use this file to preserve exact settings, prompts, and lessons so future Codex, Claude, Gemini, or local sessions do not drift into wrong usage.

Default taste boundary:

```text
underground house, deep house, minimal house, deep tech, minimal tech house, raw house, underground techno-adjacent club music
```

Avoid by default:

```text
EDM, trance, electro house, dubstep, festival house, big-room, pop dance, supersaws, rave leads, bright plucks, cinematic builds, random arps, cheesy toplines, commercial teenage festival energy
```

## ACE Proxy Generation

### Current Required Backend

Use the launcher default:

```bash
npm run ace-step:start
```

The launcher sets:

```bash
ACESTEP_USE_MLX_DIT=0
```

Expected ACE server log:

```text
DiT backend: PyTorch (mps)
```

Do not use the MLX DiT backend for calibrated similarity runs. It was faster, but the reference/noise controls did not behave consistently enough for this workflow.

### Successful Similarity Ladder

Use these with:

```bash
PROMPT2MIDI_ACE_STEP_RECONSTRUCTION_DIAGNOSTIC=1
PROMPT2MIDI_ACE_STEP_TASK_TYPE=cover
```

| Use Case | Reference Strength | Cover Noise Strength | Result |
|---|---:|---:|---|
| Diagnostic near-copy | `1.00` | `0.98` | Near-identical reconstruction test. Do not upload to Suno for normal production. |
| Very close inspired | `0.88` | `0.74` | Very close to reference, but slightly moved away. |
| Middle inspired | `0.50` | `0.30` | Keeps vibe but changes musical material more clearly. |
| Far inspired, still coherent | `0.25` | `0.12` | Strong style/mood match, clearly different track. This has been a strong production setting. |
| Further risky | `0.18` | `0.08` | Can work, but more likely to drift or become incoherent. |

### ACE Prompt Guidance

For near-copy and close calibration, keep the prompt short. Do not over-explain.

Good short prompt:

```text
keep everything the same as the reference
```

Good inspired prompt:

```text
stay closely inspired by the reference groove, sound palette, structure, and atmosphere, but do not recreate the exact recording
```

Avoid long contradictory ACE prompts with too many production instructions. They caused some references to drift into bright pop, Christmas-like chord motion, or unrelated melodic material.

## Suno Configs

Suno prompts are different from ACE prompts.

ACE controls reference reconstruction and proxy creation. Suno needs strict taste boundaries, style language, and anti-EDM constraints.

### Config: No-Vocal Underground House From ACE Proxy

Status: successful.

Use for:

```text
instrumental underground house / deep tech / minimal house continuation from an ACE proxy
```

Suno audio mode:

```text
Inspo
```

Suno settings:

```text
Model: v5.5
Lyrics Mode: Manual
Lyrics: [Instrumental] or empty
Weirdness: 8-10%
Style Influence: 80-85%
Audio Influence: 40-50%
```

Styles prompt:

```text
Original underground house track from the uploaded proxy inspiration. Deep, adult, hypnotic club music for underground rooms, not festival EDM. Preserve the proxy's rolling groove, tight kick pocket, rounded sub pressure, dry drum room, organic percussion, muted hats, dark low-pass synth texture, restrained stabs, dub delay tails, short reverb space, vinyl/noise bed, subtle risers, background air, and DJ-friendly arrangement flow. Keep it stripped-back, warm, gritty, repetitive, functional, and club-ready. No vocals. No trance leads, no electro house sounds, no supersaws, no big-room drops, no bright plucks, no pop hooks, no cinematic builds, no cheesy melodies, no rave synths, no harsh highs, no random chord changes, no messy transitions.
```

If Suno goes too EDM:

```text
Weirdness: 5-7%
Audio Influence: 40-45%
Keep Style Influence: 80-85%
```

Add stronger anti-EDM wording:

```text
dry, muted, warm, low-pass, stripped-back, warehouse, hypnotic, restrained, no festival lead sounds
```

If Suno becomes too plain:

```text
Weirdness: 10-12%
Audio Influence: 45-50%
```

Do not add words like:

```text
epic, massive, anthem, rave, big drop, festival, explosive, cinematic, euphoric trance
```

### Config: Sparse Adult Female Vocal Underground House

Status: successful direction, use only when vocals are requested.

Suno settings:

```text
Mode: Inspo
Model: v5.5
Lyrics Mode: Manual
Weirdness: 8-12%
Style Influence: 75-85%
Audio Influence: 35-45%
```

Style prompt direction:

```text
Underground house / deep tech club track from uploaded proxy inspiration. Sparse adult female vocal, intimate and dirty, spoken/sung in short hypnotic phrases. Late-night warehouse energy, sensual, high, sweaty, euphoric, controlled. Keep vocals minimal and rhythmically locked into the groove. No pop chorus, no belting, no EDM topline, no cute commercial vocal, no trance diva voice, no festival hook.
```

Lyrics direction:

```text
Short explicit adult club phrases about being high, touch, sweat, bodies, lights, and losing time on the dance floor. Keep it repetitive, sparse, hypnotic, and usable in a DJ track. Do not write a full pop song structure.
```

## Successful Track Notes

### Teskera - It's Not Here

ACE source:

```text
/Users/danilulmashev/Desktop/Candidates/Teskera-Its-Not-Here-380s-max-close-ref096-noise036-c4-v2/exports/candidate-4.wav
```

Suno config:

```text
No-Vocal Underground House From ACE Proxy
```

Result:

```text
Worked well. Stayed pure underground house when prompted with strict no-trance / no-electro-house boundaries.
```

Keep this as the reference config for instrumental Suno tests.

### Config: No-Vocal Underground Club Tool, Minimal Harmony

Status: useful but limited.

Use when Suno keeps adding cheesy electro-house / trance / festival melodies or emotional chord progressions.

Why this worked:

```text
It frames the output as a functional underground club tool, not a song. It explicitly blocks emotional harmonic movement, catchy hooks, anthem leads, bright plucks, and festival drops.
```

Suno audio mode:

```text
Inspo
```

Suno settings:

```text
Model: v5.5
Lyrics Mode: Manual
Lyrics: [Instrumental] or empty
Weirdness: 5-8%
Style Influence: 85-90%
Audio Influence: 50-55%
```

Styles prompt:

```text
Original underground house club tool from uploaded proxy inspiration. Make it as long as Suno allows, extended DJ arrangement, not a radio edit. Keep it raw, stripped-back, repetitive, dry, dark, hypnotic, and functional for underground rooms. Preserve the proxy's kick pocket, rounded sub, muted hats, organic percussion, dry drum room, low-pass stabs, dub delays, short reverb, noise bed, sweeps, risers, impacts, filtered transitions, room air, and non-melodic FX world as closely as possible. Minimal harmonic movement: no emotional chord progressions, no uplifting changes, no pop melody, no catchy hook, no anthem lead, no trance/electro-house riffs, no bright plucks, no supersaws, no festival drop, no cinematic build, no cheesy synth melody, no rave sounds, no vocal. Bass stays deep, simple, repetitive, in-key, and club-usable.
```

Critical phrases to preserve:

```text
club tool
raw, stripped-back, repetitive
minimal harmonic movement
no emotional chord progressions
no uplifting changes
no catchy hook
non-melodic FX world
```

Do not soften these constraints. They are what keep Suno away from teenage festival / electro-house material.

Limitation:

```text
The phrase "club tool" can make Suno behave like it is generating a loop/snippet or fill-in-gap track instead of a full song with intro, breakdown, return/drop, and outro.
```

Prefer the next config for normal production.

### Config: No-Vocal Full Underground House Track, Minimal Harmony

Status: successful, preferred.

Use when the track needs to stay pure underground house, avoid cheesy festival melodies, and still have a complete DJ-friendly arrangement.

Why this worked:

```text
It keeps the anti-festival and minimal-harmony constraints from the club-tool prompt, but replaces "club tool" with "full-length underground house track" and asks for intro, rolling groove, subtle breakdown, return/drop, and outro.
```

Suno audio mode:

```text
Inspo
```

Suno settings:

```text
Model: v5.5
Lyrics Mode: Manual
Lyrics: [Instrumental] or empty
Weirdness: 6-9%
Style Influence: 85-90%
Audio Influence: 45-55%
```

Styles prompt:

```text
Original full-length underground house track from uploaded proxy inspiration. Make it as long as Suno allows with a complete DJ-friendly arrangement: intro, rolling groove, subtle breakdown, return/drop, and outro. Keep it raw, stripped-back, repetitive, dry, dark, hypnotic, and functional for underground rooms, not a short loop or snippet. Preserve the proxy's kick pocket, rounded sub, muted hats, organic percussion, dry drum room, low-pass stabs, dub delays, short reverb, noise bed, sweeps, risers, impacts, filtered transitions, room air, and non-melodic FX world as closely as possible. Minimal harmonic movement: no emotional chord progressions, no uplifting changes, no pop melody, no catchy hook, no anthem lead, no trance/electro-house riffs, no bright plucks, no supersaws, no festival drop, no cinematic build, no cheesy synth melody, no rave sounds, no vocal. Bass stays deep, simple, repetitive, in-key, and club-usable.
```

Critical phrases to preserve:

```text
full-length underground house track
complete DJ-friendly arrangement
intro, rolling groove, subtle breakdown, return/drop, and outro
not a short loop or snippet
minimal harmonic movement
no emotional chord progressions
non-melodic FX world
```

### Per Hammar / Dikka Packages

Status:

```text
Proof-of-concept workflow passed: ACE proxy -> Suno -> arrangement package -> Ableton -> Suno follow-up.
```

Important packaging rule:

```text
Use Suno's original drums stem in the main arranged-stems folder. Put split kick/snare/hihats/cymbals/toms only in percussion-reference-stems for Ableton replacement guides.
```

## New Config Entry Template

Copy this block when a run works:

```text
### Track / Run Name

Date:
Source reference:
ACE output:
Suno input/proxy:

ACE settings:
- backend:
- reconstruction diagnostic:
- task type:
- reference strength:
- cover noise strength:
- duration:
- candidates:
- prompt:

Suno settings:
- mode:
- model:
- weirdness:
- style influence:
- audio influence:
- lyrics mode:
- lyrics:

Suno Styles prompt:

Result:

What worked:

What failed / avoid next time:
```
