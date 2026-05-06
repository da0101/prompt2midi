# QA Conventions

Last updated: 2026-04-28

## Scope

Manual verification for the producer workflow and plugin UX.

## QA checklist

- Plugin opens in Ableton.
- UI remains responsive while a job is queued/running.
- Analyze flow reports progress and final state.
- Backend unavailable state is understandable.
- Results show BPM/key/energy/prompt fields clearly.
- Copy prompt works.
- MIDI export creates files Ableton can import.
- Re-analyze works without restarting Ableton.

## UX rules

- Use producer language, not implementation language.
- Progress and failure states are mandatory for long-running operations.
- Avoid clutter: advanced analysis should be scannable by category.
