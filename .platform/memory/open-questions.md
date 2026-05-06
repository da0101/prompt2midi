# Open questions

_Live hypotheses and unresolved questions. Appended during `ab close <slug>` when a stream surfaced something that couldn't be answered. Moved to Resolved when a later stream answers them._

---

## Active

<!-- agentboard:open-questions:active:begin -->
<!-- Format: `- YYYY-MM-DD — [domain] question (context)` -->
- 2026-04-28 — [llm-midi-generation] Which local LLM runtime/model should replace the deterministic MVP prompt generator first?
- 2026-04-28 — [local-orchestration] Should cloud deployment keep Node as the orchestration gateway or introduce FastAPI as the public API layer?
<!-- agentboard:open-questions:active:end -->

## Resolved

<!-- agentboard:open-questions:resolved:begin -->
<!-- Format: `- YYYY-MM-DD — [domain] question → answer (stream: <slug>)` -->
- 2026-04-28 — [audio-analysis] Which source-aware transcription approach should replace heuristic full-mix bass tracking first? → Use optional Basic Pitch for first-pass local model MIDI, while keeping stem-aware separation as a later decision. (stream: source-aware-transcription-v1)
- 2026-04-28 — [audio-analysis] Which MP3/audio decoder dependency should be adopted for Phase 2 import support? → Use FFmpeg as the backend boundary adapter and keep Python analysis WAV-only. (stream: audio-intelligence-v1)
<!-- agentboard:open-questions:resolved:end -->
