# Playbook

_How work actually gets done in this project. Shortcuts, commands, dev rituals that a 20-year employee would know. Appended during `ab close <slug>` harvest._

Format: `- **[area]** — one-line practice (why/when)`

---

## Entries

<!-- agentboard:playbook:begin -->
<!-- New entries go below, newest first. Keep each entry to one line. -->
- **[audio smoke]** — For real-file checks, run the provided MP3 through `backend/lib/pythonRunner.runAnalysis`; expect `reference-sketch.mid` and optional `bass-transcription.mid`, then inspect warnings before judging accuracy.
- **[JUCE build]** — After changing `prompt2midi.jucer`, run Projucer `--resave`, then verify with `xcodebuild -project Builds/MacOSX/prompt2midi.xcodeproj -scheme "prompt2midi - All" -configuration Debug -derivedDataPath Builds/DerivedData CODE_SIGNING_ALLOWED=NO build`.
- **[local backend]** — Use `npm test`, `node --check backend/server.js`, and `python3 -m unittest analysis/test_feature_extraction.py` as the fast MVP contract gate before JUCE rebuilds.
<!-- agentboard:playbook:end -->
