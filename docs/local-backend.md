# Local Backend

The vertical-slice backend is dependency-free Node.js plus Python stdlib analysis.

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

Phase 1 supports uncompressed PCM WAV files. MP3 support is intentionally not guessed in this slice because it needs a decoder dependency decision.
