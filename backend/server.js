#!/usr/bin/env node

const { createServer } = require('node:http');
const { URL } = require('node:url');
const { validateAudioPath } = require('./lib/audioInput');
const { createJobStore } = require('./lib/jobs');
const { runAnalysis } = require('./lib/pythonRunner');
const { buildPromptPackage } = require('./lib/promptGenerator');
const { generateSunoPrompt } = require('./lib/geminiPromptGenerator');
const { createPipelineLogger } = require('./lib/devLogger');

const DEFAULT_PORT = Number.parseInt(process.env.PROMPT2MIDI_PORT || '47321', 10);
const SIMILARITY_LEVELS = new Set(['low', 'medium-low', 'medium', 'medium-high', 'high', 'near-identical', 'identical']);

function createApp(options = {}) {
  const jobs = options.jobs || createJobStore();
  const analyzer = options.analyzer || runAnalysis;
  const promptGenerator = options.promptGenerator || buildPromptPackage;
  const sunoGenerator = options.sunoGenerator || generateSunoPrompt;

  async function handleAnalyze(req, res) {
    const body = await readJsonBody(req);
    const prompt = typeof body.prompt === 'string' ? body.prompt.trim() : '';
    const audioPath = typeof body.audioPath === 'string' ? body.audioPath.trim() : '';
    const similarityLevel = typeof body.similarityLevel === 'string' ? body.similarityLevel.trim().toLowerCase() : '';

    if (!prompt && !audioPath) {
      return sendJson(res, 400, {
        error: {
          code: 'missing_input',
          message: 'Drop a WAV/MP3 file or enter a prompt before analyzing.'
        }
      });
    }
    if (similarityLevel && !SIMILARITY_LEVELS.has(similarityLevel)) {
      return sendJson(res, 400, {
        error: {
          code: 'invalid_similarity_level',
          message: 'Similarity level must be low, medium-low, medium, medium-high, high, near-identical, or identical.'
        }
      });
    }

    if (audioPath) {
      const validationError = await validateAudioPath(audioPath);
      if (validationError) return sendJson(res, 400, { error: validationError });
    }

    const job = jobs.create({ prompt, audioPath, similarityLevel });
    setImmediate(() => {
      runJob(job.id, { prompt, audioPath, similarityLevel }, jobs, analyzer, promptGenerator, sunoGenerator);
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
          events: job.events || [],
          timings: job.timings || [],
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

async function runJob(jobId, input, jobs, analyzer, promptGenerator, sunoGenerator) {
  const log = createJobPipelineLogger(jobId, jobs);
  jobs.update(jobId, { status: 'running', progress: 10, message: 'Preparing local analysis.' });
  log.banner(input);

  try {
    let analysisPayload;
    if (input.audioPath) {
      log.stage('01 validate input', 'accepted by API');
      log.done('01 validate input');
      jobs.update(jobId, { progress: 35, message: 'Analyzing reference features.' });
      log.stage('02 audio analysis', 'decode, features, MIDI extraction');
      analysisPayload = await analyzer(input.audioPath, jobId, log, input.prompt, input.similarityLevel);
      log.done('02 audio analysis', `${Object.keys(analysisPayload.midi_files || {}).length} MIDI file(s)`);
    } else {
      log.stage('01 prompt-only analysis');
      analysisPayload = {
        analysis: promptOnlyAnalysis(input.prompt),
        midi_files: {}
      };
      log.done('01 prompt-only analysis');
    }

    jobs.update(jobId, { progress: 75, message: 'Generating SUNO prompt.' });

    log.stage('03 prompt package', 'producer summary + AI prompt');
    const interpretation = promptGenerator({
      prompt: input.prompt,
      analysis: analysisPayload.analysis
    });
    log.done('03 prompt package');

    let sunoPrompt = analysisPayload.suno_prompt || null;
    if (input.audioPath && analysisPayload.composition) {
      log.stage('03b suno prompt', 'Gemini SUNO prompt from analysis + composition');
      try {
        const geminiResult = await sunoGenerator({
          analysis: analysisPayload.analysis,
          composition: analysisPayload.composition,
          exportDir: analysisPayload.export_dir,
          userPrompt: input.prompt
        });
        if (geminiResult) {
          sunoPrompt = geminiResult;
          log.done('03b suno prompt', `${geminiResult.text.length} chars`);
        } else {
          log.done('03b suno prompt', 'skipped — no key or disabled');
        }
      } catch (err) {
        log.warn(`Gemini SUNO prompt failed: ${err.message || String(err)} — using stub`);
        log.done('03b suno prompt', 'failed — using stub fallback');
      }
    }

    log.stage('04 aggregate result', 'store job result for UI polling');
    jobs.update(jobId, {
      status: 'succeeded',
      progress: 100,
      message: 'Analysis complete.',
      result: {
        analysis: analysisPayload.analysis,
        composition: analysisPayload.composition || null,
        full_arrangement: analysisPayload.full_arrangement || null,
        suno_prompt: sunoPrompt,
        export_dir: analysisPayload.export_dir || null,
        interpretation,
        midi_files: analysisPayload.midi_files || {},
        export_files: analysisPayload.export_files || {},
        midi_assets: analysisPayload.midi_assets || [],
        midi_notes: analysisPayload.midi_notes || []
      }
    });
    log.done('04 aggregate result');
    log.success(`bpm=${analysisPayload.analysis.bpm || 'unknown'} key=${analysisPayload.analysis.key || 'unknown'}`);
  } catch (error) {
    jobs.update(jobId, {
      status: 'failed',
      progress: 100,
      message: 'Analysis failed.',
      error: normalizeError(error)
    });
    log.fail(error);
  }
}

function createJobPipelineLogger(jobId, jobs) {
  const terminal = createPipelineLogger(jobId);
  const startedAt = Date.now();
  const stageStarts = new Map();
  const timings = [];
  let lastProgressKey = '';
  let lastProgressCount = 0;

  function record(type, label, detail = '', meta = {}) {
    const job = jobs.get(jobId);
    if (!job) return;
    const event = {
      at: new Date().toISOString(),
      elapsed_ms: Math.max(0, Date.now() - startedAt),
      type,
      label,
      detail,
      ...meta
    };
    const events = [
      ...(job.events || []),
      event
    ].slice(-200);
    jobs.update(jobId, {
      events,
      timings,
      message: detail ? `${label}: ${detail}` : label
    });
  }

  function updateProgress(detail) {
    const job = jobs.get(jobId);
    if (!job) return;
    const key = canonicalProgress(detail);
    const events = [...(job.events || [])];
    const now = new Date().toISOString();
    const elapsed = Math.max(0, Date.now() - startedAt);
    if (events.length && key && key === lastProgressKey && events[events.length - 1].type === 'progress') {
      lastProgressCount += 1;
      events[events.length - 1] = {
        ...events[events.length - 1],
        at: now,
        elapsed_ms: elapsed,
        count: lastProgressCount,
        detail: lastProgressCount > 1 ? `${detail} (${lastProgressCount} updates)` : detail
      };
    } else {
      lastProgressKey = key;
      lastProgressCount = 1;
      events.push({
        at: now,
        elapsed_ms: elapsed,
        type: 'progress',
        label: 'Progress',
        detail
      });
    }
    jobs.update(jobId, {
      events: events.slice(-200),
      timings,
      progress: progressForPipeline(detail, job.progress || 0),
      message: detail
    });
  }

  return {
    banner(input) {
      terminal.banner(input);
      record('start', 'Job started', input.audioPath ? `Audio: ${input.audioPath}` : 'Prompt-only mode');
    },
    stage(name, detail = '') {
      stageStarts.set(name, Date.now());
      terminal.stage(name, detail);
      record('stage', name, detail);
    },
    done(name, detail = '') {
      const started = stageStarts.get(name) || startedAt;
      const durationMs = Math.max(0, Date.now() - started);
      timings.push({
        label: name,
        detail,
        started_at: new Date(started).toISOString(),
        duration_ms: durationMs
      });
      terminal.done(name, detail);
      record('done', name, detail, { duration_ms: durationMs });
    },
    warn(detail) {
      terminal.warn(detail);
      record('warning', 'Warning', detail);
    },
    info(detail) {
      terminal.info(detail);
      record('detail', 'Detail', detail);
    },
    progress(detail) {
      terminal.info(detail);
      updateProgress(detail);
    },
    fail(error) {
      terminal.fail(error);
      record('failed', 'Analysis failed', error && (error.message || String(error)));
    },
    success(detail = '') {
      terminal.success(detail);
      record('complete', 'Analysis complete', detail, { duration_ms: Math.max(0, Date.now() - startedAt) });
    }
  };
}

function canonicalProgress(detail) {
  const text = String(detail || '');
  if (/ace-step: waiting for task/i.test(text)) return 'ace-step: waiting for task';
  return text.replace(/[0-9a-f]{8}-[0-9a-f-]{27,}/ig, '<task>');
}

function progressForPipeline(detail, current) {
  const text = String(detail || '');
  const rules = [
    [/reading audio|feature extraction/i, 15],
    [/enhanced analysis/i, 22],
    [/external analysis/i, 28],
    [/beat grid/i, 32],
    [/deep analysis/i, 38],
    [/midi sketch|heuristic bass|reference groove/i, 45],
    [/stem separation/i, 54],
    [/model transcription/i, 62],
    [/reference transform|composition/i, 68],
    [/full arrangement/i, 72],
    [/ace-step: submitting/i, 78],
    [/ace-step: waiting/i, 84],
    [/ace-step: downloading|ace-step: scoring/i, 90],
    [/audio generation/i, 94],
  ];
  for (const [pattern, value] of rules) {
    if (pattern.test(text)) return Math.max(current || 0, value);
  }
  return Math.max(current || 0, 10);
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
    bpm_confidence: bpmMatch ? 0.65 : 0.15,
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
    console.log(`\x1b[32m● prompt2midi backend listening\x1b[0m http://127.0.0.1:${DEFAULT_PORT}`);
    console.log('\x1b[2m  Waiting for Analyze jobs. Press Ctrl-C to stop.\x1b[0m');
  });
}

module.exports = { createApp, promptOnlyAnalysis };
