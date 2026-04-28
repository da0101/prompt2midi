# prompt2midi — Architecture

Last updated: 2026-04-28

`promt.md` is the execution plan. The system is a local-first AI music analysis and generation assistant for Ableton Live, built around a JUCE plugin UI, a local Node orchestration layer, a Python audio-analysis engine, and a local LLM interpretation layer.

---

## 1. What this system does

prompt2midi helps producers turn an audio reference or natural-language prompt into actionable production knowledge: BPM, key, structure, instruments, chords, energy, MIDI assets, and AI-generation prompts. The target user works inside Ableton Live and should not need to manage technical details.

Technically, the JUCE plugin is the Ableton-facing UI/client. It sends local file paths and prompts to a backend on the same machine. The backend runs long analysis jobs, calls Python for signal processing/MIDI extraction, optionally calls a local LLM runtime for interpretation, then returns structured and human-readable results.

**Who uses it:** music producers working in Ableton Live
**Who deploys it:** project owner/manual local builds first
**Hosting target:** local desktop process plus AU/VST3/standalone JUCE plugin on macOS first

## 2. High-level components

```text
Ableton Live
  -> JUCE plugin UI/client
  -> local Node orchestrator
  -> Python analysis engine
  -> local LLM interpretation layer
  -> JSON results + MIDI files + producer prompts
  -> JUCE result/export UI
```

The current repository contains the JUCE project (`prompt2midi.jucer`) and starter plugin source. Node and Python components are planned by `promt.md` but are not implemented yet.

## 3. Tech stack (summary)

| Layer | Choice | Notes |
|---|---|---|
| Plugin | C++ / JUCE | Current code in `Source/`; Mac exporter in `Builds/MacOSX`. |
| DAW target | Ableton Live | Plugin should prioritize AU/VST3-style workflows. |
| Orchestrator | Node.js | Planned REST API, queue, job status, progress, LLM bridge. |
| Analysis | Python | Planned modular audio feature extraction, segmentation, MIDI extraction. |
| LLM | Local runtime first | Converts structured JSON into producer insights and AI prompt text. |
| Build tools | Projucer/JUCE + Xcode | Current `.jucer` has Xcode Mac exporter. |
| Data store | Local files/job state | No persistent server database defined yet. |
| CI/CD | Not defined | Manual local builds for now. |

Per-stack conventions live in `conventions/{stack}.md`.

## 4. Data flow

1. User loads the plugin in Ableton and drops an audio file or enters a prompt.
2. JUCE sends a local file path/prompt to the Node API without blocking UI/audio processing.
3. Node creates a job, exposes progress, and invokes Python analysis.
4. Python returns structured JSON for tempo, key, energy, loudness, and later sections, stems, chords, and MIDI paths.
5. Node sends structured data to the local LLM layer for producer-facing explanation and generation prompt text.
6. Node aggregates JSON, text, and generated asset paths.
7. JUCE renders results and exposes copy/export actions.

## 5. Auth model

No multi-user auth model exists yet. The expected MVP is local-only on the producer's machine. Security boundaries are local process trust, file access, localhost API access, and protecting user audio from unintended upload.

See `conventions/security.md` for local-first security rules.

## 6. External services

| Service | What it's used for | Where the secret lives |
|---|---|---|
| Local LLM runtime | Producer explanation and AI prompt generation | Local model/runtime config, no committed secrets |
| OpenAI/ChatGPT API | Historical README mentions ChatGPT; not the default because `promt.md` says local-first/no cloud dependency | If ever enabled, environment variable only |

## 7. Deploy topology

Initial deployment is local development:

- JUCE plugin built via Projucer/Xcode for macOS.
- Node backend launched locally.
- Python engine installed locally with pinned dependencies once introduced.
- Generated MIDI/results stay on the user's machine.

Packaging, auto-start behavior, installers, and CI are not defined yet.

## 8. Cross-component invariants

1. Core workflow must work locally; cloud calls cannot be required for the main path.
2. JUCE must never perform long-running analysis, network, process spawning, or disk-heavy work on the audio thread.
3. Python returns structured JSON; producer prose belongs in the LLM/Node layer, not the analysis core.
4. API contracts must be stable before the UI depends on them.
5. MIDI export paths must be local, explicit, and usable from Ableton.

## 9. Known architectural debt

| Area | Issue | Planned fix |
|---|---|---|
| JUCE plugin | Starter UI only; no backend communication or drag/drop yet | Build MVP UI/client around the local API contract. |
| Backend | Node orchestrator not implemented | Add local API with job queue and progress. |
| Analysis | Python modules not implemented | Start with Phase 1 BPM/key/energy JSON. |
| LLM | Local runtime/model not selected | Decide runtime before Phase 5. |
| Build/release | Packaging and plugin-format priorities unclear | Decide AU/VST3/standalone order before release work. |
