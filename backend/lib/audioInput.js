const fs = require('node:fs/promises');
const path = require('node:path');
const { spawn } = require('node:child_process');

const MAX_AUDIO_BYTES = 250 * 1024 * 1024;
const SUPPORTED_AUDIO_EXTENSIONS = new Set(['.wav', '.wave', '.mp3']);

async function validateAudioPath(audioPath) {
  if (!path.isAbsolute(audioPath)) {
    return { code: 'invalid_audio_path', message: 'Audio path must be absolute.' };
  }

  const extension = path.extname(audioPath).toLowerCase();
  if (!SUPPORTED_AUDIO_EXTENSIONS.has(extension)) {
    return { code: 'unsupported_format', message: 'Supported inputs are PCM WAV/WAVE and MP3 files.' };
  }

  let stat;
  try {
    stat = await fs.stat(audioPath);
  } catch {
    return { code: 'audio_not_found', message: 'Audio file does not exist.' };
  }

  if (!stat.isFile()) {
    return { code: 'invalid_audio_path', message: 'Audio path must point to a file.' };
  }

  if (stat.size > MAX_AUDIO_BYTES) {
    return { code: 'audio_too_large', message: 'Audio file exceeds the Phase 1 size limit.' };
  }

  if (extension === '.mp3' && !(await findFfmpeg())) {
    return { code: 'decoder_unavailable', message: 'MP3 input requires ffmpeg on PATH or PROMPT2MIDI_FFMPEG.' };
  }

  return null;
}

async function prepareAudioForAnalysis(audioPath, outputDir) {
  const extension = path.extname(audioPath).toLowerCase();
  if (extension === '.wav' || extension === '.wave') {
    return { analysisPath: audioPath, warnings: [] };
  }

  if (extension !== '.mp3') {
    const error = new Error('Unsupported audio format.');
    error.code = 'unsupported_format';
    throw error;
  }

  const ffmpeg = await findFfmpeg();
  if (!ffmpeg) {
    const error = new Error('MP3 input requires ffmpeg on PATH or PROMPT2MIDI_FFMPEG.');
    error.code = 'decoder_unavailable';
    throw error;
  }

  await fs.mkdir(outputDir, { recursive: true });
  const decodedPath = path.join(outputDir, 'decoded-input.wav');
  await runProcess(ffmpeg, [
    '-y',
    '-hide_banner',
    '-loglevel', 'error',
    '-i', audioPath,
    '-vn',
    '-acodec', 'pcm_s16le',
    '-ar', '44100',
    decodedPath
  ]);

  return {
    analysisPath: decodedPath,
    warnings: ['MP3 input was decoded to temporary PCM WAV with ffmpeg before analysis.']
  };
}

async function findFfmpeg() {
  const candidates = [
    process.env.PROMPT2MIDI_FFMPEG,
    ...String(process.env.PATH || '').split(path.delimiter).map((entry) => path.join(entry, 'ffmpeg')),
    '/opt/homebrew/bin/ffmpeg',
    '/usr/local/bin/ffmpeg',
    '/usr/bin/ffmpeg'
  ].filter(Boolean);

  for (const candidate of candidates) {
    try {
      await fs.access(candidate);
      return candidate;
    } catch {
      // Try the next candidate.
    }
  }

  return null;
}

function runProcess(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ['ignore', 'ignore', 'pipe'] });
    let stderr = '';
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString('utf8');
    });
    child.on('error', reject);
    child.on('close', (code) => {
      if (code === 0) return resolve();
      const error = new Error(stderr || `${path.basename(command)} exited with ${code}.`);
      error.code = 'decode_failed';
      reject(error);
    });
  });
}

module.exports = { findFfmpeg, prepareAudioForAnalysis, validateAudioPath };
