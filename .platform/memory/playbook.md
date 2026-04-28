# Playbook

_How work actually gets done in this project. Shortcuts, commands, dev rituals that a 20-year employee would know. Appended during `ab close <slug>` harvest._

Format: `- **[area]** — one-line practice (why/when)`

---

## Entries

<!-- agentboard:playbook:begin -->
<!-- New entries go below, newest first. Keep each entry to one line. -->
- **[JUCE build]** — After changing `prompt2midi.jucer`, run Projucer `--resave`, then verify with `xcodebuild -project Builds/MacOSX/prompt2midi.xcodeproj -scheme "prompt2midi - All" -configuration Debug -derivedDataPath Builds/DerivedData CODE_SIGNING_ALLOWED=NO build`.
- **[local backend]** — Use `npm test`, `node --check backend/server.js`, and `python3 -m unittest analysis/test_feature_extraction.py` as the fast MVP contract gate before JUCE rebuilds.
<!-- agentboard:playbook:end -->
