function buildPromptPackage({ prompt = '', analysis }) {
  const bpm = analysis.bpm || 120;
  const key = analysis.key || 'C major';
  const energy = summarizeEnergy(analysis.energy_curve || []);
  const userIntent = prompt.trim() || 'reference-track inspired production';

  const styleTags = inferStyleTags(userIntent, energy);
  const aiPrompt = [
    `${styleTags.join(', ')} track at ${Math.round(bpm)} BPM in ${key}`,
    `with ${energy.phrase}`,
    'tight arrangement, producer-ready mix direction, and clear instrumental layers',
    userIntent
  ].filter(Boolean).join(', ');

  return {
    producer_summary: `Detected ${Math.round(bpm)} BPM in ${key}. The energy profile ${energy.summary}. Use this as the production anchor before deeper stem, chord, or section extraction.`,
    style_tags: styleTags,
    ai_music_prompt: aiPrompt,
    next_steps: [
      'Export the bass MIDI sketch into Ableton.',
      'Use the generated prompt as a starting point for AI music generation.',
      'Run a deeper pass once section and stem analysis are implemented.'
    ]
  };
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

module.exports = { buildPromptPackage, summarizeEnergy, inferStyleTags };
