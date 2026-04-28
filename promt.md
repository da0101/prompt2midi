# 🧠 FULL SYSTEM PROMPT FOR CODEX

## Project: Local AI Music Analysis & Generation Assistant (Ableton + JUCE + Python + LLM)

---

## 🎯 OBJECTIVE

You are tasked with designing and implementing a **local-first AI-powered music analysis and generation assistant** that integrates with Ableton Live via a JUCE plugin.

This system must:

1. Analyze full audio tracks (WAV/MP3)
2. Extract detailed musical intelligence (BPM, key, chords, structure, instrumentation, groove)
3. Convert that analysis into:

   * Human-readable producer insights
   * Structured machine-readable data
   * MIDI components (bassline, melody if possible)
   * High-quality prompts for AI music generators (e.g. Suno-style prompting)
4. Provide a seamless UX inside Ableton via a JUCE plugin

---

## 🧭 PRODUCT VISION

This is not just an analysis tool.

This is:

> A **personal AI co-producer** that translates music into structured production knowledge.

Users should be able to:

* Drop a track they like
* Instantly understand how it works
* Reuse its structure, groove, and style
* Generate new tracks in similar style using AI tools

---

## 👤 USER EXPERIENCE (CRITICAL)

### User Flow

1. User opens Ableton Live
2. Loads JUCE plugin
3. Drags & drops a track into plugin
4. Clicks "Analyze"

System:

* Shows progress (real-time)
* Processes track in background

Output displayed in UI:

* BPM, key, scale
* Genre + style description
* Track structure (timeline)
* Instrument breakdown
* Chord progression
* Energy curve
* MIDI export buttons
* "Generate AI Prompt" button

---

### Expected UX Principles

* Zero friction (drag & drop)
* Fast feedback (progress updates)
* Clear visual hierarchy
* Producer-friendly terminology
* No technical jargon exposed to user

---

## 🏗️ SYSTEM ARCHITECTURE

### High-Level Components

1. **JUCE Plugin (C++)**

   * UI layer only
   * Runs inside Ableton
   * Communicates with backend

2. **Node.js Orchestrator**

   * API gateway
   * Job queue manager
   * LLM interaction layer
   * Data formatting

3. **Python Analysis Engine**

   * Audio processing core
   * Feature extraction
   * Signal analysis
   * MIDI extraction

4. **Local LLM Layer**

   * Converts structured data → human insights
   * Generates prompts

---

## 🔄 END-TO-END DATA FLOW

1. JUCE sends audio file path → Node API
2. Node queues job
3. Node triggers Python analysis
4. Python returns structured JSON
5. Node sends JSON → LLM
6. LLM returns:

   * Description
   * Prompt
7. Node aggregates response
8. JUCE receives and displays results

---

## 🧩 IMPLEMENTATION PHASES

---

# 🟢 PHASE 1 — CORE ANALYSIS (FOUNDATION)

### Goal:

Deliver basic but useful analysis

### Python Responsibilities:

* Extract BPM
* Detect key
* Compute spectral features
* Basic energy profile

### Output:

```json
{
  "bpm": number,
  "key": "string",
  "energy_curve": [],
  "loudness": number
}
```

### Value:

* Immediate usefulness
* Foundation for all advanced features

---

# 🟡 PHASE 2 — STRUCTURAL INTELLIGENCE

### Goal:

Understand track arrangement

### Features:

* Section segmentation (intro, drop, breakdown, outro)
* Energy-based transitions

### Techniques:

* Self-similarity matrices
* Clustering

### Output:

```json
{
  "sections": [
    { "type": "intro", "start": 0, "end": 30 },
    { "type": "drop", "start": 30, "end": 90 }
  ]
}
```

### Value:

* Enables reconstruction of arrangement
* Essential for production learning

---

# 🟠 PHASE 3 — INSTRUMENT & STEM ANALYSIS

### Goal:

Break track into components

### Features:

* Stem separation (drums, bass, harmonic)
* Instrument classification

### Output:

```json
{
  "instruments": {
    "drums": "4/4 kick-heavy groove",
    "bass": "rolling sub bass",
    "pads": "dark atmospheric"
  }
}
```

### Value:

* Helps users recreate tracks in DAW
* Bridges gap between listening and producing

---

# 🔵 PHASE 4 — HARMONIC & MIDI EXTRACTION

### Goal:

Make music reusable

### Features:

* Chord progression detection
* Melody extraction (if possible)
* MIDI export

### Output:

```json
{
  "chords": ["Am", "F", "C", "G"],
  "midi_files": {
    "bass": "path.mid",
    "melody": "path.mid"
  }
}
```

### Value:

* Direct integration into Ableton workflow
* Massive practical value

---

# 🟣 PHASE 5 — LLM INTERPRETATION LAYER

### Goal:

Turn data into intelligence

### Input:

Structured JSON from Python

### Output:

1. Producer-style explanation
2. Genre/style breakdown
3. AI generation prompt

### Example Prompt Output:

"A dark, groovy tech house track at 125 BPM in F minor, featuring a rolling bassline, punchy 4/4 drums..."

### Value:

* Bridges technical → creative
* Improves AI generation dramatically

---

# 🔴 PHASE 6 — JUCE UI INTEGRATION

### UI Components:

* Waveform display
* Section markers
* BPM / key panel
* Instrument tags
* Export buttons

### Features:

* Copy prompt
* Export MIDI
* Re-analyze

---

## ⚙️ ENGINEERING REQUIREMENTS

### Node.js Layer

* REST API:

  * POST /analyze
  * GET /status
  * GET /result

* WebSocket:

  * Progress updates

* Queue system:

  * Handle long-running jobs

---

### Python Layer

* Modular design:

  * feature_extraction.py
  * segmentation.py
  * midi_extraction.py

* Return structured JSON only

---

### JUCE Plugin

* Async communication
* Non-blocking UI
* Local file handling

---

## 🧠 LLM PROMPT ENGINEERING

Codex must design prompts that:

* Are deterministic
* Avoid vague descriptions
* Use structured inputs
* Produce consistent outputs

---

## 🔍 RESEARCH REQUIREMENTS

Before implementation:

1. Analyze existing tools:

   * Music analysis software
   * AI music generators
   * DAW plugins

2. Identify:

   * Strengths
   * Weaknesses
   * Missing features

3. Validate:

   * Feasibility of each phase
   * Performance constraints
   * Local processing limits

---

## 📊 PRODUCT MANAGEMENT CONSIDERATIONS

### MVP Definition:

* BPM
* Key
* Basic prompt generation

### Success Metrics:

* Accuracy of BPM/key
* Quality of generated prompts
* User ability to recreate style

---

## ⚠️ CONSTRAINTS

* Must run locally
* Must not rely on cloud APIs
* Must be modular and extensible
* Must handle large audio files

---

## 🚀 FINAL DELIVERABLE

A fully working system where:

User drops a track →
System analyzes it →
User receives:

* Technical breakdown
* MIDI assets
* AI-ready prompt
  → Uses it to generate a similar track

---

## 🧠 FINAL NOTE TO CODEX

Do not treat this as a simple coding task.

This is:

* A system design problem
* A product design problem
* A UX problem
* An AI pipeline problem

You must:

* Validate each component
* Choose best tools
* Optimize for performance
* Ensure scalability

Focus on building a **real producer tool**, not a demo.

---
