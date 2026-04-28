#!/usr/bin/env node

const { createServer } = require('node:http');
const fs = require('node:fs/promises');
const path = require('node:path');
const { URL } = require('node:url');
const { createJobStore } = require('./lib/jobs');
const { runAnalysis } = require('./lib/pythonRunner');
const { buildPromptPackage } = require('./lib/promptGenerator');

const DEFAULT_PORT = Number.parseInt(process.env.PROMPT2MIDI_PORT || '47321', 10);
const MAX_AUDIO_BYTES = 250 * 1024 * 1024;

function createApp(options = {}) {
  const jobs = options.jobs || createJobStore();
  const analyzer = options.analyzer || runAnalysis;
  const promptGenerator = options.promptGenerator || buildPromptPackage;

  async function handleAnalyze(req, res) {
    const body = await readJsonBody(req);
    const prompt = typeof body.prompt === 'string' ? body.prompt.trim() : '';
    const audioPath = typeof body.audioPath === 'string' ? body.audioPath.trim() : '';

    if (!prompt && !audioPath) {
      return sendJson(res, 400, {
        error: {
          code: 'missing_input',
          message: 'Drop a WAV file or enter a prompt before analyzing.'
        }
      });
    }

    if (audioPath) {
      const validationError = await validateAudioPath(audioPath);
      if (validationError) return sendJson(res, 400, { error: validationError });
    }

    const job = jobs.create({ prompt, audioPath });
    setImmediate(() => {
      runJob(job.id, { prompt, audioPath }, jobs, analyzer, promptGenerator);
    });
    return sendJson(res, 202, { job_id: job.id, status: job.status });
  }

  async function router(req, res) {
    try {
      const url = new URL(req.url, `http://${req.headers.host || '127.0.0.1'}`);

      if (req.method === 'GET' && url.pathname === '/health') {
        return sendJson(res, 200, { ok: true, service: 'prompt2midi-local', version: '0.1.0' });
      }

      if (req.method === 'POST' && url.pathname === '/analyze') {
        return await handleAnalyze(req, res);
      }

      if (req.method === 'GET' && url.pathname === '/status') {
        const job = jobs.get(url.searchParams.get('id'));
        if (!job) return sendJson(res, 404, jobNotFound());
        return sendJson(res, 200, {
          job_id: job.id,
          status: job.status,
          progress: job.progress,
          message: job.message,
          error: job.error || null
        });
      }

      if (req.method === 'GET' && url.pathname === '/result') {
        const job = jobs.get(url.searchParams.get('id'));
        if (!job) return sendJson(res, 404, jobNotFound());
        if (job.status !== 'succeeded') {
          return sendJson(res, 409, {
            error: {
              code: 'result_not_ready',
              message: `Job is ${job.status}.`,
              status: job.status
            }
          });
        }
        return sendJson(res, 200, {
          job_id: job.id,
          status: job.status,
          result: job.result
        });
      }

      return sendJson(res, 404, { error: { code: 'not_found', message: 'Endpoint not found.' } });
    } catch (error) {
      const statusCode = error.statusCode || 500;
      return sendJson(res, statusCode, {
        error: {
          code: error.code || 'server_error',
          message: statusCode >= 500 ? 'Unexpected server error.' : error.message
        }
      });
    }
  }

  return createServer(router);
}

async function runJob(jobId, input, jobs, analyzer, promptGenerator) {
  jobs.update(jobId, { status: 'running', progress: 10, message: 'Preparing local analysis.' });

  try {
    let analysisPayload;
    if (input.audioPath) {
      jobs.update(jobId, { progress: 35, message: 'Analyzing WAV features.' });
      analysisPayload = await analyzer(input.audioPath, jobId);
    } else {
      analysisPayload = {
        analysis: promptOnlyAnalysis(input.prompt),
        midi_files: {}
      };
    }

    jobs.update(jobId, { progress: 75, message: 'Generating producer prompt.' });
    const interpretation = promptGenerator({
      prompt: input.prompt,
      analysis: analysisPayload.analysis
    });

    jobs.update(jobId, {
      status: 'succeeded',
      progress: 100,
      message: 'Analysis complete.',
      result: {
        analysis: analysisPayload.analysis,
        interpretation,
        midi_files: analysisPayload.midi_files || {}
      }
    });
  } catch (error) {
    jobs.update(jobId, {
      status: 'failed',
      progress: 100,
      message: 'Analysis failed.',
      error: normalizeError(error)
    });
  }
}

function promptOnlyAnalysis(prompt) {
  const lower = prompt.toLowerCase();
  const bpmMatch = lower.match(/\b(\d{2,3})\s*bpm\b/);
  const keyMatch = lower.match(/\b([a-g](?:#|b)?)\s*(major|minor|min|maj)\b/i);
  const scale = keyMatch ? `${keyMatch[1].toUpperCase()} ${keyMatch[2].startsWith('min') ? 'minor' : 'major'}` : 'C major';
  const bpm = bpmMatch ? Number.parseInt(bpmMatch[1], 10) : 120;

  return {
    source_path: null,
    duration_seconds: null,
    sample_rate: null,
    channels: null,
    bpm,
    key: scale,
    key_confidence: keyMatch ? 0.7 : 0.15,
    energy_curve: [
      { time: 0, energy: lower.includes('ambient') ? 0.22 : 0.52 },
      { time: 30, energy: lower.includes('drop') ? 0.9 : 0.62 },
      { time: 60, energy: lower.includes('breakdown') ? 0.35 : 0.68 }
    ],
    loudness: -14,
    spectral_features: {
      zero_crossing_rate: null,
      peak_amplitude: null
    },
    warnings: ['Prompt-only mode uses inferred defaults until generated audio or a reference track is provided.']
  };
}

function normalizeError(error) {
  if (error && error.code && error.message) {
    return { code: error.code, message: error.message };
  }
  return { code: 'analysis_failed', message: error.message || 'Analysis failed.' };
}

function jobNotFound() {
  return { error: { code: 'job_not_found', message: 'No job exists for that id.' } };
}

async function validateAudioPath(audioPath) {
  if (!path.isAbsolute(audioPath)) {
    return { code: 'invalid_audio_path', message: 'Audio path must be absolute.' };
  }

  if (!['.wav', '.wave'].includes(path.extname(audioPath).toLowerCase())) {
    return { code: 'unsupported_format', message: 'Phase 1 supports uncompressed PCM WAV files.' };
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

  return null;
}

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.setEncoding('utf8');
    req.on('data', (chunk) => {
      body += chunk;
      if (body.length > 1024 * 1024) {
        reject(Object.assign(new Error('Request body too large.'), { code: 'request_too_large', statusCode: 413 }));
        req.destroy();
      }
    });
    req.on('end', () => {
      if (!body.trim()) return resolve({});
      try {
        resolve(JSON.parse(body));
      } catch (error) {
        reject(Object.assign(new Error('Request body must be valid JSON.'), { code: 'invalid_json', statusCode: 400 }));
      }
    });
    req.on('error', reject);
  });
}

function sendJson(res, statusCode, payload) {
  const json = JSON.stringify(payload);
  res.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(json),
    'Access-Control-Allow-Origin': 'http://127.0.0.1'
  });
  res.end(json);
}

if (require.main === module) {
  const server = createApp();
  server.listen(DEFAULT_PORT, '127.0.0.1', () => {
    console.log(`prompt2midi local backend listening on http://127.0.0.1:${DEFAULT_PORT}`);
  });
}

module.exports = { createApp, promptOnlyAnalysis };
