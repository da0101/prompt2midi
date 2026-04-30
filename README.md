# prompt2midi

Local-first AI co-producer for Ableton Live.

prompt2midi analyzes a reference track, turns the musical evidence into producer-readable structure, generates editable MIDI, creates an original inspired loop package, and prepares a Suno-ready prompt. The core path is designed to run locally: JUCE is the Ableton-facing client, Node owns the job API, and Python owns audio analysis and generation helpers.

The product goal is not to copy songs. It is a pre-production tool for making new material from reference traits: tempo, key, groove, drum feel, bass movement, arrangement energy, and production language.

## Current Status

The repo already contains a working local vertical slice:

- JUCE plugin UI for WAV/MP3 selection, prompt entry, job polling, result display, and prompt copy.
- Local Node backend on `127.0.0.1:47321`.
- Python WAV analysis with BPM, key, energy, loudness, spectral features, genre/groove hints, chords, structure, stems, transcription, composition, and optional audio generation.
- Deterministic inspired-loop generator that writes `bass.mid`, `drums.mid`, `chords.mid`, `melody.mid`, `full_loop.mid`, `summary.json`, and `prompt.txt`.
- Optional model paths for Basic Pitch, Demucs, CLAP genre detection, Gemini Suno prompt generation, ACE-Step, and MusicGen.

This is still an MVP/research codebase. Some outputs are production useful, but many model and transcription outputs are explicitly labeled as estimates or editable starting points.

## Why It Exists

Producers often know what they like about a reference record but cannot quickly turn that into reusable production material. prompt2midi closes that gap:

1. Drop in a reference track.
2. Extract musical facts and evidence.
3. Generate original MIDI parts that match the useful traits, not the exact song.
4. Generate a clear AI-music prompt for Suno or similar tools.
5. Optionally render a local 30-second reference-inspired sample before uploading anything elsewhere.

When a generation service rejects direct artist/song prompts, the correct workflow is not to bypass the filter. prompt2midi uses the reference to identify neutral production traits, then creates new musical assets and a prompt that avoids artist imitation, copied hooks, lyrics, and vocal likeness.

Example framing:

- Avoid: `make a Michael Jackson song` or `copy the bassline from this record`.
- Prefer: `1980s pop-funk feel, tight dance groove, bright chord stabs, syncopated bass movement, crisp drums, original melody, no copied lyrics, no vocal imitation`.

The tool is designed to reduce copying risk by creating original material and by describing musical traits instead of requesting a clone. It does not guarantee legal clearance, does not replace rights review, and should not be used to bypass copyright or platform policies.

## Architecture

```text
Ableton / JUCE plugin
        |
        | POST /analyze
        v
Local Node backend
        |
        | validates input, decodes MP3, creates job, calls Python
        v
Python analysis engine
        |
        | returns structured JSON, MIDI paths, composition package, optional audio sample
        v
Node aggregation
        |
        | deterministic producer prompt, optional Gemini Suno prompt
        v
JUCE result display
```

### Component Responsibilities

| Layer | Files | Responsibility |
|---|---|---|
| JUCE plugin | `Source/PluginEditor.*`, `Source/PluginProcessor.*`, `Source/LocalApiClient.h` | UI only: choose/drop reference, send local job, poll status, show results. Audio processing stays pass-through. |
| Node backend | `backend/server.js`, `backend/lib/*` | Local API, job state, input validation, MP3 decode, Python invocation, prompt aggregation, error normalization. |
| Python analysis | `analysis/analyze.py`, `feature_extraction.py`, `enhanced_analysis.py`, `chord_detection.py`, `structure_analysis.py`, `genre_detection.py`, `drum_analysis.py` | Extract structured musical facts from WAV audio. Optional libraries improve results, but fallback paths keep the core running. |
| MIDI/transcription | `analysis/midi_extraction.py`, `bass_transcription.py`, `source_transcription.py`, `stem_separation.py` | Write MIDI, run Basic Pitch, run Demucs, expose provenance and limitations for every MIDI asset. |
| Composition | `analysis/composition.py`, `composition_patterns.py` | Generate a new original loop package from analysis hints. This is the main product output. |
| Prompting | `backend/lib/promptGenerator.js`, `backend/lib/geminiPromptGenerator.js` | Turn structured facts into producer-facing copy and Suno prompts. Gemini is optional. |
| Audio generation | `analysis/audio_generation.py`, `ace_step_generation.py`, `audiocraft_musicgen.py`, `musicgen_generation.py` | Optional local sample generation using ACE-Step first, then AudioCraft/MusicGen fallback paths. |

## End-to-End Flow

### 1. User Input

The plugin accepts:

- A local `.wav` / `.wave` / `.mp3` reference file.
- A text direction.
- Or prompt-only mode when no audio file is supplied.

The plugin posts JSON to the local backend:

```json
{
  "audioPath": "/absolute/path/to/reference.mp3",
  "prompt": "same groove, change the bass notes a little, replace the main stab"
}
```

### 2. Node Job Orchestration

`backend/server.js` exposes:

- `GET /health`
- `POST /analyze`
- `GET /status?id=<job_id>`
- `GET /result?id=<job_id>`

Node creates a job immediately so the plugin remains responsive. It validates absolute audio paths, rejects unsupported formats, enforces a size limit, and decodes MP3 input through `ffmpeg` into `tmp/jobs/<job_id>/decoded-input.wav`.

Node then starts `analysis/analyze.py` as a child process and records pipeline events so the UI can show progress.

### 3. Python Feature Analysis

The Python engine reads PCM WAV and returns structured JSON. The dependency-free base path extracts:

- duration, sample rate, channel count
- energy curve
- loudness
- zero-crossing rate and peak amplitude
- approximate BPM
- approximate key
- warnings when confidence is low

Optional `librosa`/`scipy` paths improve:

- BPM estimation
- key estimation
- chord progression detection
- arrangement/section analysis
- groove descriptors

Optional CLAP genre detection uses `laion/larger_clap_music` through `transformers` when available.

### 4. Stem and MIDI Evidence

Every MIDI file is labeled by source and confidence.

| Asset | How it is made | Meaning |
|---|---|---|
| `reference-sketch.mid` | Deterministic pattern from estimated BPM/key | Generated sketch, not transcription. |
| `model-transcription.mid` | Basic Pitch on full mix | Model transcription candidate; needs ear correction. |
| `source-bass-transcription.mid` | Demucs bass stem + Basic Pitch | Stem-aware bass candidate; still may contain bleed. |
| `source-drum-groove.mid` | Demucs drums stem + onset detection | Quantized drum groove estimate. |
| `model-bass-transcription.mid` | Pitch-filtered Basic Pitch notes from full mix | Fallback bass candidate, not source-separated. |
| `bass-transcription.mid` | Monophonic low-frequency tracking | Legacy heuristic fallback. |

Recommended evidence exports are copied to:

```text
tmp/jobs/<job_id>/exports/
```

The code intentionally distinguishes generated MIDI from transcription evidence. This matters because only source-aware paths should be described as source-aware.

### 5. Reference Transformation

`analysis/reference_groove.py` fingerprints the reference for:

- kick accents
- bass accents
- hat/percussion accents
- swing
- low-end weight
- bass note tendencies
- club energy

`analysis/reference_transform.py` converts the user's direction into controls such as:

- preserve groove similarity
- keep bass rhythm but vary notes
- replace a stab/timbre role
- keep kick and hat feel while using new samples

This is the bridge between "I like this song" and "make a new production with similar traits."

### 6. Original Composition Package

`analysis/composition.py` generates the main product output:

```text
tmp/jobs/<job_id>/exports/
  midi/
    bass.mid
    drums.mid
    chords.mid
    melody.mid
    full_loop.mid
  summary.json
  prompt.txt
```

The generator is deterministic in structure but randomized in musical choices. It uses BPM, key, detected chords, drum pattern evidence, genre/style hints, and user direction to choose one of several composition modes:

- house
- techno
- synth wave
- hip hop
- ambient

`full_loop.mid` is MIDI format type 1 so a DAW can import separate tracks.

### 7. Suno Prompt Package

There are two prompt paths:

1. Python stub prompt from `composition.py`, always local.
2. Optional Gemini prompt from `backend/lib/geminiPromptGenerator.js` when `GEMINI_API_KEY` is present.

The Gemini path uses `gemini-2.0-flash` by default and writes a single Suno paragraph from structured analysis and composition data. If Gemini is disabled, missing, times out, or fails, the job still succeeds with the local stub prompt.

The prompt contract ends with a protective instruction:

```text
Instrumental, no vocals. Inspired by the reference groove and production style, not a cover and not a copy.
```

### 8. Optional Local Audio Sample

`analysis/audio_generation.py` can prepare a 30-second local sample before the user uploads anything to Suno.

Provider order:

1. ACE-Step local API, enabled by `PROMPT2MIDI_ENABLE_ACE_STEP=1`.
2. AudioCraft MusicGen, enabled by `PROMPT2MIDI_ENABLE_AUDIOCRAFT=1`.
3. Transformers MusicGen Melody, enabled by `PROMPT2MIDI_ENABLE_MUSICGEN=1`.

ACE-Step uses a local API at `127.0.0.1:8001` by default and model settings around:

- `acestep-v15-turbo`
- `acestep-5Hz-lm-0.6B`
- MLX backend by default on macOS

The sample is scored for duration, loudness, pulse consistency, clipping, harshness, and reference groove similarity. The score helps pick the best candidate, but listening is still required.

## Models and Engines

| Engine | Required? | Purpose | Setup |
|---|---:|---|---|
| Python stdlib WAV analyzer | Yes | Base BPM/key/energy/loudness/spectral analysis | Built in |
| `ffmpeg` | For MP3 | Decode MP3 to WAV and export reference sections | Install separately or set `PROMPT2MIDI_FFMPEG` |
| `librosa` / `scipy` | Optional | Better BPM/key, chords, structure, drums, groove | Python environment |
| CLAP `laion/larger_clap_music` | Optional | Zero-shot genre tags | Python ML deps |
| Basic Pitch | Optional | Model MIDI transcription | `npm run setup:transcription` |
| Demucs `htdemucs` | Optional | Bass/drum/other/vocal stems | `npm run setup:stems` |
| Gemini `gemini-2.0-flash` | Optional cloud | Higher quality Suno prompt | `GEMINI_API_KEY=...` |
| ACE-Step 1.5 | Optional local service | Reference-guided audio samples | `npm run setup:ace-step`, then `npm run ace-step:start` |
| AudioCraft MusicGen | Optional local | Fallback sample generation | `npm run setup:musicgen` |
| Transformers MusicGen Melody | Optional local | Legacy fallback sample generation | Set `PROMPT2MIDI_ENABLE_MUSICGEN=1` with deps installed |

## Legal and Platform-Safety Position

prompt2midi is built around reference-inspired transformation, not cloning.

It should:

- Analyze traits instead of copying a recording.
- Generate new MIDI instead of exporting copyrighted melodies as final output.
- Use neutral production language instead of artist-name prompting.
- Avoid vocals, lyrics, artist likeness, copied hooks, and exact bass/melody sequences.
- Keep every extracted/transcribed artifact labeled as evidence, not guaranteed clearance.

It should not:

- Promise that any output is free of legal issues.
- Claim to bypass Suno copyright filters.
- Recreate a protected song, master recording, vocal likeness, lyric, or signature hook.
- Tell users that a generated sample is automatically safe to upload commercially.

Use references you own, created, licensed, or are otherwise allowed to analyze. Treat the generated Suno prompt and local sample as a safer creative starting point, not legal advice.

## Running Locally

Install Node dependencies:

```bash
npm install
```

Start the backend:

```bash
npm start
```

Run the developer loop with backend logs:

```bash
npm run dev:refresh
```

Install optional engines:

```bash
npm run setup:transcription
npm run setup:stems
npm run setup:ace-step
npm run setup:musicgen
```

Start ACE-Step when using local sample generation:

```bash
npm run ace-step:start
```

Useful environment flags:

```bash
PROMPT2MIDI_DISABLE_MODEL=1
PROMPT2MIDI_DISABLE_STEMS=1
PROMPT2MIDI_DISABLE_SUNO=1
PROMPT2MIDI_DISABLE_LIBROSA=1
PROMPT2MIDI_DISABLE_GENRE=1
PROMPT2MIDI_DISABLE_CHORDS=1
PROMPT2MIDI_DISABLE_STRUCTURE=1
PROMPT2MIDI_DISABLE_DRUMS=1
PROMPT2MIDI_ENABLE_ACE_STEP=1
PROMPT2MIDI_ENABLE_AUDIOCRAFT=1
PROMPT2MIDI_ENABLE_MUSICGEN=1
GEMINI_API_KEY=...
```

## API Example

```bash
curl -s -X POST http://127.0.0.1:47321/analyze \
  -H 'Content-Type: application/json' \
  -d '{"audioPath":"/absolute/path/to/reference.wav","prompt":"keep the groove, vary the bass notes, replace the stab sound"}'
```

Poll status:

```bash
curl -s 'http://127.0.0.1:47321/status?id=<job_id>'
```

Fetch result:

```bash
curl -s 'http://127.0.0.1:47321/result?id=<job_id>'
```

## Testing

Run Python tests:

```bash
python3 -m unittest analysis/test_feature_extraction.py
python3 -m unittest analysis/test_composition.py
```

Run Node tests:

```bash
npm test
```

Compile-check Python:

```bash
python3 -m compileall analysis
```

## Important Invariants

- Keep the core workflow local-first.
- Do not run long jobs, subprocesses, network calls, or file-heavy analysis in JUCE `processBlock`.
- Node owns orchestration and aggregation.
- Python returns structured analysis JSON and file paths.
- Generated MIDI is product output; extracted MIDI is evidence.
- Optional engines must degrade to warnings, not hard job failure.
- Producer-facing copy must describe confidence and limitations honestly.
