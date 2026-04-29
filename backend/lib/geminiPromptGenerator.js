'use strict';

const fs = require('node:fs');
const path = require('node:path');

const DEFAULT_MODEL = 'gemini-2.5-pro';

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

  const result = await model.generateContent(prompt);
  const text = result.response.text().trim();

  if (exportDir) {
    const promptPath = path.join(exportDir, 'prompt.txt');
    fs.writeFileSync(promptPath, text, 'utf8');
    return { text, path: path.resolve(promptPath) };
  }

  return { text, path: null };
}

module.exports = { generateSunoPrompt };
