# Session Log

One line per completed task. Newest at the top. Append-only.

Format: `YYYY-MM-DD — <task> — <outcome> — <takeaway>`

---
- 2026-05-05 — commit `9609c41`: Record ACE UI pipeline commit — auto-logged
- 2026-05-05 — commit `93cad39`: Add ACE inspired loop UI and proxy pipeline — auto-logged
- 2026-05-03 — implementation: optional Gemini ACE brief lane — added Gemini smart-brief and experimental-control flags to the ACE proxy runner/UI; Gemini now pre-analyzes locally, writes `gemini-ace-brief.json`, appends a producer brief to ACE prompts, and can conservatively suggest ACE slider-equivalent controls when explicitly enabled.
- 2026-05-03 — debug: explicit added layers ignored by ACE prompt — fixed root cause: UI prompt text was passed but not promoted into the ACE caption as hard audible layers; cowbell and vocal-chop requests now become explicit high-priority caption controls.
- 2026-05-01 — commit `6e1faf3`: updqte — auto-logged
- 2026-05-01 — commit `ac6f6da`: update — auto-logged
- 2026-04-30 — debug: Tiga LOW vocal/electro-house failure — added stem-aware vocal role detection, vocal-hook ACE payloads, and electronic-house style override; 15s Tiga v2 generated 4 candidates with `instrumental=false`, but all failed the automatic quality/timbre gate, so vocal references still need ACE/backend quality tuning.
- 2026-04-30 — fast sample calibration lane — added `--fast-sample` / `npm run sample:fast` to skip stems, Basic Pitch, MIDI, composition, and full-arrangement work while preserving BPM/key/genre/structure analysis and ACE profile controls; smoke test passes without ACE enabled.
- 2026-04-30 — Tiga fast LOW v2 30s — generated 4 candidates in one ACE batch at `tmp/tiga-fast-low-v2-30s/exports`; candidate 1 passed LOW gate (`score=0.753`, `timbre=0.696`), candidates 2-4 failed noisy/timbre gates; runtime was about 11 minutes cold-start, now dominated by ACE render rather than analysis.
- 2026-04-30 — commit `c3bfb05`: update — auto-logged
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
2026-04-30 — debug: low similarity accepted weak-groove candidates — fixed root cause: candidate quality ranking treated generic timbre/score as enough even when club pulse was weak; low/medium-low ACE outputs now get a level quality gate and sweep summaries expose pass/fail.
2026-04-30 — debug: low similarity still generated alien/robotic audio — fixed root cause: low ACE conditioning was under-anchored (`audio_cover_strength=0.16`) so the model could leave the house/music manifold; low now uses a stronger musical reference floor with high composition variation.
2026-04-30 — debug: low similarity became too close after musicality retune — user accepted v6 musicality but said it belonged around medium/medium-low and leaked original bass/stab identity; low now uses style/energy anchoring with lower cover strength/noise (`0.21`/`0.11`), lower target similarity (`0.24`), and stronger no-original-motif prompt language.
2026-04-30 — debug: LOW Tiga output had occasional off-scale/weird notes — added harmonic guard propagation into reference transform, model prompt, ACE caption, and ACE negative prompt; Tiga LOW harmonic v3 wrote 4 candidates to `tmp/tiga-fast-low-v3-harmonic-30s/exports`, with candidate 1 passing the LOW quality gate.
2026-04-30 — calibration: tried a midpoint between Tiga LOW v2 and v3 — added generic reference-character extraction from energy/loudness/groove/vocal analysis and softened harmonic wording; v4 batch wrote to `tmp/tiga-fast-low-v4-balanced-30s/exports` but all four candidates failed the LOW quality gate, so v4 should be auditioned cautiously and not treated as an improvement until user confirms.
2026-04-30 — calibration: Smooth Criminal LOW fast test — generated 4 candidates in `tmp/smooth-criminal-fast-low-v1-30s/exports`; analyzer classified the reference section as breakbeat/classic rock/indie rock, 120 BPM, F Major, with a lead-vocal-hook role; all candidates failed the current LOW quality gate, with candidate 3 suggested for audition by score.
2026-04-30 — debug: rich vocal/melodic references produced weird chops and stretched transitions — fixed root causes: LOW prompt had house-specific/contradictory wording, near-zero CLAP genre labels overrode stable BPM-range genre, and negative phrases like "no lead vocal resynthesis" were parsed as direct vocal requests. Added rich-reference safety, instrumental hook-proxy mode, and reduced ACE source strength/noise for unreliable low-similarity vocal references. Generated corrected Smooth Criminal LOW v3 in `tmp/smooth-criminal-fast-low-v3-instrumental-proxy-30s/exports`; candidate 3 is suggested, all candidates still fail the strict numeric quality gate.
2026-04-30 — debug: Smooth Criminal LOW v3 regressed into muffled/random/no-structure output — fixed root cause: rich-reference safety removed too much source structure and treated the track like a late instrumental proxy. LOW rich harmonic references now use an earlier character window plus stronger structure anchoring (`audio_cover_strength=0.26`, `cover_noise_strength=0.11`) while still blocking lead-vocal resynthesis. Generated v4 in `tmp/smooth-criminal-fast-low-v4-structure-anchor-20s/exports`; candidate 2 is suggested and is the only candidate passing the LOW quality gate.
2026-04-30 — debug: Smooth Criminal LOW v5 still produced nonsense — confirmed previous fix targeted the wrong layer: dense melodic/vocal references should not use ACE cover/source-audio conditioning at LOW. Rich LOW references now switch to analysis-text-only `text2music` with no reference/src audio upload. Generated v6 in `tmp/smooth-criminal-fast-low-v6-text-lane-15s/exports`; all candidates failed the quality gate, confirming the remaining blocker is inadequate rich-reference analysis/prompting or ACE model capability for this style, not just cover-mode artifacting.
2026-04-30 — implementation: structured local sample renderer — added `analysis/structured_render.py` and `npm run sample:structured` to render full WAV guide candidates inside the pipeline without Ableton/ACE; generated Smooth Criminal LOW v1 in `tmp/smooth-criminal-structured-low-v1-30s/exports`; fixed slow long-WAV loading and an infinite low-similarity kick-variation loop.
2026-05-01 — debug: MJ bass-proxy scaffold sounded chaotic — fixed root cause handling: generated bass scaffolds are not real bass transcriptions and contaminate ACE conditioning on rich/vocal references; bass-proxy route is now diagnostic-only, skipped for rich/vocal references unless explicitly forced, and internal scaffold files are labeled as non-listenable control signals.
2026-05-03 — implementation: optional Gemini ACE brief lane — added Gemini producer-brief generation from fast local analysis plus user direction, wired `--gemini-brief` and experimental `--gemini-control` into the ACE proxy runner/UI, and made UI scripts load `.env` so `GEMINI_API_KEY` is available at runtime.
2026-05-03 — fix: ACE proxy UI progress visibility — preserved machine-readable child `progress:` events for UI-launched runs, added explicit reference/Gemini/ACE/package milestones, kept longer per-run trace logs with UUID/output-dir events, and rebuilt the Vue UI.
2026-05-04 — fix: Gemini UI checkbox submission — backend now accepts normal checkbox truthy values (`on`, `checked`, `1`, `true`) and the Vue form normalizes checkbox updates before submit, preventing visually checked Gemini controls from being omitted from the runner command.
2026-05-04 — debug: stale ACE proxy UI server — found old `node scripts/ace-proxy-ui.js` and duplicate Vite processes still serving port 47322, killed them, removed nodemon from UI scripts to avoid EMFILE watcher failures, and added `/api/health`/run trace fields with backend pid/start time/Gemini-key presence.
2026-05-04 — fix: ACE proxy UI offline feedback — after killing all servers, the cached Vue page silently ignored Browse/Start/Restart clicks because the API was offline; added visible toasts/status messages for unreachable API calls and relaunched clean web UI/API.
