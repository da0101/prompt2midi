# prompt2midi — Decision Log

Last updated: 2026-04-28

> **Purpose:** capture the _why_ behind architectural, product, and tooling decisions so future AI sessions and developers don't have to re-derive them (or undo them).

---

## Format

Each decision is one row. **Locked** decisions are final until a new decision supersedes them. **Deferred** decisions are explicit non-decisions with a trigger for when to revisit.

| # | Date | Status | Topic | Decision | Why | Rejected alternatives |
|---|---|---|---|---|---|---|

---

## Locked decisions

| # | Date | Topic | Decision | Why | Rejected alternatives |
|---|---|---|---|---|---|
| 1 | 2026-04-28 | Product source of truth | Treat `promt.md` as the exact execution plan. | The owner explicitly confirmed it defines the project. | Inferring scope only from the starter JUCE code. |
| 2 | 2026-04-28 | Product scope | Build both prompt-to-MIDI and full audio-track analysis. | The owner confirmed both are required, and the execution plan describes both. | Narrowing MVP permanently to only prompt input or only analysis. |
| 3 | 2026-04-28 | Architecture | Use JUCE plugin + local Node orchestrator + Python analysis engine + local LLM layer. | This keeps the DAW UI thin, signal processing modular, and interpretation separate from analysis. | Putting all logic in the plugin; mixing producer prose into Python feature extraction. |
| 4 | 2026-04-28 | Local-first constraint | Core workflow must run locally and must not require cloud APIs. | `promt.md` lists local-first/no cloud dependency as hard constraints. | Making OpenAI/ChatGPT API calls mandatory for the main path. |
| 5 | 2026-04-28 | Threading boundary | Heavy work must stay out of JUCE `processBlock` and the audio thread. | Ableton plugin stability depends on non-blocking processing. | Running analysis, HTTP, subprocesses, or file-heavy logic in audio callbacks. |
| 6 | 2026-04-28 | First backend slice | Use dependency-free Node stdlib HTTP/job orchestration and Python stdlib WAV analysis for the first vertical slice. | It proves the end-to-end contract immediately and keeps FastAPI/MP3/model choices reversible. | Introducing framework and decoder dependencies before the API and result contract are stable. |
| 7 | 2026-04-28 | MP3 input | Use FFmpeg as the MP3 boundary adapter and keep Python analysis WAV-only. | FFmpeg handles decoding locally without forcing Python audio dependencies into the analysis core. | Requiring users to pre-convert MP3s; adding a Python decoder dependency before deeper analysis is designed. |
| 8 | 2026-04-28 | MIDI truthfulness | Expose heuristic bass tracking only as experimental `bass-transcription.mid` and keep `reference-sketch.mid` separate. | The user needs useful MIDI exports, but full-mix low-frequency tracking is not source-separated transcription. | Renaming the sketch to imply accuracy; hiding the experimental file behind the same label. |
| 9 | 2026-04-28 | Model MIDI transcription | Use Basic Pitch as an optional isolated local engine for first-pass model MIDI transcription. | It provides a real audio-to-MIDI model without cloud APIs and can be installed separately from the dependency-free analyzer. | Pretending stdlib heuristics are final; making Basic Pitch mandatory for the baseline backend. |
| 10 | 2026-04-28 | Stem-aware bass transcription | Use Demucs as an optional isolated local stem engine before Basic Pitch bass MIDI. | It produces a real bass stem locally while preserving graceful fallback when the heavy dependency is absent. | Making Demucs mandatory; continuing to label full-mix bass filtering as source-aware transcription. |

---

## Deferred decisions

| # | Date | Topic | Current non-decision | Trigger to revisit |
|---|---|---|---|---|
| 1 | 2026-04-28 | Local LLM runtime | Model/runtime is not selected yet. | Before implementing Phase 5 interpretation. |
| 2 | 2026-04-28 | Repo split | Node and Python can start in this repo; split is undecided. | When backend/analysis code becomes large enough to need separate release/versioning. |
| 3 | 2026-04-28 | First plugin format | AU/VST3/standalone release order is undecided. | Before packaging or Ableton acceptance testing. |
| 4 | 2026-04-28 | Cloud API framework | Public cloud API may stay Node or move to FastAPI; endpoint contract should remain stable either way. | Before cloud deployment/auth/audio upload design. |

---

## How to add a decision

1. Use the highest unused `#`.
2. Fill date, status, topic, decision, why, rejected alternatives.
3. If this supersedes a prior decision, reference it: "Supersedes #N".
4. If it's deferred, include a trigger condition.
5. Commit with message: `Record decision #N: <topic>`.
