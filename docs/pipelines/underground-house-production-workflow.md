# Underground House Production Workflow

This runbook is for using prompt2midi as a local-first co-producer for underground house, deep house, minimal house, deep tech, minimal tech house, and underground techno-adjacent tracks.

Do not steer the system toward EDM, trance, dubstep, festival house, big-room drops, supersaws, rave leads, cinematic builds, surprise vocals, bright plucks, or random arps unless the owner explicitly asks for that.

## Agent Brief

When starting with Codex, Claude, Gemini, or another LLM agent, paste this:

```text
Read docs/pipelines/underground-house-production-workflow.md and .platform/conventions/music-generation-style.md first.

We are making underground house / deep tech / minimal house production demos, not EDM, trance, dubstep, festival house, or pop dance.

Help me:
1. generate a long ACE proxy from a reference track,
2. prepare a strict Suno prompt and optional lyrics/voice brief,
3. organize Suno stems,
4. run the continuation arranger,
5. export a final arrangement package where arranged-stems uses Suno's original drums.wav, while percussion-reference-stems contains kick/snare/hihats/cymbals/toms guide stems for Ableton replacement.
```

## Setup

From the repo root:

```bash
npm install
npm run setup:ace-step
npm run setup:drumsep
```

Start the local ACE-Step API in a separate terminal:

```bash
npm run ace-step:start
```

For current reference-calibrated ACE settings, read `docs/pipelines/ace-step-reference-calibration.md` first. The launcher defaults ACE-Step to the PyTorch/MPS DiT backend (`ACESTEP_USE_MLX_DIT=0`) because that is the backend where the calibrated similarity controls behaved correctly.

For exact successful ACE/Suno recipes, use `docs/pipelines/successful-generation-configs.md` as the living config database.

The DrumSep setup installs `.venv-drumsep/bin/prompt2midi-drumsep`. It is optional but useful for percussion reference guides.

## Generate A Long ACE Proxy

On the current 32 GB M2 MacBook Pro calibration, the practical one-shot ACE limit is about `380` seconds, or about `6:20`. Confirmed behavior:

```text
360s works
380s works
400s usually fails with MPS out-of-memory
420s fails
full 7+ minute references fail
```

Use `360` for safer runs and `380` for max-length tests.

Recommended balanced starting command:

```bash
PROMPT2MIDI_ACE_STEP_TASK_TYPE=cover \
PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH=0.30 \
PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH=0.10 \
PROMPT2MIDI_PROGRESS_ANIMATION=0 \
npm run suno:proxy-run -- \
  --reference "/path/to/reference-track.mp3" \
  --output-dir "/path/to/Candidates/TrackName-380s-ref030-noise010-c4-v1" \
  --similarity-level low \
  --duration 380 \
  --candidates 4 \
  --reference-start 0 \
  --prompt "same tempo and same key area as the reference. Keep the underground house production world close: dry drum room, organic percussion, muted hats, rounded sub bass, warm stabs, low-pass synth texture, subtle dub delays, short plate reverb, vinyl/noise bed, dark warehouse atmosphere, rolling groove, restrained transitions, and DJ-friendly structure. Keep the bassline different but stable and in-key: new bass notes, new bass contour, different phrase development, no copied bass hook. In breakdowns and transitions use non-melodic FX only: noise sweeps, filters, reverb, delay, impacts, risers, drum fills, and atmosphere. No vocals, no trance leads, no supersaws, no festival EDM, no bright plucks, no cinematic builds, no random melodies, no off-key notes, no empty gaps." \
  --instrumental \
  --map-stems
```

For near-identical calibration only, raise reference strength. For more original basslines, lower reference strength and keep the prompt strict.

## Prepare The Suno Prompt

Upload the generated ACE proxy to Suno as inspiration, not as a request to copy the original reference.

Baseline Suno style prompt:

```text
Original underground house track from the uploaded proxy inspiration. Preserve the proxy's tempo, key area, DJ-friendly arrangement, rolling groove, deep kick, rounded sub bass, dry drum room, organic percussion, muted hats, warm stabs, low-pass synth texture, subtle dub delays, short plate reverb, vinyl noise bed, dark warehouse atmosphere. Keep the groove continuous and stripped-back, with restrained transitions and no vocals. Bass should differ from the proxy but stay stable and in-key. No female voice, no vocals, no trance leads, no supersaws, no festival EDM, no big-room drops, no bright plucks, no rave synths, no cinematic builds, no harsh highs, no random melodies.
```

Baseline Suno settings:

```text
Mode: Inspo
Model: v5.5
Weirdness: 8-12%
Style Influence: 75-85%
Audio Influence: 35-45%
Lyrics Mode: Manual
Lyrics: [Instrumental]
```

When a Suno config works, copy it into `docs/pipelines/successful-generation-configs.md` with the exact prompt and slider values.

If the result gets too EDM/trance/festival:

```text
Lower Weirdness.
Lower Audio Influence slightly.
Strengthen dry, warm, muted, warehouse, stripped-back wording.
Avoid "epic", "massive", "festival", "rave", "anthem", "big drop", and "supersaw".
```

## Ask An Agent For Suno Lyrics Or Vocal Direction

Use this prompt when the track needs vocals or a more specific Suno style brief:

```text
Create a Suno-ready style prompt under 1000 characters and lyrics under 5000 characters.

Genre boundary: underground house / deep tech / minimal house only. No EDM, trance, dubstep, festival house, big-room, pop dance, supersaws, rave leads, cinematic builds, or random arps.

Reference/proxy intent: preserve the proxy's tempo, key area, dry drum room, organic percussion, rounded low end, muted hats, dub delays, restrained FX, dark warehouse atmosphere, rolling groove, and DJ-friendly arrangement.

Vocal direction:
- Gender: [male/female/none]
- Delivery: [spoken/rap/sung/whispered/hooked phrases]
- Subject: [write subject]
- Language/accent/tone: [write details]
- Keep vocals sparse and club-usable.
- No famous artist imitation, no copied lyrics, no copied hooks.

Return:
1. Suno Styles prompt
2. Suno Lyrics field
3. Suno settings recommendation
```

## Suno Limits And Stem Export

Suno often generates about `3:00-3:30` even when the uploaded proxy is `6:20`. Treat Suno as the high-quality first-half generator, then export stems and let prompt2midi build a longer arrangement from the material.

Download Suno stems into a folder. The arranger expects WAV stems. If Suno gives MP3 files, convert them:

```bash
mkdir -p "/path/to/suno-stems-wav"
for f in "/path/to/suno-stems-mp3"/*.mp3; do
  ffmpeg -y -i "$f" "/path/to/suno-stems-wav/$(basename "${f%.mp3}").wav"
done
```

The folder should contain names the role mapper can understand, for example:

```text
drums.wav
bass.wav
synths.wav
fx.wav
vocals.wav
candidate.wav
```

Vocals are muted by default in the arranger unless `--include-vocals` is passed.

## Drum Layer Splitter

Use the drum splitter only for Ableton reference guides, not as final drum audio.

Run DrumSep directly on the Suno drum stem:

```bash
.venv-drumsep/bin/prompt2midi-drumsep \
  --input "/path/to/suno-stems-wav/drums.wav" \
  --output-dir "/path/to/percussion-reference-input"
```

Expected files:

```text
kick.wav
snare.wav
cymbals.wav
toms.wav
```

If hats/cymbals need a separate guide, use the best available split folder from listening QA. The arranger accepts `kick`, `snare`, `hihats`, `cymbals`, and `toms`. These are reference lanes for matching rhythm in Ableton, not clean final-production stems.

## Build The Long Arrangement

Core rule:

```text
arranged-stems/ keeps Suno's original drums.wav for musical continuity.
percussion-reference-stems/ contains arranged kick/snare/hihats/cymbals/toms guide stems for Ableton drum replacement.
```

Recommended generic command:

```bash
npm run arrange:continue -- \
  --input-dir "/path/to/suno-stems-wav" \
  --output-dir "/path/to/final-arrangement-package" \
  --bpm 126 \
  --target-duration 380 \
  --arrangement-mode club-second-half \
  --phrase-bars 16 \
  --transition-grid-bars 16 \
  --intro-bars 16 \
  --source-intro-bars 8 \
  --preserve-source-bars 96 \
  --pre-break-source-start-bars 80 \
  --pre-break-source-bars 16 \
  --pre-break-groove-bars 32 \
  --breakdown-source-start-bars 64 \
  --breakdown-bars 16 \
  --breakdown-drum-mode tops \
  --post-drop-groove-bars 64 \
  --second-half-extra-bars 32 \
  --post-drop-source-start-bars 32 \
  --post-drop-source-bars 64 \
  --outro-bars 16 \
  --percussion-reference-input-dir "/path/to/percussion-reference-input"
```

Tune these per track:

```text
--intro-bars: desired total DJ intro, usually 16 or 32
--source-intro-bars: intro already present in Suno source
--preserve-source-bars: accepted Suno first-half material to keep
--pre-break-groove-bars: extra developed groove before breakdown
--breakdown-bars: usually 16 or 32
--breakdown-drum-mode: tops, none, full, half-tops, or half-full
--post-drop-groove-bars: main second-half groove after breakdown
--second-half-extra-bars: adds more post-drop groove before outro
--outro-bars: usually 16 or 32
```

Breakdown drum modes:

```text
tops: remove kick/sub bass, keep top percussion feel
none: no drums
full: full drums
half-tops: first half no drums, second half tops
half-full: first half no drums, second half full drums
```

## Output Package

The arranger writes:

```text
arranged-full-mix.wav
arranged-stems/
  bass.wav
  drums.wav
  fx.wav
  synths.wav
percussion-reference-stems/
  kick.wav
  snare.wav
  hihats.wav
  cymbals.wav
  toms.wav
arrangement-map.json
arrangement-report.md
```

Use `arranged-full-mix.wav` and `arranged-stems/` for Suno/Ableton musical production. Use `percussion-reference-stems/` only to manually replace or reinforce drums in Ableton.

## QA Checklist

Before accepting a package:

```text
1. All joins happen on 8/16/32-bar boundaries.
2. The first half preserves the good Suno arrangement.
3. The breakdown is the requested bar length.
4. The drop returns with energetic groove material, not intro material.
5. The outro continues the current groove with bass removed; it does not jump to an unrelated section.
6. No tempo glitches, sudden mutes, empty gaps, or obvious copied random chunks.
7. Main arranged-stems uses Suno drums.wav.
8. percussion-reference-stems exists if drum guide stems were provided.
```

## Logging

For useful runs, add notes to `.platform/memory/generation-run-log.md`:

```text
reference track
ACE output folder
ACE settings
Suno settings
arranger command
listening result
accepted/rejected reason
```
