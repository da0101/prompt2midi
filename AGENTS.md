<!-- agentboard:root-entry:begin v=1 -->
# prompt2midi

**What this is:** A local-first AI co-producer for Ableton Live. It combines prompt-to-MIDI generation and full audio-track analysis so producers can turn reference tracks or ideas into BPM/key/structure insights, MIDI assets, and AI-ready music prompts.

## Stack

JUCE/C++ plugin shell now; planned local Node.js orchestrator, Python audio-analysis engine, and local LLM interpretation layer. macOS/Ableton is the first practical target through the existing JUCE/Xcode setup.

## Repo Structure

Single repo for now:

| Area | Path | Purpose |
|---|---|---|
| Product plan | `promt.md` | Exact execution plan and source of truth |
| JUCE project | `prompt2midi.jucer` | Projucer/JUCE project definition |
| Plugin source | `Source/` | Processor/editor C++ code |
| Mac exporter | `Builds/MacOSX/` | Generated Xcode project and plist files |
| Shared memory | `.platform/` | Agentboard context, domains, decisions, workflow |

## How This Project Actually Works

- `promt.md` is the execution plan unless the owner changes it.
- The current code is a JUCE starter plugin: processor pass-through plus a prompt box and Generate button.
- Intended architecture is JUCE UI/client -> local Node API/job queue -> Python analysis -> local LLM -> JUCE result/export UI.
- Core workflow must run locally. Cloud APIs may be optional later, but cannot be required.
- Never put long-running work, network calls, subprocesses, or file-heavy analysis in JUCE `processBlock`.

## Workflow

At session start, run `ab brief`, then read `.platform/work/BRIEF.md` and `.platform/work/ACTIVE.md`. If a stream exists, use `ab handoff <slug>` before touching code.

For non-trivial work, follow `.platform/workflow.md`: triage, research, plan, execute, verify, record/handoff.

Before ending a meaningful session, checkpoint the active stream:

```bash
ab checkpoint <stream-slug> --what "<what changed>" --next "<next action>" --provider <provider>
```

## Reference Pack (.platform/)

- `.platform/work/BRIEF.md` — current project orientation
- `.platform/STATUS.md` — feature status and priorities
- `.platform/architecture.md` — end-to-end architecture and invariants
- `.platform/repos.md` — repo routing and conventions map
- `.platform/memory/decisions.md` — locked decisions
- `.platform/memory/log.md` — chronological work log
- `.platform/domains/juce-plugin.md` — plugin/UI/client domain
- `.platform/domains/audio-analysis.md` — Python analysis and MIDI extraction domain
- `.platform/domains/local-orchestration.md` — Node job/API orchestration domain
- `.platform/domains/llm-midi-generation.md` — LLM prompt/MIDI output domain
- `.platform/conventions/` — stack, API, testing, security, QA, deployment, PM rules

## Hard Constraints (Don't Break These)

1. `promt.md` is the exact plan and must guide implementation.
2. Build both prompt-to-MIDI and audio-track analysis; do not collapse the product to only one.
3. Local-first is mandatory for the core workflow.
4. JUCE must stay responsive inside Ableton and must not block the audio thread.
5. Python returns structured analysis JSON; Node owns orchestration and aggregation.
6. Use producer-friendly UX language, not backend or ML jargon.

## Current State

Activation is complete. Implementation streams have not started yet. The first recommended stream is a vertical-slice MVP: plugin/client request -> local job -> Phase 1 Python analysis JSON -> producer prompt/result display.
<!-- agentboard:root-entry:end v=1 -->
