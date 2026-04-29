'use strict';

const fs = require('node:fs/promises');
const path = require('node:path');

// gemini-2.0-flash: generous free-tier quota, fast. Override via PROMPT2MIDI_GEMINI_MODEL.
const DEFAULT_MODEL = 'gemini-2.0-flash';
const GEMINI_TIMEOUT_MS = 20_000;

const SYSTEM_INSTRUCTION = `You are a music production expert writing a SUNO AI prompt.
You receive structured JSON describing a reference track analysis and a generated loop composition.
Write ONE flowing paragraph — not bullet points — that a producer can paste directly into SUNO.
Include all of: genre/subgenre, BPM, key/scale, groove feel, drum style, bass description, chord language, melody/arp description, arrangement arc, production and mix notes.
End with exactly: "Instrumental, no vocals. Inspired by the reference groove and production style, not a cover and not a copy."
Use producer-friendly language. Be specific and evocative, not generic.`;

async function generateSunoPrompt({ analysis, composition, exportDir, userPrompt = '' }) {
  if (process.env.PROMPT2MIDI_DISABLE_SUNO === '1') return null;

  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey || !composition) return null;

  const { GoogleGenerativeAI } = require('@google/generative-ai');
  const modelId = process.env.PROMPT2MIDI_GEMINI_MODEL || DEFAULT_MODEL;
  const model = new GoogleGenerativeAI(apiKey).getGenerativeModel({ model: modelId });

  const structured = {
    style: composition.style,
    bpm: composition.bpm,
    key: composition.key,
    bars: composition.bars,
    // Genre: use deep detection if confident, else BPM range
    genre: (analysis.genre_deep && analysis.genre_deep.confidence > 0.3)
      ? analysis.genre_deep
      : (analysis.genre || null),
    groove: analysis.groove || null,
    // Detected chord progression from reference (empty = not detected)
    detected_chords: (analysis.chords && analysis.chords.progression) || [],
    // Drum feel from reference stem analysis
    drum_feel: analysis.drums
      ? { tempo_feel: analysis.drums.tempo_feel, density: analysis.drums.density, swing: analysis.drums.swing }
      : null,
    // Track structure
    structure: analysis.structure
      ? { arrangement_arc: analysis.structure.arrangement_arc, energy_profile: analysis.structure.energy_profile, section_count: analysis.structure.section_count }
      : null,
    // Composition descriptions
    bass: (composition.description || {}).bass,
    drums: (composition.description || {}).drums,
    chords: (composition.description || {}).chords,
    melody: (composition.description || {}).melody,
    bpm_confidence: analysis.bpm_confidence,
    key_confidence: analysis.key_confidence,
    user_direction: userPrompt || null,
  };

  const prompt = [
    SYSTEM_INSTRUCTION,
    '',
    'Reference analysis:',
    JSON.stringify(structured, null, 2),
  ].join('\n');

  const timeout = new Promise((_, reject) =>
    setTimeout(() => reject(new Error('Gemini request timed out')), GEMINI_TIMEOUT_MS)
  );
  const result = await Promise.race([model.generateContent(prompt), timeout]);
  const text = result.response.text().trim();

  if (exportDir) {
    const promptPath = path.join(exportDir, 'prompt.txt');
    await fs.writeFile(promptPath, text, 'utf8');
    return { text, path: path.resolve(promptPath) };
  }

  return { text, path: null };
}

module.exports = { generateSunoPrompt };
