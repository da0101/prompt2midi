# Local Backend

The local backend uses Node.js orchestration, Python stdlib WAV analysis, and optional `ffmpeg` decoding for MP3 input.

## Run

```bash
npm start
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

MP3 files are decoded into `tmp/jobs/<job_id>/decoded-input.wav` before Python analysis. MIDI output is named `reference-sketch.mid` because it is generated from estimated BPM/key and is not transcription.
