# prompt2midi — Current Status

Last updated: 2026-05-06

prompt2midi is an open-source, local-first AI co-producer for producers and artists. It can be used as a DAW inspiration starter for Ableton/Logic/other DAWs, or as a pre-SUNO tool for turning a reference-inspired idea into a cleaner prompt, structure guide, MIDI package, and optional proxy material.

`develop` is the default branch for daily work. `main` is release-only and should receive merges from `develop` when creating version tags.

## Feature Areas

| Area | Status | Last touched | Notes |
|---|---|---|---|
| JUCE plugin client | 🔵 Exists | 2026-05-06 | WAV/MP3 selection, prompt entry, job polling, result display, copy prompt. Full AU/VST integration and host QA are next production work. |
| Local Node backend | 🔵 Exists | 2026-05-06 | Localhost API with `/health`, `/analyze`, `/status`, `/result`, job state, MP3 decode, Python bridge, aggregation. |
| Python analysis engine | 🔵 Exists | 2026-05-06 | Structured BPM/key/energy/loudness/spectral/genre/chord/drum/structure outputs. Optional engines improve results but must fail soft. |
| Stem splitting / MIDI mapping | ⚠ Flagged | 2026-05-06 | Useful evidence path, but still weak. Needs better source-aware cleanup, note ownership, quantization, register selection, and confidence labeling. |
| Composition package | 🔵 Exists | 2026-05-06 | Generates original bass/drums/chords/melody/full_loop MIDI, summary, and prompt package. |
| Full Arrangement / proxy flow | 🔵 Exists | 2026-05-06 | Arrangement Lock, structure maps, guide MIDI, SUNO proxy package, optional ACE/local audio candidates. |
| Gemini SUNO prompt | ⚠ Blocked | 2026-05-06 | Code exists, but real `GEMINI_API_KEY` + WAV smoke test is still required before closure. |
| Branch/release flow | ✓ Done | 2026-05-06 | GitHub default branch is `develop`; `main` is release-only; CODEOWNERS assigns all changes to `@da0101`. |

**Legend:** ✓ Done, 🔵 Exists, ⚠ Flagged/blocked, ⧗ Pending, 🔴 Deferred.

## Immediate Priorities

1. **Release v1.0.0 baseline** — merge `develop` to `main` and tag once docs/platform refresh is committed.
2. **Improve stem/MIDI quality** — source-aware mapping, cleanup, quantization, register choice, confidence labels.
3. **Complete JUCE AU/VST integration** — reliable plugin build/install, Ableton host QA, import/export ergonomics.
4. **Unblock Gemini SUNO prompt stream** — run a real-key smoke test and verify `exports/prompt.txt` is Gemini-generated.

## Release Blocklist

- [x] Branch flow documented and `develop` set as default.
- [x] CODEOWNERS added for owner review.
- [x] Local backend and Python analysis path exist.
- [x] README/platform docs describe current architecture.
- [ ] Full AU/VST/JUCE workflow verified in a real DAW host.
- [ ] Stem/MIDI evidence improved beyond weak MVP mapping.
- [ ] Real Gemini SUNO prompt smoke test completed or explicitly deferred.

## Known Gotchas

- Stem splitting and MIDI mapping are not production-grade yet; treat extracted MIDI as editable evidence.
- JUCE must remain the client/UI layer; do not put long-running work in `processBlock`.
- Optional cloud/model engines must not be required for the core workflow.
- `develop` is the default branch for feature work; `main` is for releases and tags.
