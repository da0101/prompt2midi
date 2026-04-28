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

Phase 2 accepts prompt-only jobs plus WAV/WAVE and MP3 references. MP3 input is decoded locally with `ffmpeg` before the Python WAV analyzer runs.

MIDI output always includes `reference-sketch.mid`, generated from estimated BPM/key only. When low-frequency pitch tracking finds usable note events, the job also writes `bass-transcription.mid`; that file is experimental monophonic bass tracking, not full source-track transcription.
