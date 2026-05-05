'use strict';

const fs = require('node:fs/promises');
const path = require('node:path');

const DEFAULT_MODEL = 'gemini-2.0-flash';
const GEMINI_TIMEOUT_MS = 25_000;

const SYSTEM_INSTRUCTION = `You are a senior electronic music producer helping an audio generation pipeline.
You receive structured analysis from a reference track and a user's creative direction.
Return STRICT JSON only. Do not use markdown.
Your job is to write a concise ACE-Step generation brief that helps the model preserve the reference style, groove, energy, and arrangement role while creating original music.
Be specific about drums, bass, percussion, hook role, effects, timbre, and requested added layers.
Never ask to copy an artist, singer, recording, hook, lyric, or exact melody.
Prefer stable club-ready musical language over vague mood words.
If experimental control is allowed, suggest only conservative ACE controls.`;

async function generateAceBrief({
  analysis,
  userPrompt = '',
  similarityLevel = '',
  duration = null,
  referenceStart = null,
  vocals = true,
  controls = {},
  allowControl = false,
  outputDir = '',
}) {
  if (process.env.PROMPT2MIDI_DISABLE_GEMINI === '1') {
    return { status: 'disabled', reason: 'PROMPT2MIDI_DISABLE_GEMINI=1' };
  }
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    return { status: 'disabled', reason: 'GEMINI_API_KEY is not set' };
  }

  const { GoogleGenerativeAI } = require('@google/generative-ai');
  const modelId = process.env.PROMPT2MIDI_GEMINI_MODEL || DEFAULT_MODEL;
  const model = new GoogleGenerativeAI(apiKey).getGenerativeModel({ model: modelId });

  const structured = {
    user_direction: userPrompt || null,
    similarity_level: similarityLevel || null,
    duration_seconds: duration,
    reference_start_seconds: referenceStart,
    vocals_or_hook_role_enabled: Boolean(vocals),
    current_controls: controls,
    reference: compactAnalysis(analysis || {}),
    control_mode: allowControl
      ? 'experimental: you may suggest conservative reference_strength, cover_noise_strength, and similarity_level'
      : 'brief only: do not suggest controls',
    output_schema: {
      ace_prompt_addition: 'string, 1 concise paragraph, max 900 chars',
      rationale: 'string, max 300 chars',
      requested_layers: ['string'],
      warnings: ['string'],
      ace_controls: allowControl
        ? {
            reference_strength: 'optional number 0.24-0.42',
            cover_noise_strength: 'optional number 0.08-0.20',
            similarity_level: 'optional one of low, medium-low, medium, medium-high, high, near-identical',
            reason: 'string',
          }
        : null,
    },
  };

  const prompt = [
    SYSTEM_INSTRUCTION,
    '',
    'Reference analysis and user request:',
    JSON.stringify(structured, null, 2),
  ].join('\n');

  const timeout = new Promise((_, reject) =>
    setTimeout(() => reject(new Error('Gemini ACE brief request timed out')), GEMINI_TIMEOUT_MS)
  );
  const result = await Promise.race([model.generateContent(prompt), timeout]);
  const text = result.response.text().trim();
  const parsed = parseJsonObject(text);
  const normalized = normalizeBrief(parsed, { allowControl });
  const payload = {
    status: 'succeeded',
    provider: 'gemini',
    model: modelId,
    ...normalized,
  };

  if (outputDir) {
    await fs.mkdir(outputDir, { recursive: true });
    const file = path.join(outputDir, 'gemini-ace-brief.json');
    await fs.writeFile(file, JSON.stringify(payload, null, 2) + '\n', 'utf8');
    payload.path = path.resolve(file);
  }
  return payload;
}

function compactAnalysis(analysis) {
  const transform = analysis.reference_transform || {};
  const preflight = analysis.ace_preflight || {};
  return {
    bpm: analysis.bpm,
    bpm_confidence: analysis.bpm_confidence,
    key: analysis.key,
    key_confidence: analysis.key_confidence,
    genre: analysis.genre || null,
    groove: analysis.groove || null,
    chords: compactChords(analysis.chords || {}),
    vocals: analysis.vocals || null,
    drums: analysis.drums || null,
    structure: compactStructure(analysis.structure || {}),
    production_descriptors: analysis.production_descriptors || null,
    reference_transform: {
      style_brief: transform.style_brief,
      groove_similarity: transform.groove_similarity,
      difference_level: transform.difference_level,
      bass: transform.bass,
      vocals: transform.vocals,
      harmonic: transform.harmonic,
      reference_character: transform.reference_character,
    },
    ace_preflight: {
      ace_suitability: preflight.ace_suitability,
      recommended_generator: preflight.recommended_generator,
      risk_reasons: preflight.risk_reasons,
      strengths: preflight.strengths,
      hidden_controls: preflight.hidden_controls,
    },
  };
}

function compactChords(chords) {
  return {
    method: chords.method,
    confidence: chords.confidence,
    progression: Array.isArray(chords.progression) ? chords.progression.slice(0, 24) : [],
  };
}

function compactStructure(structure) {
  return {
    method: structure.method,
    section_count: structure.section_count,
    arrangement_arc: structure.arrangement_arc,
    energy_profile: structure.energy_profile,
    sections: Array.isArray(structure.sections) ? structure.sections.slice(0, 12) : [],
  };
}

function parseJsonObject(text) {
  const cleaned = text
    .replace(/^```(?:json)?/i, '')
    .replace(/```$/i, '')
    .trim();
  try {
    return JSON.parse(cleaned);
  } catch (_) {
    const match = cleaned.match(/\{[\s\S]*\}/);
    if (!match) throw new Error(`Gemini did not return JSON: ${text.slice(0, 200)}`);
    return JSON.parse(match[0]);
  }
}

function normalizeBrief(parsed, { allowControl }) {
  const acePrompt = String(parsed.ace_prompt_addition || '').replace(/\s+/g, ' ').trim();
  if (!acePrompt) throw new Error('Gemini response was missing ace_prompt_addition');
  const payload = {
    ace_prompt_addition: acePrompt.slice(0, 1000),
    rationale: String(parsed.rationale || '').replace(/\s+/g, ' ').trim().slice(0, 500),
    requested_layers: Array.isArray(parsed.requested_layers) ? parsed.requested_layers.map(String).slice(0, 12) : [],
    warnings: Array.isArray(parsed.warnings) ? parsed.warnings.map(String).slice(0, 12) : [],
  };
  if (allowControl) payload.ace_controls = normalizeControls(parsed.ace_controls || {});
  return payload;
}

function normalizeControls(raw) {
  const controls = {};
  const reference = Number.parseFloat(raw.reference_strength);
  const noise = Number.parseFloat(raw.cover_noise_strength);
  if (Number.isFinite(reference)) controls.reference_strength = clamp(reference, 0.24, 0.42);
  if (Number.isFinite(noise)) controls.cover_noise_strength = clamp(noise, 0.08, 0.20);
  const level = String(raw.similarity_level || '').trim();
  if (['low', 'medium-low', 'medium', 'medium-high', 'high', 'near-identical'].includes(level)) {
    controls.similarity_level = level;
  }
  if (raw.reason) controls.reason = String(raw.reason).replace(/\s+/g, ' ').trim().slice(0, 400);
  return controls;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

module.exports = { generateAceBrief };
