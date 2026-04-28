# Local Backend

The local backend uses Node.js orchestration, Python stdlib WAV analysis, and optional `ffmpeg` decoding for MP3 input.

## Run

```bash
npm start
```

For local model MIDI transcription, install the isolated Basic Pitch engine:

```bash
npm run setup:transcription
```

For optional stem-aware bass transcription, install the isolated Demucs engine:

```bash
npm run setup:stems
```

For everyday plugin testing with live backend logs:

```bash
npm run dev:refresh
```

The dev loop prints color-coded pipeline logs for each job: input validation, MP3 decode, Python analysis/model transcription, prompt generation, result aggregation, warnings, MIDI asset paths, note counts, and timing.

Default address:

```text
http://127.0.0.1:47321
```

## Endpoints

- `GET /health`
- `POST /analyze`
- `GET /status?id=<job_id>`
- `GET /result?id=<job_id>`

`POST /analyze` accepts:

```json
{
  "audioPath": "/absolute/path/to/file.wav",
  "prompt": "dark groovy tech house at 124 BPM in A minor"
}
```

Supported reference files:

- `.wav` / `.wave` PCM files
- `.mp3` files when `ffmpeg` is on `PATH` or `PROMPT2MIDI_FFMPEG` points to the binary

MP3 files are decoded into `tmp/jobs/<job_id>/decoded-input.wav` before Python analysis.

MIDI outputs:

- `reference-sketch.mid` is always generated from estimated BPM/key and is not transcription.
- `model-transcription.mid` is written when the Basic Pitch engine is installed. It is model MIDI from the supplied mix and should still be corrected by ear.
- `source-bass-transcription.mid` is written when both Demucs and Basic Pitch are installed. Demucs first separates a bass stem, then Basic Pitch transcribes that stem. It is usually more useful than full-mix bass filtering, but still needs ear correction because separated stems can contain bleed.
- `model-bass-transcription.mid` is a pitch-range filtered bass candidate from model notes. It is not stem-separated bass.
- `bass-transcription.mid` is written when experimental monophonic low-frequency tracking finds note events. Treat it as a legacy heuristic fallback, not a finished extraction.

The result also includes `midi_assets`, a structured list with `kind`, `source_method`, confidence, note count, and limitations for each MIDI file.

Product-facing MIDI is copied into `tmp/jobs/<job_id>/exports/` and marked with `is_recommended_output: true`.
Use that folder when auditioning or giving feedback. Other files in the job folder are retained as debug/intermediate artifacts.

Optional engines are capability-gated:

- `PROMPT2MIDI_DISABLE_MODEL=1` disables Basic Pitch.
- `PROMPT2MIDI_BASIC_PITCH=/path/to/basic-pitch` overrides Basic Pitch discovery.
- `PROMPT2MIDI_DISABLE_STEMS=1` disables Demucs.
- `PROMPT2MIDI_DEMUCS=/path/to/demucs` overrides Demucs discovery.
- `PROMPT2MIDI_STEM_TIMEOUT_SECONDS=360` controls Demucs timeout.
