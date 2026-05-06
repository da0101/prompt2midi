function buildPromptPackage({ prompt = '', analysis }) {
  const bpm = analysis.bpm || 120;
  const key = analysis.key || 'C major';
  const bpmConfidenceValue = Number(analysis.bpm_confidence) || 0;
  const keyConfidenceValue = Number(analysis.key_confidence) || 0;
  const bpmConfidence = confidencePhrase(bpmConfidenceValue);
  const keyConfidence = confidencePhrase(keyConfidenceValue);
  const hasReliableBpm = bpmConfidenceValue >= 0.55;
  const hasReliableKey = keyConfidenceValue >= 0.55;
  const energy = summarizeEnergy(analysis.energy_curve || []);
  const userIntent = prompt.trim() || 'reference-track inspired production';
  const modelReady = analysis.model_transcription && analysis.model_transcription.available;

  const styleTags = inferStyleTags(userIntent, energy);
  const tempoPhrase = hasReliableBpm ? `${Math.round(bpm)} BPM` : `around ${Math.round(bpm)} BPM, tempo unverified`;
  const keyPhrase = hasReliableKey ? `in ${key}` : 'with key left flexible';
  const aiPrompt = [
    `${styleTags.join(', ')} track at ${tempoPhrase} ${keyPhrase}`,
    `with ${energy.phrase}`,
    'tight arrangement, producer-ready mix direction, and clear instrumental layers',
    userIntent
  ].filter(Boolean).join(', ');

  return {
    producer_summary: [
      hasReliableBpm ? `Tempo: ${Math.round(bpm)} BPM (${bpmConfidence}).` : `Possible tempo: around ${Math.round(bpm)} BPM, but confidence is ${bpmConfidence}.`,
      hasReliableKey ? `Key: ${key} (${keyConfidence}).` : `Possible tonal center: ${key}, but confidence is ${keyConfidence}.`,
      `The energy profile ${energy.summary}.`,
      modelReady
        ? 'Model MIDI transcription is available; audition it and correct by ear.'
        : 'Model transcription is not available, so MIDI output is limited to generated or heuristic sketches.'
    ].join(' '),
    style_tags: styleTags,
    ai_music_prompt: aiPrompt,
    next_steps: [
      modelReady ? 'Audition the model MIDI first, then correct timing and false notes in Ableton.' : 'Run npm run setup:transcription to enable model MIDI transcription.',
      'Treat reference-sketch MIDI as generated scaffolding, not transcription.',
      'Treat heuristic bass MIDI as full-mix pitch tracking, not source-separated bass.',
      'Use the generated prompt as a starting point for AI music generation.',
      'Run a deeper stem-aware pass once source separation is implemented.'
    ]
  };
}

function confidencePhrase(value) {
  const confidence = Number(value) || 0;
  if (confidence >= 0.7) return 'higher confidence';
  if (confidence >= 0.4) return 'medium confidence';
  if (confidence > 0) return 'low confidence';
  return 'unavailable confidence';
}

function summarizeEnergy(curve) {
  if (!curve.length) {
    return {
      summary: 'does not contain enough energy data yet',
      phrase: 'a balanced medium-energy groove'
    };
  }

  const values = curve.map((point) => Number(point.energy) || 0);
  const average = values.reduce((sum, value) => sum + value, 0) / values.length;
  const first = values[0];
  const last = values[values.length - 1];
  const trend = last > first * 1.15 ? 'builds over time' : last < first * 0.85 ? 'relaxes over time' : 'stays steady';

  if (average >= 0.45) {
    return { summary: `${trend} with high average intensity`, phrase: 'driving high-energy drums and a strong low-end pulse' };
  }
  if (average >= 0.2) {
    return { summary: `${trend} with moderate intensity`, phrase: 'a steady groove, defined bass movement, and controlled dynamics' };
  }
  return { summary: `${trend} with restrained intensity`, phrase: 'an atmospheric low-intensity arrangement and sparse rhythmic motion' };
}

function inferStyleTags(prompt, energy) {
  const lower = prompt.toLowerCase();
  const tags = [];
  if (lower.includes('tech house')) tags.push('tech house');
  if (lower.includes('house') && !tags.includes('tech house')) tags.push('house');
  if (lower.includes('trap')) tags.push('trap');
  if (lower.includes('ambient')) tags.push('ambient');
  if (lower.includes('dark')) tags.push('dark');
  if (lower.includes('groovy') || lower.includes('groove')) tags.push('groovy');
  if (!tags.length) tags.push(energy.summary.includes('high') ? 'dance-focused' : 'producer-focused');
  return tags.slice(0, 4);
}

module.exports = { buildPromptPackage, confidencePhrase, summarizeEnergy, inferStyleTags };
