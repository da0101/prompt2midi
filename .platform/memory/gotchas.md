# Gotchas

_Landmines found in this codebase. Each line = one thing a fresh agent should know before touching the related area. Appended automatically during `ab close <slug>` harvest._

**Severity tiers** (use the emoji prefix):
- 🔴 **never-forget** — breaks prod, loses data, or wastes hours. Always surfaced in `ab brief`.
- 🟡 **usually-matters** — trips up most new work in the area. Surfaced when relevant domains are active.
- 🟢 **minor** — worth mentioning, not worth interrupting flow.

Format: `🔴 [domain or file] — one-line gotcha (incident date if applicable)`

---

## Entries

<!-- agentboard:gotchas:begin -->
<!-- New entries go below, newest first. Keep entries to one line each. -->
- 🟡 [audio-analysis] — Basic Pitch on macOS/CoreML needs `TMPDIR` pointed at a writable project temp dir; sandboxed `/var/folders/.../T` can fail model compilation (2026-04-28).
- 🟡 [audio-analysis] — `model-bass-transcription.mid` is pitch-filtered model output from the full mix, not stem-separated bass (2026-04-28).
- 🟡 [audio-analysis] — `bass-transcription.mid` is experimental monophonic low-frequency tracking from the full mix, not source-separated or production-grade transcription (2026-04-28).
- 🟡 [local-orchestration] — MP3 support depends on FFmpeg being on `PATH` or `PROMPT2MIDI_FFMPEG`; Python still receives WAV (2026-04-28).
- 🟡 [llm-midi-generation] — `bassline.mid` in the MVP is a deterministic placeholder root pattern, not real track transcription (2026-04-28).
- 🟡 [audio-analysis] — Phase 1 accepts uncompressed PCM WAV only; MP3 needs an explicit decoder dependency decision before UI/backend support (2026-04-28).
<!-- agentboard:gotchas:end -->
