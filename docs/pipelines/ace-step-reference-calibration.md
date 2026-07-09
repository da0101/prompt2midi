# ACE-Step Reference Calibration Runbook

This runbook documents the ACE-Step settings that produced reliable underground house / deep tech proxy tracks during July 2026 calibration.

The goal is not to clone released music. The goal is to create close, usable proxy demos from a reference track so the producer can finish an original track in Suno and Ableton.

For successful end-to-end ACE/Suno prompt recipes, use `docs/pipelines/successful-generation-configs.md` as the living config database.

## Required Server Mode

Start ACE-Step through the project launcher:

```bash
cd /Users/danilulmashev/Documents/GitHub/prompt2midi
npm run ace-step:start
```

The launcher defaults to:

```bash
ACESTEP_USE_MLX_DIT=0
```

This is required for calibrated reference controls.

The ACE server log should say:

```text
DiT backend: PyTorch (mps)
```

If the log says this instead, stop the server and restart it:

```text
DiT backend: MLX (native)
```

## Why MLX Is Disabled

The Apple Silicon MLX DiT backend is faster, but it did not honor `cover_noise_strength` in the same source-latent way as the PyTorch/MPS backend during calibration.

That caused wrong behavior:

- similarity knobs appeared to do little or nothing
- near-copy tests drifted into unrelated music
- some references produced bright, pop, or "Christmas-like" chord movement
- reducing strength too much made the generation incoherent

The PyTorch/MPS backend restored predictable behavior:

- high strength/noise gives near-identical diagnostic reconstruction
- medium strength/noise gives close inspired versions
- low strength/noise gives far-inspired but still coherent versions

Only use MLX deliberately for speed tests:

```bash
ACESTEP_USE_MLX_DIT=1 npm run ace-step:start
```

Do not use MLX when calibrating reference similarity.

## Diagnostic Mode

For reference-calibrated ACE proxy generation, use:

```bash
PROMPT2MIDI_ACE_STEP_RECONSTRUCTION_DIAGNOSTIC=1
PROMPT2MIDI_ACE_STEP_TASK_TYPE=cover
```

Diagnostic mode keeps the source audio as a structural anchor. It also avoids the normal prompt path that asks ACE to vary basslines and avoid copying reference material.

Do not turn diagnostic mode off when trying to make "far inspired" versions. In calibration, turning it off with very low strength/noise produced nonsense instead of usable underground house.

## Settings Ladder

Use this ladder to choose how close the ACE proxy should be.

| Intent | Reference Strength | Cover Noise Strength | Notes |
|---|---:|---:|---|
| Near diagnostic copy | `1.00` | `0.98` | Use only for calibration / cleared material checks. Too close for Suno upload in normal production. |
| Very close inspired | `0.88` | `0.74` | Still very close. Useful for checking that the reference controls work. |
| About 50% inspired | `0.50` | `0.30` | Good middle ground when the proxy should keep the production world but change musical material. |
| Far inspired, still coherent | `0.25` | `0.12` | Best discovered zone for "same mood, clearly different track" on several underground house references. |
| Further but risky | `0.18` | `0.08` | Can work when `0.25/0.12` is still too close. More reference-dependent. |
| Too far / unstable | diagnostic off + `0.10/0.03` | Avoid. Calibration produced incoherent output. |

## Timeout Rules

PyTorch/MPS is slower than MLX. A `380s` four-candidate run can exceed the default 30-minute client timeout.

For full-length four-candidate runs, set:

```bash
PROMPT2MIDI_ACE_STEP_TIMEOUT=5400
```

If a run times out but ACE generated audio, check:

```text
.cache/ace-step/ACE-Step-1.5/.cache/acestep/tmp/api_audio/
```

Recovered full-length candidates are usually `70M` WAV files with `380.000000` duration.

## Recommended Far-Inspired Full Run

```bash
cd /Users/danilulmashev/Documents/GitHub/prompt2midi

PROMPT2MIDI_ACE_STEP_TIMEOUT=5400 \
PROMPT2MIDI_ACE_STEP_RECONSTRUCTION_DIAGNOSTIC=1 \
PROMPT2MIDI_ACE_STEP_TASK_TYPE=cover \
PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH=0.25 \
PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH=0.12 \
PROMPT2MIDI_PROGRESS_ANIMATION=0 \
npm run suno:proxy-run -- \
  --reference "/path/to/reference-track.mp3" \
  --output-dir "/path/to/Candidates/TrackName-380s-far-inspired-ref025-noise012-c4-v1" \
  --similarity-level low \
  --duration 380 \
  --candidates 4 \
  --reference-start 0 \
  --prompt "create a new original underground house track. Use the reference only for broad tempo and club context. Make the bassline, chords, hook, percussion accents, transitions, and sound design clearly different. Keep it dark, restrained, hypnotic, minimal, and club-ready. No EDM, no trance, no pop, no bright festival sounds" \
  --instrumental
```

## Recommended 50% Inspired Full Run

```bash
cd /Users/danilulmashev/Documents/GitHub/prompt2midi

PROMPT2MIDI_ACE_STEP_TIMEOUT=5400 \
PROMPT2MIDI_ACE_STEP_RECONSTRUCTION_DIAGNOSTIC=1 \
PROMPT2MIDI_ACE_STEP_TASK_TYPE=cover \
PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH=0.50 \
PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH=0.30 \
PROMPT2MIDI_PROGRESS_ANIMATION=0 \
npm run suno:proxy-run -- \
  --reference "/path/to/reference-track.mp3" \
  --output-dir "/path/to/Candidates/TrackName-380s-inspired-ref050-noise030-c4-v1" \
  --similarity-level medium \
  --duration 380 \
  --candidates 4 \
  --reference-start 0 \
  --prompt "use the reference as a loose underground house inspiration for tempo, groove pocket, room feel, bass pressure, percussion attitude, dark atmosphere, and DJ-friendly structure. Write clearly original musical material with a different bassline, different chord movement, different hook, different fills, and different transitions. Keep it underground, dark, restrained, hypnotic, and club-ready" \
  --instrumental
```

## What Works

- Start ACE with PyTorch/MPS DiT, not MLX DiT.
- Keep `PROMPT2MIDI_ACE_STEP_RECONSTRUCTION_DIAGNOSTIC=1` for controlled similarity tests.
- Keep prompts simple. Let source audio carry groove, timing, room, and production identity.
- Use 120-second single-candidate tests to calibrate a reference before spending time on `380s x 4`.
- Use `380` seconds as the practical max-length target on the current Apple Silicon setup.
- Use `PROMPT2MIDI_ACE_STEP_TIMEOUT=5400` for `380s x 4`.

## What Does Not Work

- Do not use MLX DiT for similarity calibration.
- Do not assume `cover_noise_strength` behaves correctly on MLX.
- Do not remove diagnostic mode and drop strength/noise extremely low; it can create unrelated or broken music.
- Do not over-prompt with long contradictory instructions. Long prompts made some references drift into bright EDM/pop/chord nonsense.
- Do not use generic "electronic", "festival", "big energy", "trance", "supersaw", or "cinematic" wording unless explicitly requested.

## Genre Boundary

Default generation taste is:

```text
underground house, deep house, minimal house, deep tech, minimal tech house, raw house, underground techno-adjacent club music
```

Avoid:

```text
EDM, trance, dubstep, festival house, big-room, pop dance, supersaws, rave leads, cinematic builds, random arps, bright happy chord progressions
```
