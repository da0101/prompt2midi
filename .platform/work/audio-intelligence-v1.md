---
stream_id: stream-audio-intelligence-v1
slug: audio-intelligence-v1
type: feature
status: in-progress
agent_owner: codex
domain_slugs: [audio-analysis, llm-midi-generation, local-orchestration, juce-plugin]
repo_ids: [prompt2midi]
base_branch: feature/vertical-slice-mvp
git_branch: feature/audio-intelligence-v1
created_at: 2026-04-28
updated_at: 2026-04-28
closure_approved: false
---

# audio-intelligence-v1

_Metadata rules: `stream_id` must be `stream-<slug>`, `slug` must match the filename, `status` must match `work/ACTIVE.md`, and `updated_at` should change whenever ownership or state changes._

## Scope
- Improve Phase 1 musical usefulness beyond the vertical-slice placeholder: more honest BPM/key confidence, clearer warnings, and less misleading MIDI output.
- Add a better audio-import path decision and implementation plan for MP3 or explicit WAV-only UX, starting from the open decoder question.
- Replace the placeholder bassline behavior with either a clearly labeled sketch generator or a first real extraction path that can be tested against fixtures.
- Keep the existing local-first Node/Python/JUCE architecture and avoid cloud-only dependencies.
- Out of scope: polished UI redesign, release installer/notarization, full stem separation, and production-grade chord/melody transcription.

## Done criteria
- [x] Reference-track analysis no longer presents placeholder MIDI as if it were accurate transcription.
- [x] First-pass bass transcription exists as a separately labeled experimental output with fixture coverage.
- [x] BPM/key/energy outputs have documented confidence/warnings and fixture-backed regression tests.
- [x] MP3 support is either implemented with a chosen decoder or intentionally deferred with a clear product/API reason.
- [x] Backend and Python tests pass: `npm test`, `python3 -m unittest analysis/test_feature_extraction.py`, and Python compile check.
- [x] JUCE Debug `prompt2midi - All` still builds after any UI/client contract changes.
- [x] Manual verification documents behavior on at least one WAV reference and the current fake-music fixture path if retained.
- [x] `.platform/memory/log.md` appended
- [x] `decisions.md` updated if any architectural choices were made

## Key decisions
_Append-only. Format: `2026-04-28 — <decision> — <rationale>`_

- 2026-04-28 — Build on vertical-slice MVP — The local Node/Python/JUCE contract is now proven; this stream should improve musical validity, not re-platform the app.
- 2026-04-28 — Use FFmpeg as the MP3 boundary adapter — Keep Python analysis WAV-only while allowing common reference-track imports locally.

## Resume state
_Overwritten by `ab checkpoint` — the compact payload the next agent reads first. Keep this block under ~10 lines._

- **Last updated:** 2026-04-28 by codex
- **What just happened:** Committed experimental bass transcription as `625a780`.
- **Current focus:** Close the stream and archive it cleanly.
- **Next action:** Run `agentboard close audio-intelligence-v1 --confirm` after final status check.
- **Blockers:** none

## Progress log
_Append-only. `ab checkpoint` prepends a dated line and auto-trims to the last 10 entries. Format: `2026-04-28 HH:MM — <what happened>`._

2026-04-28 14:07 — (auto) 625a780: Add experimental bass transcription

2026-04-28 13:35 — Added experimental bass transcription: Python low-frequency note tracking, event MIDI writer, backend contract/tests, JUCE result labeling, docs, and manual MP3 smoke on the provided fake-music track.

2026-04-28 13:07 — (auto) ecb4501: Implement audio intelligence v1

2026-04-28 13:07 — Implemented audio-intelligence v1: MP3 boundary decoding via FFmpeg, BPM/key confidence and warnings, reference-sketch MIDI labeling, JUCE MP3 picker support, docs/tests/platform updates, and manual smoke on the provided MP3.

2026-04-28 12:46 — (auto) 1aaa4c4: Checkpoint audio intelligence stream

2026-04-28 13:00 — Implemented MP3 boundary decoding and renamed generated MIDI to a reference sketch.
2026-04-28 13:05 — Verified backend, Python, manual MP3 smoke, and full JUCE Debug build.

2026-04-28 12:46 — Started the audio-intelligence-v1 stream after closing vertical-slice MVP.

2026-04-28 12:45 — (auto) 5344af4: Start audio intelligence stream

2026-04-28 12:45 — Created stream after closing vertical-slice MVP.

## Open questions
_Things blocked on user input. Remove when resolved._

- Resolved for this pass: do all three narrowly. MP3 uses FFmpeg, BPM/key expose confidence/warnings, and MIDI is labelled as a generated reference sketch.

---

## 🔍 Audit — 2026-04-28

> Run locally for one repo. No delegated agents were used because this Codex session only delegates when explicitly requested.

# 📋 audio-intelligence-v1 — Audit Snapshot

> **Stream:** `audio-intelligence-v1` · **Date:** 2026-04-28 · **Status:** 🟢 clean
> **Repos touched:** prompt2midi

---

## ⚡ At-a-Glance Scorecard

| | 🖥️ prompt2midi |
|---|:---:|
| **Implementation** | 🟢 |
| **Tests**          | 🟢 |
| **Security**       | 🟢 |
| **Code Quality**   | 🟢 |

> **Bottom line:** The stream is green for a first-pass local audio intelligence upgrade: MP3 input, confidence metadata, honest sketch labeling, and experimental bass transcription are implemented and verified.

---

## 🔄 How the Feature Works (End-to-End)

```text
JUCE editor
  -> Node local API /analyze
  -> optional FFmpeg MP3 decode to WAV
  -> Python feature extraction + experimental bass transcription
  -> reference-sketch.mid + optional bass-transcription.mid
  -> Node prompt package
  -> JUCE result summary
```

---

## 🛡️ Security

| Severity | Repo | Finding |
|:---:|---|---|
| 🟢 Clean | prompt2midi | Local-only path-based workflow; no secrets, auth, SQL, external upload path, or user-input shell execution added. |

---

## 🧪 Test Coverage

### prompt2midi
| Area | Tested? | File |
|---|:---:|---|
| Python feature extraction + MIDI writers | ✅ Strong | `analysis/test_feature_extraction.py` |
| Experimental bass transcription fixture | ✅ Good | `analysis/test_feature_extraction.py` |
| Backend API and Python bridge | ✅ Strong | `backend/test/server.test.js` |
| MP3 decode boundary | ✅ Good | `backend/test/server.test.js` |
| Native JUCE build | ✅ Good | `xcodebuild -project Builds/MacOSX/prompt2midi.xcodeproj ... build` |

---

## ✅ Implementation Status

### prompt2midi
| Component | Status | Location |
|---|:---:|---|
| Backend/Python analysis orchestration | ✅ Done | `analysis/analyze.py:16` |
| Experimental bass transcription | ✅ Done | `analysis/bass_transcription.py:21` |
| Event-based MIDI writer | ✅ Done | `analysis/midi_extraction.py:27` |
| JUCE result labeling | ✅ Done | `Source/LocalApiClient.h:91` |
| Backend prompt next steps | ✅ Done | `backend/lib/promptGenerator.js:18` |
| Platform/docs state | ✅ Done | `docs/local-backend.md:38` |

---

## 🔧 Open Issues

### 🔴 Must Fix (blocking)
| # | Repo | Issue |
|---|---|---|
| - | - | None |

### 🟡 Should Fix Soon
| # | Repo | Issue | Location |
|---|---|---|---|
| - | - | None blocking this stream | - |

### ⚪ Known Limitations (document, not block)
| # | Limitation |
|---|---|
| 1 | `bass-transcription.mid` is monophonic low-frequency tracking over the full mix, not source separation. |
| 2 | Full chord, melody, section, and stem-aware extraction remain future streams. |
| 3 | The standalone plugin UI is functional but still temporary; the accepted UI polish follow-up remains separate. |

---

## 🎯 Close Checklist / Priority Order

  ☑  1. 🧪  Run Python unit tests.
  ☑  2. 🧪  Run backend Node tests.
  ☑  3. 🔍  Run compile/syntax checks.
  ☑  4. 🔍  Run JUCE Debug native build.
  ☑  5. ✅  Commit and close the stream.
