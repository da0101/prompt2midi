# Session Log

One line per completed task. Newest at the top. Append-only.

Format: `YYYY-MM-DD — <task> — <outcome> — <takeaway>`

---
- 2026-04-28 — commit `1f758bc`: Fix chord quality, register, and chord-following bass — auto-logged
- 2026-04-28 — commit `8948663`: Fix bass pitches being identical across runs — auto-logged
- 2026-04-28 — commit `c757dff`: Fix perceptually identical composition output across runs — auto-logged
- 2026-04-28 — commit `8262ca3`: Add style-aware randomised composition engine — auto-logged
- 2026-04-28 — commit `eb7ebdf`: Add deep analysis pipeline: genre (CLAP), chords, drums, structure — auto-logged
- 2026-04-28 — commit `82164e5`: Fix genre lying and prompt visibility — auto-logged
- 2026-04-28 — commit `23dcf16`: Switch default Gemini model to gemini-2.0-flash for better free-tier quota — auto-logged
- 2026-04-28 — commit `056400a`: Load .env via --env-file and add .env to .gitignore — auto-logged
- 2026-04-28 — Phase 7 acceptance run — 14/14 checks passed: librosa BPM/key, genre, groove, 5 MIDI files, summary.json, prompt.txt, Gemini fallback on 429 — product contract is complete
- 2026-04-28 — commit `87d5a56`: Fix all audit findings from Phase 1-5 review — auto-logged
- 2026-04-28 — analysis-ui-v1 Phase 3+5 — librosa BPM/key, genre heuristics, groove, composition progress stages, clean JUCE display — DISABLE_LIBROSA flag essential for test speed; install once per python3 version
- 2026-04-28 — commit `712b866`: Add Phase 3 analysis intelligence and Phase 5 UI pipeline stages — auto-logged
- 2026-04-28 — gemini-suno-prompt-v1 Phase 4 — Gemini 2.5 Pro SUNO prompt wired end-to-end, 10 tests pass — injectable pattern + DISABLE flag keeps CI clean without mocking the real API

---
- 2026-04-28 — commit `83bba7e`: Add Gemini 2.5 Pro SUNO prompt generation (Phase 4) — auto-logged
- 2026-04-28 — commit `72dad5d`: Register gemini-suno-prompt-v1 stream — auto-logged
- 2026-04-28 — commit `1449406`: Promote only recommended MIDI outputs — auto-logged
- 2026-04-28 — commit `4f76c6b`: Show live analysis pipeline progress — auto-logged

2026-04-28 — closed stream source-aware-transcription-v1 → ./.platform/work/archive/source-aware-transcription-v1.md (by danilulmashev)
- 2026-04-28 — commit `08eebd4`: Add stem-aware bass transcription — auto-logged
- 2026-04-28 — source-aware-transcription-v1 stem pass — added optional Demucs bass-stem separation feeding Basic Pitch and verified real MP3 output with `source-bass-transcription.mid` — stem-aware MIDI now exists locally but still needs musical QA by ear.
- 2026-04-28 — commit: Add visual pipeline logging — auto-logged
- 2026-04-28 — dev pipeline logging — added color-coded backend analysis stages with warnings, MIDI paths, note counts, and timings — `npm run dev:refresh` now shows what the pipeline is doing during manual QA.
- 2026-04-28 — commit: Add model-backed MIDI transcription — auto-logged
- 2026-04-29 — debug: low-percentage reference control degraded output — fixed root cause: 20% was parsed/mapped into loose text-guided generation instead of source-conditioned cover mode; low percentages now keep BPM/genre/key/style floor while varying bass notes, percussion accents, and effects.

- 2026-04-28 — source-aware-transcription-v1 model pass — added optional Basic Pitch setup/runner, structured MIDI assets, low-confidence wording guards, and real MP3 smoke output — model MIDI is now available locally, but stem separation remains future work.
- 2026-04-28 — commit: Close audio intelligence stream — auto-logged

2026-04-28 — closed stream audio-intelligence-v1 → ./.platform/work/archive/audio-intelligence-v1.md (by danilulmashev)
- 2026-04-28 — commit `843c3dc`: Add experimental bass transcription — auto-logged
- 2026-04-28 — audio-intelligence-v1 bass transcription — added experimental monophonic low-frequency tracking and `bass-transcription.mid` output — better than the old sketch, but still not source-separated transcription.
- 2026-04-28 — commit `ecb4501`: Implement audio intelligence v1 — auto-logged
- 2026-04-28 — audio-intelligence-v1 implementation — added FFmpeg MP3 boundary decoding, confidence metadata, and honest `reference-sketch.mid` labeling — generated MIDI is now explicitly framed as a sketch, not transcription.
- 2026-04-28 — commit `1aaa4c4`: Checkpoint audio intelligence stream — auto-logged
- 2026-04-28 — commit `5344af4`: Start audio intelligence stream — auto-logged
- 2026-04-28 — commit `20196f5`: Close vertical slice stream — auto-logged

2026-04-28 — closed stream vertical-slice-mvp → ./.platform/work/archive/vertical-slice-mvp.md (by danilulmashev)
- 2026-04-28 — commit `76d9b06`: Implement vertical slice MVP — auto-logged
- 2026-04-28 — vertical-slice-mvp implementation — added local Node API, Python WAV analyzer/MIDI writer, and async JUCE client — backend/Python tests pass; JUCE Debug shared build passes after Projucer regeneration
- 2026-04-28 — commit `d2de237`: Activate Agentboard project context — auto-logged

2026-04-28 — Activated project from execution plan — filled context pack for JUCE + Node + Python + local LLM architecture — `promt.md` is the source of truth and the current code is a JUCE starter shell
2026-04-28 — Initialized project with ab — created .platform/ context pack — workflow, conventions, and templates are in place; next task is to fill STATUS.md and architecture.md
2026-04-28 — composition engine randomisation + CLAP threshold fix — committed — rng per call + 5 style patterns; CLAP threshold 0.3→0.12
2026-04-30 — debug: similarity levels collapsed in ACE pipeline — fixed root cause: named levels all mapped to compressed cover-mode conditioning; low now uses text2music style conditioning, medium/high/near-identical use wider ACE source strengths, and prompts preserve micro-percussion/vocal-chop roles.
