# prompt2midi — Repos & Specialist Routing

Last updated: 2026-04-28

---

## Repos

| Repo ID | Path | Role / stack hint | Deep reference |
|---|---|---|---|
| prompt2midi | `.` | JUCE/C++ plugin now; planned Node + Python local backend in same repo unless split later | `architecture.md` |

This is currently a single-repo project. If Node or Python become sibling repos later, add them here and update `.platform/scripts/sync-context.sh`.

## Conventions — which file governs which area

| Area you're touching | Read first |
|---|---|
| JUCE plugin/audio-thread code | `conventions/cpp-juce.md` |
| Node API/orchestration | `conventions/nodejs.md` + `conventions/api.md` |
| Python analysis/MIDI extraction | `conventions/python-audio.md` |
| Local-first security/secrets/audio files | `conventions/security.md` |
| Tests | `conventions/testing.md` |
| Build/release/rollback | `conventions/deployment.md` |
| Plugin UX/manual QA | `conventions/qa.md` |
| Product scope/user value | `conventions/pm.md` |

## Specialist routing

| When you touch... | Use skill |
|---|---|
| Product scope, milestones, MVP tradeoffs | `ab-pm` |
| Cross-component design | `ab-architect` |
| JUCE/plugin or backend implementation | `ab-workflow` |
| Test strategy or fixtures | `ab-test-writer` |
| Pre-PR review | `ab-review` |
| Bug investigation | `ab-debug` |
| Local-first/privacy/security checks | `ab-security` |
| Manual Ableton/plugin QA | `ab-qa` |

## Hard repo rules carried over from the platform

1. Max ~300 lines per file unless a generated file or JUCE/Xcode output makes that impractical.
2. No secrets in code, logs, prompts, fixtures, or committed files.
3. Keep user audio local unless the user explicitly opts into a cloud integration.
4. API response shape must match `conventions/api.md` before UI code depends on it.
5. New analysis behavior needs at least one representative fixture or deterministic test.
