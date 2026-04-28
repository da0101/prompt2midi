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

For everyday plugin testing with live backend logs:

```bash
npm run dev:refresh
```

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
- `model-bass-transcription.mid` is a pitch-range filtered bass candidate from model notes. It is not stem-separated bass.
- `bass-transcription.mid` is written when experimental monophonic low-frequency tracking finds note events. Treat it as a legacy heuristic fallback, not a finished extraction.

The result also includes `midi_assets`, a structured list with `kind`, `source_method`, confidence, note count, and limitations for each MIDI file.
