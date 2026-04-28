# Testing Conventions

Last updated: 2026-04-28

## Scope

Applies across JUCE, Node, Python, and integration behavior.

## Minimum bar by area

- JUCE UI/client: verify no blocking calls in audio-thread paths and test backend-down UI states manually.
- Node API: unit test request validation, job state transitions, structured errors, and result aggregation.
- Python analysis: fixture-based tests for BPM/key/energy output with deterministic tolerances.
- LLM prompting: snapshot or schema tests for deterministic prompt structure using fixed analysis JSON.
- Integration: one vertical slice from plugin/client request to local result JSON before expanding feature depth.

## Fixture rules

- Do not commit copyrighted commercial tracks.
- Use generated, public-domain, or synthetic short audio fixtures.
- Keep fixtures small enough for normal repo operations.
