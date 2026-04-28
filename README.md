# prompt2midi
Generate MIDI patterns from natural language prompts using ChatGPT and Python. Connects seamlessly with Ableton Live via a custom AU plugin.

## Local vertical slice

Start the local backend:

```bash
npm start
```

Run tests:

```bash
python3 -m unittest analysis/test_feature_extraction.py
npm test
```

The backend listens on `http://127.0.0.1:47321` and exposes:

- `POST /analyze`
- `GET /status?id=<job_id>`
- `GET /result?id=<job_id>`

Phase 1 supports prompt-only jobs and uncompressed PCM WAV analysis. MP3/stem extraction requires a decoder/model dependency decision.
