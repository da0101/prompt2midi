# Manual Verification

## Local backend

1. Run `npm start`.
2. In another terminal, submit a prompt-only job:

```bash
curl -s -X POST http://127.0.0.1:47321/analyze \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"dark groovy tech house at 124 BPM in A minor"}'
```

3. Poll `GET /status?id=<job_id>` until `succeeded`.
4. Fetch `GET /result?id=<job_id>`.

Expected:

- Result includes `analysis.bpm`, `analysis.key`, `interpretation.producer_summary`, `interpretation.ai_music_prompt`.
- Reference jobs create `tmp/jobs/<job_id>/reference-sketch.mid`.
- The result labels that MIDI as a generated sketch, not source-track transcription.
- With `npm run setup:transcription` completed, reference jobs also create `model-transcription.mid` and usually `model-bass-transcription.mid`.
- When low-frequency note tracking finds events, jobs also create `tmp/jobs/<job_id>/bass-transcription.mid`.
- The bass transcription is experimental monophonic tracking and should be edited by ear.
- MP3 jobs include an analysis warning that the input was decoded through `ffmpeg`.
- Low-confidence BPM/key results should say possible/unverified instead of sounding authoritative.

## JUCE plugin

The editor is wired to the local backend at `http://127.0.0.1:47321`.

1. Start the backend with `npm run dev:refresh` so server logs stay visible.
2. Open the plugin UI.
3. Drop or choose a `.wav`, `.wave`, or `.mp3` file, or enter a prompt only.
4. Click Analyze.
5. Confirm status moves through the local job and results render in the text area.
6. Click Copy Prompt and paste into a text editor.

## Build output

JUCE is expected at `/Applications/JUCE`. The project has been resaved with Projucer and Debug builds are generated under:

- `Builds/MacOSX/build/Debug/prompt2midi.app`
- `Builds/MacOSX/build/Debug/prompt2midi.component`
- `Builds/MacOSX/build/Debug/prompt2midi.vst3`

The AU/VST3 build also copies plugin bundles into the user plugin folders when the full Xcode scheme runs successfully.
