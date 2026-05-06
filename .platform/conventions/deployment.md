# Deployment / Release Conventions

Last updated: 2026-05-06

## Current state

No formal release pipeline exists. The current project is a JUCE `.jucer` with a Mac/Xcode exporter.

## Rules

- Use `develop` as the integration branch. Feature branches merge into `develop`; release merges go from `develop` into `main` and then get tagged.
- Document exact local build commands once the first working build path is confirmed.
- Keep plugin packaging separate from backend runtime packaging decisions.
- Before release, define whether AU, VST3, standalone, or all are required.
- Backend startup must be clear: either user-started, plugin-managed, or installer-managed.
- Rollback for early releases is manual: keep tagged builds and note compatible backend/Python versions.
- Full JUCE AU/VST integration and Ableton host QA are release blockers, not optional polish.

## Do not ship until

- Plugin loads in Ableton without crashes.
- Backend-down and analysis-failed states are graceful.
- Phase 1 analysis is verified on representative fixtures.
- Stem/MIDI evidence is labeled honestly and does not imply production-grade transcription.
- AU/VST import/export workflow is verified in a real DAW host.
- Local-first privacy behavior is documented.
