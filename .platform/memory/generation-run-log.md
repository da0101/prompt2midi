# Generation Run Log

Purpose: track reproducible generation configs, output folders, pass/fail results, and listening notes. Use this when comparing reference strength, duration limits, near-identical settings, and later stem/MIDI extraction quality.

Newest entries should be added at the top of the table.

## Arrangement Maker Tests

| Date | Output | Source | BPM | Result | Notes |
|---|---|---|---:|---|---|
| 2026-05-28 | `/Users/danilulmashev/Documents/GitHub/prompt2midi/tmp/per-hammar-candidate-3-firsthalf-lock-v7` | Suno `candidate-3` stems from Per Hammar test | 128 | technical check: explicit breakdown drum mode | Same musical structure as v6, rendered to verify generic arrangement controls. The report now exposes `Breakdown drums: tops`. Supported generic modes are `tops`, `none`, `full`, `half-tops`, and `half-full`, so future tracks can request breakdowns like `16 bars + no drums`, `16 bars + full drums`, or `16 bars + first half no drums / second half drums` without hardcoding a track-specific rule. |
| 2026-05-28 | `/Users/danilulmashev/Documents/GitHub/prompt2midi/tmp/per-hammar-candidate-3-firsthalf-lock-v6` | Suno `candidate-3` stems from Per Hammar test | 128 | needs listening: corrected groove-minus-bass outro | Same as v5 through the post-drop groove, but fixes the outro rule: do not switch to intro sounds. The 16-bar DJ outro now reuses the tail of the post-drop groove source (`80-96`) with bass/vocals muted. This follows the house rule: keep the current groove material, remove bass, keep drums/tops/FX for DJ mixing. |
| 2026-05-28 | `/Users/danilulmashev/Documents/GitHub/prompt2midi/tmp/per-hammar-candidate-3-firsthalf-lock-v5` | Suno `candidate-3` stems from Per Hammar test | 128 | needs listening: FFT/bar-locked second-half trial | First second-half attempt after the accepted v4 baseline. Uses `club-second-half` mode with a 16-bar transition grid: accepted 16-bar intro + first half + 32-bar pre-break + 16-bar breakdown, then one contiguous FFT/RMS-selected 48-bar post-drop source window from source bars `48-96`, then a 16-bar intro-derived DJ outro. Total is bar-locked at 200 bars / 375s, avoiding arbitrary partial-bar chopping. Do not mark accepted until Ableton listening confirms the post-drop and outro work. |
| 2026-05-28 | `/Users/danilulmashev/Documents/GitHub/prompt2midi/tmp/per-hammar-candidate-3-firsthalf-lock-v4` | Suno `candidate-3` stems from Per Hammar test | 128 | SUCCESS: accepted intro + first half + breakdown | User-approved baseline. Correct reusable rule: desired arrangement lengths are explicit inputs, not hardcoded. This run uses `--intro-bars 16 --source-intro-bars 8`, so the arranger prepends only the missing 8 bars, preserves Suno source bars `0-80`, repeats source bars `80-96` exactly twice for a 32-bar pre-break continuation, then starts a 16-bar stripped breakdown with `--breakdown-bars 16` from source bars `64-80`. This is the locked baseline before second-half/drop/outro work. `--outro-bars 16` is now also available for the second-half modes. Future runs should expose intro, pre-break, breakdown, drop, and outro bar counts as parameters such as 16/32 bars depending on the track. Drum bus was split with MDX23C DrumSep into `drum-substems/kick.wav`, `snare.wav`, `hihats.wav`, `toms.wav`, and `cymbals.wav`. |
| 2026-05-28 | `/Users/danilulmashev/Documents/GitHub/prompt2midi/tmp/per-hammar-candidate-3-firsthalf-lock-v2` | Suno `candidate-3` stems from Per Hammar test | 128 | replaced by v4 | Close baseline, but missing the extra 8 bars needed to make the intro 16 bars total. Replaced by v4, which keeps this same musical arrangement but computes missing intro bars from `intro_bars - source_intro_bars`. |
| 2026-05-28 | `/Users/danilulmashev/Documents/GitHub/prompt2midi/tmp/per-hammar-candidate-3-firsthalf-lock-v1` | Suno `candidate-3` stems from Per Hammar test | 128 | rejected intro math | The pre-break and breakdown math was close, but it prepended an extra intro before preserving source bars `0-80`, creating an overlong/duplicated intro. Do not use this pattern. |

## How To Record A Run

For every meaningful run, capture:

- Reference file
- Output folder
- Duration / reference start
- Similarity level
- `PROMPT2MIDI_ACE_STEP_TASK_TYPE`
- `PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH`
- `PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH`
- `PROMPT2MIDI_ACE_STEP_RECONSTRUCTION_DIAGNOSTIC`
- Candidates
- Prompt summary
- Result: success, fail, OOM, packaging error, or listening accepted/rejected
- Notes about sound quality and how close/original it felt

## Dikka Boundary And Similarity Tests

Reference unless noted: `/Users/danilulmashev/Downloads/DIKKA - Same Time (Original Mix).mp3`

| Date | Output | Duration | Start | Level | Ref strength | Audio start | Diagnostic | Candidates | Result | Notes |
|---|---|---:|---:|---|---:|---:|---|---:|---|---|
| 2026-05-24 | `/Users/danilulmashev/Desktop/Candidates/Dikka-keyshift-test-ref070-start015` | 60s | 60s | high | 0.70 | 0.15 | off | 1 | success | First perceived successful key-shift variation. User reported the key shifted and the result was a cool usable variation. Analyzer could not confirm key because both candidate and reference-section returned `Unknown` key on the 60s drum/low-end-heavy window. Candidate manifest: target similarity 0.52, reference similarity score 0.59, passed quality gate. Use this as the full-length key-shift starting point. |
| 2026-05-24 | `/Users/danilulmashev/Desktop/Candidates/Dikka-380s-near-identical-ref090-start090-v1` | 380s | 0s | near-identical | 0.90 | 0.90 | on | 1 | success | Closest diagnostic reconstruction baseline. User reported it worked. Use as max-closeness anchor before backing off toward originality. |
| 2026-05-24 | `/Users/danilulmashev/Desktop/Candidates/Dikka-380s-ref090-v1` | 380s | 0s | near-identical | 0.90 | 0.20 | off | 1 | success | Strong reference-guided 6:20 render. User reported it worked and sounded very good. |
| 2026-05-24 | `/Users/danilulmashev/Desktop/Candidates/Dikka-380s-v1` | 380s | 0s | near-identical | 0.42 | 0.20 | off | 1 | success | Longest confirmed stable-ish one-shot at normal near-identical controls. |
| 2026-05-24 | `/Users/danilulmashev/Desktop/Candidates/Dikka-400s-v1` | 400s | 0s | near-identical | 0.42 | 0.20 | off | 1 | failed OOM | Failed in PyTorch MPS `scaled_dot_product_attention`; attempted extra 1.49 GiB allocation. Not an exact 400s breakpoint, but over local safe duration. |
| 2026-05-24 | `/Users/danilulmashev/Desktop/Candidates/Dikka-420s-v1` | 420s | 0s | near-identical | 0.42 | 0.20 | off | 1 | failed OOM | Failed in PyTorch MPS attention; attempted extra 1.64 GiB allocation. Confirms ceiling below 420s. |
| 2026-05-24 | `/Users/danilulmashev/Desktop/Candidates/Dikka-full-746-v1` | full / 466s | 0s | near-identical | 0.42 | 0.20 | off | 1 | failed OOM | Full one-shot source length fails on local MPS. |
| 2026-05-24 | `/Users/danilulmashev/Desktop/Candidates/Dikka-360s-v1` | 360s | 0s | near-identical | 0.42 | 0.20 | off | 1 | success | Six-minute one-shot succeeded. Good product-safe target. |
| 2026-05-24 | `/Users/danilulmashev/Desktop/Candidates/Dikka-300s-v1` | 300s | 0s | near-identical | 0.42 | 0.20 | off | 1 | success | Five-minute one-shot succeeded quickly. |
| 2026-05-24 | `/Users/danilulmashev/Desktop/Candidates/Dikka-240s-v1` | 240s | 0s | medium | 0.18 effective | 0.08 effective | off | 1 | success | Inspired/original 4-minute baseline. Candidate passed quality gate. Packaging was later fixed to allow 240s proxy upload. |
| 2026-05-24 | `/Users/danilulmashev/Desktop/Candidates/Dikka-746-oneshot-v1` | full / 466s | 0s | medium | 0.18 | 0.08 | off | 1 | failed OOM | Experimental full source one-shot with loose controls still failed on local MPS at 466s. |
| 2026-05-24 | `/Users/danilulmashev/Desktop/Candidates/Dikka-746-oneshot-v2` | full / 466s | 0s | medium | 0.18 | 0.08 | off | 1 | failed OOM | Retry after cleanup/restart still failed at full source duration. |

## Reproducible Known Commands

### Dikka 240s Inspired Baseline

This generated `/Users/danilulmashev/Desktop/Candidates/Dikka-240s-v1/exports/candidate-1.wav`.

```bash
PROMPT2MIDI_ACE_STEP_TASK_TYPE=cover \
PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH=0.18 \
PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH=0.08 \
PROMPT2MIDI_PROGRESS_ANIMATION=0 \
npm run suno:proxy-run -- \
  --reference "/Users/danilulmashev/Downloads/DIKKA - Same Time (Original Mix).mp3" \
  --output-dir "/Users/danilulmashev/Desktop/Candidates/Dikka-240s-v1" \
  --similarity-level medium \
  --duration 240 \
  --candidates 1 \
  --reference-start 0 \
  --prompt "same tempo, key area, groove pocket, club energy, and arrangement flow as the reference. Generate one coherent 4-minute underground house track with consistent drum kit, bass tone, percussion palette, ambience, and mix identity." \
  --instrumental
```

Saved manifest reported effective controls:

```text
task_type=cover
reference_guidance=0.18
audio_start_amount=0.08
requested_similarity=0.37
effective_similarity=0.40
seed=-1
model=acestep-v15-turbo
```

### Dikka 380s Diagnostic Near-Identical Baseline

Use this only as the max-closeness calibration anchor.

```bash
PROMPT2MIDI_ACE_STEP_TASK_TYPE=cover \
PROMPT2MIDI_ACE_STEP_RECONSTRUCTION_DIAGNOSTIC=1 \
PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH=0.90 \
PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH=0.90 \
PROMPT2MIDI_PROGRESS_ANIMATION=0 \
npm run suno:proxy-run -- \
  --reference "/Users/danilulmashev/Downloads/DIKKA - Same Time (Original Mix).mp3" \
  --output-dir "/Users/danilulmashev/Desktop/Candidates/Dikka-380s-near-identical-ref090-start090-v1" \
  --similarity-level near-identical \
  --duration 380 \
  --candidates 1 \
  --reference-start 0 \
  --prompt "same tempo and key area as the reference." \
  --instrumental
```

### Dikka Key-Shift Variation Baseline

This 60s test is the first user-confirmed setting that audibly shifted the key while keeping the Dikka ambience/groove world.

```bash
PROMPT2MIDI_ACE_STEP_TASK_TYPE=cover \
PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH=0.70 \
PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH=0.15 \
PROMPT2MIDI_PROGRESS_ANIMATION=0 \
npm run suno:proxy-run -- \
  --reference "/Users/danilulmashev/Downloads/DIKKA - Same Time (Original Mix).mp3" \
  --output-dir "/Users/danilulmashev/Desktop/Candidates/Dikka-keyshift-test-ref070-start015" \
  --similarity-level high \
  --duration 60 \
  --candidates 1 \
  --reference-start 60 \
  --prompt "keep the same underground house ambience, drum room, bass pressure, percussion texture, tempo, groove pocket, and mix identity, but transpose all musical material up exactly 2 semitones from G# minor to A# minor. Bassline must use A# minor notes, not G# minor roots. Chords and stabs must be in A# minor. Do not keep the original bass notes or chord roots." \
  --instrumental
```

Full-length follow-up should keep the same controls and prompt intent, then set `--duration 380` and a full-run output folder.

### Dikka 380s Key-Shift Follow-Up v1

First attempt to scale the successful 60s key-shift setting to a 380s render.

```bash
PROMPT2MIDI_ACE_STEP_TASK_TYPE=cover \
PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH=0.70 \
PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH=0.15 \
PROMPT2MIDI_PROGRESS_ANIMATION=0 \
npm run suno:proxy-run -- \
  --reference "/Users/danilulmashev/Downloads/DIKKA - Same Time (Original Mix).mp3" \
  --output-dir "/Users/danilulmashev/Desktop/Candidates/Dikka-380s-keyshift-ref070-start015-v1" \
  --similarity-level high \
  --duration 380 \
  --candidates 1 \
  --reference-start 0 \
  --prompt "keep the same underground house ambience, drum room, bass pressure, percussion texture, tempo, groove pocket, and mix identity, but transpose all musical material up exactly 2 semitones from G# minor to A# minor. Bassline must use A# minor notes, not G# minor roots. Chords and stabs must be in A# minor. Do not keep the original bass notes or chord roots." \
  --instrumental
```

Listening note: user reported it did not reproduce the useful rhythm/bassline behavior from the 60s key-shift version. Likely cause: the 60s baseline used `--reference-start 60`, while this 380s run starts at `0` and asks ACE to follow a much longer arrangement. Treat this as a failed musical match, not a failed key-shift proof.

### Dikka 60s Key-Shift Lower-Source Calibration

Attempted to reduce source lock so the target key instruction could win.

```bash
PROMPT2MIDI_ACE_STEP_TASK_TYPE=cover \
PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH=0.45 \
PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH=0.08 \
PROMPT2MIDI_PROGRESS_ANIMATION=0 \
npm run suno:proxy-run -- \
  --reference "/Users/danilulmashev/Downloads/DIKKA - Same Time (Original Mix).mp3" \
  --output-dir "/Users/danilulmashev/Desktop/Candidates/Dikka-keyshift-test-ref045-start008-v1" \
  --similarity-level medium \
  --duration 60 \
  --candidates 1 \
  --reference-start 60 \
  --prompt "target key is A# minor. Keep the same underground house ambience, drum room, bass pressure, percussion texture, tempo, groove pocket, rhythm feel, bass movement style, and mix identity. Transpose the musical material into A# minor. Bassline, chords, stabs, hooks, fills, and risers must be tuned inside A# minor. Do not keep the original key center, original bass notes, or original chord roots." \
  --instrumental
```

Listening note: user reported it generated an interesting new bassline, but did not shift the entire track into a new key and did not preserve the original reference effects. Follow-up fix: the ACE metadata key was still derived from the detected reference key; target-key prompts now also override `key_scale`/`keyscale`.

## Current Empirical Limits

For Dikka on the current 32GB M2 MacBook Pro with ACE-Step turbo/MPS:

```text
300s: works
360s: works
380s: works
400s: fails with MPS OOM
420s: fails with MPS OOM
466s/full: fails with MPS OOM
```

Product default recommendation:

```text
360s = stable long one-shot
380s = experimental long one-shot
full source length > 380s = use Smart Reference Window / Club Edit Fit instead of raw full one-shot
```

## Calibration Finding: 60s vs 380s Layer Variation

Repeated Dikka layer-control tests show that the same apparent config does not behave the same across duration:

```text
60s source-conditioned runs: more likely to create a unique/new bassline while keeping some reference world.
380s source-conditioned runs: much more likely to sound too close to the original, even with the same reference_strength/noise prompt intent.
```

Interpretation: long cover-source conditioning gives ACE much more original bass/motif evidence, so the model re-locks to the reference over time. Layer similarity controls must be duration-normalized; `reference_strength=0.58` at 60s is not equivalent to `reference_strength=0.58` at 380s.

Product implication: full-track variation needs a dedicated long-form mode, not the same settings as short calibration. Candidate approaches:

```text
1. Duration-compensated source strength for long one-shot renders.
2. Smart reference windows instead of feeding the entire 380s source with the same strength.
3. Section/layer control scaffolds for bass/chords/hooks while preserving drums/FX/arrangement.
4. Post-generation layer scoring to reject outputs that are too close or have copied bass motifs.
```

### Dikka Short-Source / Long-Output Experiment

Added pipeline support for separating generated output duration from ACE source-conditioning window duration:

```text
--duration controls generated candidate length.
--reference-conditioning-duration controls the source section length sent to ACE.
```

First test shape:

```bash
PROMPT2MIDI_ACE_STEP_TASK_TYPE=cover \
PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH=0.34 \
PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH=0.10 \
PROMPT2MIDI_PROGRESS_ANIMATION=0 \
npm run suno:proxy-run -- \
  --reference "/Users/danilulmashev/Downloads/DIKKA - Same Time (Original Mix).mp3" \
  --output-dir "/Users/danilulmashev/Desktop/Candidates/Dikka-280s-short-source120-ref034-noise010-stems-v1" \
  --similarity-level medium-low \
  --duration 280 \
  --reference-conditioning-duration 120 \
  --reference-strategy stable_energy \
  --candidates 1 \
  --prompt "same tempo and same key area as the reference. Use the selected source window for underground house sonic palette, drum kit attitude, kick pocket, percussion density, groove pressure, effects style, risers, noise sweeps, delays, reverb space, chord/stab sound design, synth texture, low-end weight, and club mix pressure. Generate a complete 280-second DJ-friendly track with intro, groove development, breakdown/build energy, return, and outro. Make the bassline clearly different from the reference: new bass notes, new bass contour, new low-end hook movement, and different motif development. Also create a new chord/stab progression and new hook movement. Do not copy the original bass melody, chord roots, synth riff, hook, or exact arrangement gestures. Same sonic palette and producer vibe, different track." \
  --instrumental \
  --map-stems
```

Goal: keep a long Suno-ready proxy output while reducing copied long-form bass/motif evidence by conditioning ACE on a smart 120s source window.

### Dikka 380s Bass/FX Balance

Latest midpoint calibration:

```text
reference_strength=0.26
cover_noise_strength=0.08
duration=380
similarity-level=low
```

Listening note: user reported the bassline moved closer in a useful way, but the generated track did not preserve enough of the reference effects/ambience world. Next calibration should keep bass variation intent, but strengthen reference-like FX/ambience via prompt wording and a small source-conditioning increase rather than jumping back to high conditioning.

Follow-up balanced calibration:

```text
reference_strength=0.30
cover_noise_strength=0.10
duration=380
similarity-level=low
prompt intent=close drums/FX/ambience, different bassline/motif
```

Listening note: user liked this version overall and reported that the bassline is very good. Remaining gap: the output needs more of the reference track's sound effects, sound design, ambience, and atmospheric effects. Next test should preserve bass settings and increase FX/ambience emphasis first through prompt wording; if that is not enough, try only a small source-conditioning bump.

FX-focused follow-up:

```text
reference_strength=0.30
cover_noise_strength=0.12
duration=380
similarity-level=low
prompt intent=preserve bass variation, add stronger reference-like FX/atmosphere
```

Listening note: rejected. User reported weird silences/breaks and no clear improvement in reference-like effects. Bass remained different, which is good. Next test should avoid increasing `cover_noise_strength` in this direction and should explicitly request continuous club flow/no dropouts. Use four candidates per config to judge the setting rather than a single seed.

Four-candidate balanced FX push:

```text
reference_strength=0.34
cover_noise_strength=0.10
duration=380
candidates=4
similarity-level=low
prompt intent=continuous club flow, no dropouts, bass variation, closer FX/ambience
```

Listening note: user reported this is much better structurally: no empty spaces and no weird breaks. Bass is still not identical, which is desired. Effects feel slightly closer to the reference. Next test can push a little more reference-like FX by raising reference strength only while keeping noise at `0.10` and preserving the no-dropout language.

Max-FX push feedback:

```text
reference_strength=0.38-0.42
cover_noise_strength=0.10
duration=380
candidates=4
prompt intent=maximize FX/ambience while keeping bass different
```

Listening note: user reported weird random melodies in breaks that are not part of the reference. Interpretation: stronger FX/ambience language can cause ACE/Suno-proxy-style melodic invention during breakdown sections. Next prompt should explicitly request non-melodic FX/atmosphere only in breaks and prohibit new lead melodies, vocal-like hooks, arps, and random melodic fills.

### Suno Proxy Test Feedback

Suno test used uploaded generated proxy candidate with approximately:

```text
Suno v5.5
Remix/Cover audio mode
Weirdness=20%
Style Influence=50%
Audio Influence=65%
Prompt length=900/1000 chars
```

Listening note: output quality was excellent, but sound selection skewed too EDM/trance/festival: loud sharp sounds and less underground house restraint. Next Suno prompt should explicitly ask for deep/underground/minimal tech-house timbres, warm/dark/rounded sound design, restrained FX, muted highs, no supersaws/trance leads/festival risers/bright plucks. Consider lowering Audio Influence slightly if the proxy itself contains sharp EDM-like timbres.

Follow-up Suno prompt/settings finding:

```text
Mode tested around Inspo/Remix audio workflows
Prompt moved away from festival language toward underground house/minimal tech-house
Key wording: dry drum room, organic percussion, muted hats, warm stabs, low-pass synth texture, subtle dub delays, short plate reverb, vinyl/noise bed, dark warehouse atmosphere, no vocals
```

Listening note: user reported this generated a very good Suno version. Difference from worse tests: less "club-ready/risers/impacts/energy" language, more dry/warm/muted/warehouse/stripped-back timbre constraints, lower audio-following style, and explicit no-vocals/no-festival-EDM constraints.

Current best Suno finishing recipe:

```text
Mode: Inspo
Weirdness: 8-12%
Style Influence: 75-85%
Audio Influence: 35-45%
```

Prompt:

```text
Original underground house track from the uploaded proxy inspiration. 126 BPM, G# minor, DJ-friendly arrangement, rolling groove, deep kick, rounded sub bass, dry drum room, organic percussion, muted hats, warm stabs, low-pass synth texture, subtle dub delays, short plate reverb, vinyl noise bed, dark warehouse atmosphere. Keep the groove continuous and stripped-back, with restrained transitions and no vocals. Bass should differ from the proxy but stay stable and in-key. No female voice, no vocals, no trance leads, no supersaws, no festival EDM, no big-room drops, no bright plucks, no rave synths, no cinematic builds, no harsh highs, no random melodies.
```

Status: best Suno finishing baseline so far. It avoids the festival/trance sound-palette problem better than higher audio-influence Remix/Cover prompts.

### Durable Style Rule

The project now has a durable music generation style contract at:

```text
.platform/conventions/music-generation-style.md
```

All future ACE/Suno/Gemini/Claude/Codex prompt work should stay in underground house, minimal house, deep tech, minimal tech-house, raw house, and underground techno-adjacent lanes by default. Avoid EDM, trance, big-room, dubstep, hardstyle, festival house, cinematic builds, supersaws, bright plucks, rave leads, random arps, surprise vocals, and pop/radio dance unless explicitly requested by the owner.

### Arrangement Maker Calibration

Accepted first-half baseline:

```text
tmp/per-hammar-candidate-3-firsthalf-lock-v4
```

Listening note: user marked this as successful for intro + first half + breakdown. The useful rule is not track-specific: obey house bar math first. Intro, breakdown, outro, and transition placement must land on 8/16/32-bar boundaries, with 16-bar transitions as the default for this style. For this track, the fix was to preserve the good Suno first-half arrangement, add only the missing intro bars, repeat the correct developed pre-break phrase to complete the phrase math, then enter the breakdown.

Current configurable arrangement controls:

```text
intro_bars
source_intro_bars
breakdown_bars
breakdown_drum_mode = tops | none | full | half-tops | half-full
outro_bars
transition_grid_bars
pre_break_groove_bars
post_drop_groove_bars
```

Percussion-stem export fix:

```text
tmp/per-hammar-candidate-3-firsthalf-lock-v8-percussion-stems
```

Technical note: v8 uses prepared independent percussion stems (`kick`, `snare`, `hihats`, `toms`, `cymbals`) plus `bass`, `synths`, and `fx`. Fixed stem role inference so a parent folder named `percussion` no longer causes `bass.wav`, `fx.wav`, or `synth.wav` to be misclassified as percussion. Export now writes all arranged percussion stems under `arranged-stems/` alongside the full mix.

Dikka candidate-4 same-format test:

```text
tmp/dikka-candidate-4-firsthalf-lock-v1-percussion-stems
```

Inputs:

```text
Suno stems: /Users/danilulmashev/Downloads/candidate-4
ACE: /Users/danilulmashev/Desktop/Candidates/Dikka-380s-fx-boundary-ref072-noise010-c4-v1/exports/candidate-4.wav
Reference: /Users/danilulmashev/Desktop/Candidates/Dikka-380s-fx-boundary-ref072-noise010-c4-v1/exports/reference-section.wav
```

Render settings: 126 BPM, 200 bars / 380.954s, 16-bar intro target with 8 bars prepended, preserve first 80 source bars, 32-bar pre-break developed groove, 16-bar breakdown with tops, 48-bar FFT/RMS-selected post-drop groove, 16-bar bass-muted outro. Drum stem was split with the same MDX23C DrumSep audio-separator model used for the best previous candidate-3 drum split. Output includes `arranged-stems/kick.wav`, `snare.wav`, `hihats.wav`, `toms.wav`, `cymbals.wav`, `bass.wav`, `synths.wav`, and `fx.wav`, plus `source-audio/` with Suno, ACE, and reference WAVs for Ableton comparison.

Reference-blueprint Dikka candidate-4 test:

```text
tmp/dikka-candidate-4-reference-blueprint-v7
```

Why this exists: the previous Dikka same-format render reused the fixed Per-Hammar club-second-half template, so the structure was too similar across tracks and did not follow the Dikka reference. v7 uses `arrangement_mode=reference-blueprint`, analyzes `reference-section.wav` on an FFT/RMS bar grid, and applies the reference's full-groove/breakdown/outro states to the Suno stems. This is the preferred direction: the original/reference controls arrangement energy and bass-removal logic; Suno stems provide the audio material.

Important generic rule captured from user feedback: never randomly chop/insert arbitrary fragments. Preserve or copy material on 8/16/32-bar boundaries only. If a generated Suno intro contains a bad leading block, skip it with `preserve_source_start_bars` instead of baking it into the arrangement. Outro should normally reuse the last groove material with bass muted, not switch back to intro sounds and not mute the kick by default.

v7 render settings:

```text
arrangement_mode=reference-blueprint
bpm=126
target_duration=380 -> snapped to 200 bars / 380.954s
intro_bars=16
source_intro_bars=0
preserve_source_start_bars=8
preserve_source_bars=80
transition_grid_bars=16
breakdown_drum_mode=tops
outro_bars=16
```

Resulting appended sections after intro + preserved Suno body:

```text
reference_full_groove: 16 bars, source 64-80, mute vocals
stripped_breakdown: 16 bars, source 48-64, mute bass/vocals
reference_full_groove: 40 bars, source 32-72, mute vocals
stripped_breakdown: 8 bars, source 48-56, mute bass/vocals
reference_full_groove: 8 bars, source 64-72, mute vocals
dj_outro: 16 bars, source 64-80, mute bass/vocals
```

Status: ready for Ableton audition. This is a structural attempt, not final proof. The next user feedback should focus on whether the reference-driven breakdown/drop/outro placement is closer than the fixed-template Dikka render.

User rejected the Dikka `reference-blueprint` direction after Ableton review: it overfit the reference energy map and made sloppy bass-mute/intro decisions inside Suno material that was already arranged well. Reverted direction is Suno-priority: preserve the generated Suno body as the primary arrangement, then use deterministic 8/16/32-bar controls to add/extend intro, breakdown, post-drop second half, and outro.

New reusable arranger control:

```text
second_half_extra_bars
```

This is additive on top of `post_drop_groove_bars` in `club-second-half` mode. Example: `post_drop_groove_bars=48` plus `second_half_extra_bars=32` renders an 80-bar post-drop/second-half groove, while intro, breakdown, and outro remain separately controlled.

Dikka Suno-priority long second-half test:

```text
tmp/dikka-candidate-4-suno-priority-longsecondhalf-v1
```

Render settings: 126 BPM, `arrangement_mode=club-second-half`, preserve first 80 Suno source bars, no prepended intro (`intro_bars=16`, `source_intro_bars=16`), 32-bar breakdown with top percussion, 48-bar base post-drop groove, `second_half_extra_bars=32`, 16-bar bass-muted DJ outro. Effective output is 208 bars / 396.192s because the user specifically asked that the second half can be made longer by parameter, for example +32 bars.

User feedback on `tmp/dikka-candidate-4-suno-priority-longsecondhalf-v1`: musically closer, but it still removed too much accepted Suno arrangement before the breakdown. The mistake was preserving only 80 source bars. For this Dikka Suno file, the better rule is to preserve the full complete 96-bar Suno body and cut only the odd/non-musical tail before the breakdown.

Corrected Dikka Suno-priority preserve-96 render:

```text
tmp/dikka-candidate-4-suno-priority-preserve96-v2
```

Render settings: 126 BPM, `arrangement_mode=club-second-half`, preserve source bars `0-96` (0.0s-182.858s), no prepended intro (`intro_bars=16`, `source_intro_bars=16`), 32-bar breakdown with tops, 32-bar base post-drop groove plus `second_half_extra_bars=32` for 64 effective post-drop bars, 16-bar bass-muted outro. Effective output remains 208 bars / 396.192s, but the extra time now comes from keeping Suno's real development instead of replacing it with copied continuation material.

User feedback on preserve-96 v2: the direction is good, and the process should be simplified. Intro/outro can be handled later in Suno; for the arranger, prioritize keeping Suno's body and making the second half longer when requested. The v2 outro arrived too quickly, so render a longer second-half test by adding 32 more bars before the outro.

Longer second-half Dikka render:

```text
tmp/dikka-candidate-4-suno-priority-preserve96-extra32-v3
```

Render settings: same preserved Suno source bars `0-96`, same 32-bar breakdown, same 16-bar outro, but `second_half_extra_bars=64` instead of `32`. Effective post-drop section is now 96 bars, so the outro starts at bar 224 instead of bar 192. Total output is 240 bars / 457.145s.

User rejected `tmp/dikka-candidate-4-suno-priority-preserve96-extra32-v3`: it violated the core rule by restarting the post-break groove from source bar 0. The cause was technical: a 96-bar rendered post-drop requested a 96-bar source window, and the only possible contiguous 96-bar source window was the whole song (`0-96`), including the intro.

Fix added to arranger: `post_drop_source_bars` is now separate from rendered `post_drop_groove_bars + second_half_extra_bars`. This allows rendering a long second half while forcing the source window to the developed/energetic part only.

Corrected developed-postdrop render:

```text
tmp/dikka-candidate-4-suno-priority-developed-postdrop-extra32-v4
```

Render settings: preserve Suno bars `0-96`, 32-bar breakdown, render 96 post-drop bars, but source the post-drop from developed bars `32-96` only (`post_drop_source_start_bars=32`, `post_drop_source_bars=64`). This repeats developed/energetic material after the breakdown instead of restarting from the intro. Total remains 240 bars / 457.145s.

User feedback on `tmp/dikka-candidate-4-suno-priority-developed-postdrop-extra32-v4`: the post-drop was fixed, but the red outro still sounded like a new/glitchy section. Core outro rule clarified: do not add a new section for outro. Continue the exact same groove section that was playing immediately before the outro, then remove/mute the bass line only.

Arranger fix: `club-second-half` outro source now follows the same repeated post-drop slice that was playing immediately before the outro. It no longer blindly uses the tail of the post-drop source window.

Corrected same-groove outro render:

```text
tmp/dikka-candidate-4-suno-priority-same-groove-outro-v5
```

Render settings: same as v4, but the 16-bar outro now uses source bars `48-64`, because those are the final 16 source bars heard at the end of the repeated 96-bar post-drop render (`32-96` looped). Bass/vocals are muted in the outro; other roles continue from the same groove material.

Export contract update for arranger packages:

```text
main arranged-stems/
  use the original Suno drum stem as drums.wav

percussion-reference-stems/
  use DrumSep-derived kick/snare/hihats/cymbals/toms rendered through the same arrangement
```

Reason: the separated drum layers are not production-quality sound sources, but they are useful Ableton reference guides for rhythm, placement, and manual drum replacement. The main musical package sent back to Suno or used as the full arrangement must keep the real Suno drum stem, not the separated drum layers.

Regenerated packages with the corrected drum/reference contract:

```text
/Users/danilulmashev/Desktop/per-hammar-candidate-3-final-package-v2
/Users/danilulmashev/Desktop/dikka-candidate-4-final-package-v2
```

Each package contains `arranged-full-mix.wav`, main `arranged-stems/{drums,bass,synths,fx}.wav`, and reference-only `percussion-reference-stems/{kick,snare,hihats,cymbals,toms}.wav`. The `percussion-reference-stems` are rendered through the same arrangement timing and should be used only as Ableton guides for manual drum replacement.
