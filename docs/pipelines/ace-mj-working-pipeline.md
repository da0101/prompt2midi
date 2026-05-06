# ACE MJ-Style Working Pipeline

This is the working setup that produced three good MJ-inspired 30-second proxy batches in a row on May 2, 2026.

The goal is not to create a cover and not to upload the protected reference to Suno. The goal is to use the reference locally, create a new generated proxy demo with the same pocket, energy, rhythm, percussion attitude, and hook role, then upload only that generated proxy to Suno.

## Reference Used

```text
/Users/danilulmashev/Documents/GitHub/prompt2midi/test/fixtures/MJ-testing.m4a
```

## What Worked

The successful setup used ACE-Step in source-conditioned cover/proxy mode:

```text
model: acestep-v15-turbo
task_type: cover
similarity_level: medium-high
reference_start: 8 seconds
duration: 30 seconds
candidates: 4
vocals: enabled
reference_strength: 0.32
cover_noise_strength: 0.14
```

Treat these values as frozen for the accepted MJ proxy recipe. Do not retune them while testing other ideas. New experiments should use new output folders and separate docs so this setup remains reproducible.

The important part is balance. ACE receives enough of the reference to keep the groove, pocket, energy, and character, but the reference strength is low enough that it does not simply copy the song.

Do not use the failed synthetic bass scaffold for this recipe. Do not use Yue for this recipe. Do not render MIDI/square-wave demos for this recipe.

## Why This Is The Locked Recipe

We finally got consistent drums, bass attitude, and MJ-style essence by removing the unstable control layers and letting ACE do the musical work from the real audio reference.

Earlier failed paths tried to help ACE too much:

```text
synthetic bass scaffold
manual generated bass notes
MIDI/square-wave proxy demos
Yue full-song generation
MusicGen-style text generation
over-detailed prompts that buried the useful instruction
```

Those paths either sounded cheap, copied the wrong thing, lost the groove, added off-key notes, or produced random artifacts.

The working path is simpler:

```text
real reference section at 8s
+ ACE cover/proxy mode
+ medium-high similarity
+ vocals enabled
+ moderate reference strength
+ small but real cover noise
+ short prompt that does not fight the audio
= new musical proxy with the same pocket and energy
```

### What Produced The Drums

The drums came from using the actual reference audio as source conditioning, not from trying to describe every drum in text. The `reference_start=8` section contains the clean rhythmic identity: tight dance-pop/electro-funk pulse, crisp percussion, strong backbeat attitude, and forward motion.

ACE hears that timing and energy directly through the reference section. The prompt only reinforces it; it does not have to fully recreate it from words.

### What Produced The Bass Feel

The bass worked once we stopped adding our own bass scaffold. The synthetic/generated bass guides introduced wrong notes, unstable tone, and timing problems.

With the accepted recipe, ACE hears the reference low-end pocket directly, but `reference_strength=0.32` and `cover_noise_strength=0.14` leave enough room for a new generated bass performance. This is why the result can keep the punch, syncopation, and attitude without becoming a literal bassline extraction workflow.

### What Produced The MJ Essence

The MJ-like essence came from the combination of:

```text
the 8-second reference entry point
electro-funk / dance-pop groove profile
minor-key dramatic synth/stab attitude
tight syncopated bass feel
crisp percussion and rhythmic drive
vocal/lead-hook role enabled
moderate source conditioning instead of exact copying
```

The important detail is that we are preserving a role and a feel, not copying a singer, melody, lyric, or master recording. The proxy can then go to Suno as a copyright-safer generated guide.

## What The Pipeline Does

## Clean Testing Lane

For current ACE/Suno proxy testing, use the clean fast sample lane only:

```text
local audio decode
reference analysis
reference section extraction
ACE source-conditioned proxy generation
candidate manifest
Suno proxy packaging
```

The following older/experimental steps stay in the repo but are intentionally bypassed for this lane:

```text
MIDI export
Basic Pitch transcription
Demucs stem splitting
source-aware bass transcription
Python-generated bass scaffold
bass-proxy source guide
structured/MIDI renderer
MusicGen
Yue
full arrangement generation
```

Those pieces are not deleted because they may still matter for other product streams, but they should not run while calibrating ACE proxy quality. The clean lane exists so bad or experimental MIDI/stem/bass paths cannot pollute the audio proxy generation.

## Basic Web UI

Start the local ACE server first:

```bash
npm run ace-step:start
```

Then start the basic UI:

```bash
npm run ace:ui
```

Open:

```text
http://127.0.0.1:47322
```

The UI exposes only safe controls:

```text
ACE server start / stop / restart
similarity level
reference start
duration
candidate count
reference hold, mapped to PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH
variation noise, mapped to PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH
vocals/hook role
prompt direction
```

The default "magic" recipe is:

```text
similarity = medium-high
reference hold = 0.32
variation noise = 0.14
reference start = 8 seconds
duration = 30 seconds
candidates = 4
vocals = enabled
prompt = same tempo and key area as the reference.
```

When the UI starts, it checks `http://127.0.0.1:8001/health`. If ACE is not running, it starts `scripts/services/start-ace-step-api.sh`. If ACE was already running before the UI launched, the UI can still use it and the Stop/Restart buttons can control it.

Browser-window close sends a best-effort stop signal only for an ACE server started by the UI. Browser cleanup is not guaranteed after crashes or force-quit, so use the Stop button when you need to be certain the ACE process is stopped.

### 1. Starts ACE locally

ACE runs as a local server on:

```text
http://127.0.0.1:8001
```

The server loads:

```text
acestep-v15-turbo
acestep-5Hz-lm-0.6B
```

On Apple Silicon, the server may log MLX/MPS fallback messages. That is expected. In cover mode, ACE ultimately uses the DiT/audio model directly for the actual source-conditioned generation.

### 2. Decodes the reference for local use only

Because the source is `.m4a`, the wrapper converts it to a local WAV:

```text
local-reference-for-ace.wav
```

The original reference stays local. It is not packaged for Suno.

### 3. Analyzes the reference

The pipeline extracts enough musical information to condition ACE:

```text
BPM: about 120.19
Key area: F major
Genre lane: electronic / 4-4 / club / electro-funk-ish
Groove: minimal steady groove
Energy: club-pop / electro-funk drive
Vocal role: new vocal hook/chop role, not copied vocals
```

The analysis is not perfect, but for this recipe it is good enough because the audio reference does most of the work.

### 4. Extracts the strongest reference section

We force the section start instead of letting the pipeline choose automatically:

```text
reference_start: 8 seconds
duration: 30 seconds
```

This creates:

```text
exports/reference-section.wav
```

This 8-second start point matters. It catches the groove identity clearly.

### 5. Builds the ACE prompt

The effective generated prompt asks ACE to keep:

```text
same tempo and key area
same groove pocket
same mood and energy
same rhythmic drive
same vocal/lead-hook role
```

But it also asks for:

```text
new bass notes
new secondary percussion
new vocal hook/chop phrases
no copied lyrics
no copied singer identity
no copied master recording
no off-key or alien glitch artifacts
```

The actual short user prompt we pass is intentionally simple:

```text
same tempo and key area as the reference.
```

The pipeline adds the rest from analysis and profile rules.

### 6. Sends source-conditioned request to ACE

The hidden controls are:

```text
reference_strength=0.32
cover_noise_strength=0.14
route=source_conditioned_cover_rich_proxy
vocal_mode=new_vocal_hook
target_similarity=0.4
```

ACE receives the extracted 30-second reference section as both reference/source conditioning. This is what gives it the MJ-style pocket and musical character.

### 7. Generates four candidates

The pipeline writes:

```text
exports/candidate-1.wav
exports/candidate-2.wav
exports/candidate-3.wav
exports/candidate-4.wav
exports/candidate-manifest.json
exports/ace-preflight.json
exports/fast-analysis.json
```

The automatic picker is advisory only. Always listen to all four.

### 8. Packages one generated proxy for Suno

The wrapper chooses the suggested candidate and creates:

```text
suno-proxy-package/suno-upload-proxy.wav
suno-proxy-package/suno-upload-proxy.mp3
suno-proxy-package/suno-proxy-prompt.md
suno-proxy-package/suno-proxy-analysis.md
suno-proxy-package/suno-proxy-package.json
```

Only upload the generated proxy to Suno. Do not upload the original reference.

## Terminal Commands

Run this from the repo:

```bash
cd /Users/danilulmashev/Documents/GitHub/prompt2midi
```

### Terminal 1: Start ACE

Keep this terminal open while generating.

```bash
npm run ace-step:start
```

Wait until you see:

```text
Uvicorn running on http://127.0.0.1:8001
```

### Terminal 2: Generate A New Batch

Change only the output folder name each time.

```bash
cd /Users/danilulmashev/Documents/GitHub/prompt2midi

PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH=0.32 \
PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH=0.14 \
npm run suno:proxy-run -- \
  --reference "/Users/danilulmashev/Documents/GitHub/prompt2midi/test/fixtures/MJ-testing.m4a" \
  --output-dir "/Users/danilulmashev/Documents/GitHub/prompt2midi/tmp/mj-working-test-01" \
  --similarity-level medium-high \
  --duration 30 \
  --candidates 4 \
  --vocals \
  --reference-start 8 \
  --prompt "same tempo and key area as the reference."
```

## Where To Listen

After the run, listen to:

```text
tmp/mj-working-test-01/exports/candidate-1.wav
tmp/mj-working-test-01/exports/candidate-2.wav
tmp/mj-working-test-01/exports/candidate-3.wav
tmp/mj-working-test-01/exports/candidate-4.wav
```

The Suno-ready generated proxy will be:

```text
tmp/mj-working-test-01/suno-proxy-package/suno-upload-proxy.wav
```

## Why This Worked

This worked because we stopped over-controlling ACE.

The failed approaches tried to force a bassline scaffold, add synthetic bass, or use models that did not preserve the musicality. This recipe lets ACE use the real reference section for groove and production DNA, while keeping source strength moderate enough to create a new proxy instead of a direct copy.

The three successful rounds used the same recipe:

```text
tmp/mj-inspired-proxy-v5-rerun-20260502
tmp/mj-inspired-proxy-v5-rerun-20260502-round2
tmp/mj-inspired-proxy-v5-rerun-20260502-round3
```

## Known Limitation

This gives consistent quality, not byte-for-byte identical audio. ACE still uses randomness internally. To make exact repeatable candidates, the pipeline needs seed pinning added later.

For now, generate four candidates and pick by ear.
