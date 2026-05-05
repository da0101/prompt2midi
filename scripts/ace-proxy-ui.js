#!/usr/bin/env node

const { createServer, request } = require('node:http');
const { execFileSync, spawn } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { URL } = require('node:url');

const repoRoot = path.resolve(__dirname, '..');
const runner = path.join(repoRoot, 'scripts', 'run-suno-proxy-pipeline.js');
const aceStarter = path.join(repoRoot, 'scripts', 'start-ace-step-api.sh');
const aceUrl = process.env.PROMPT2MIDI_ACE_STEP_URL || 'http://127.0.0.1:8001';
const port = Number.parseInt(process.env.PROMPT2MIDI_ACE_UI_PORT || '47322', 10);
const autoStartAce = process.env.PROMPT2MIDI_ACE_PROXY_AUTOSTART !== '0';
const serverStartedAt = new Date().toISOString();
const runs = new Map();
const aceState = {
  child: null,
  status: 'unknown',
  message: 'Not checked yet',
  startedByUi: false,
  logs: [],
};
let aceStartPromise = null;
const LEVELS = new Set(['low', 'medium-low', 'medium', 'medium-high', 'high', 'very-high', 'near-identical']);
const NON_DIAGNOSTIC_NEAR_COPY = {
  similarityLevel: 'near-identical',
  referenceStrength: 0.42,
  coverNoiseStrength: 0.2,
  aceSeed: -1,
};

const STEP_PROGRESS = [
  [/starting ACE server/i, 3],
  [/ACE server ready/i, 4],
  [/preparing reference audio/i, 8],
  [/reference audio ready/i, 10],
  [/local analysis and ACE generation started|started /i, 12],
  [/decod|reading audio|feature extraction/i, 15],
  [/enhanced analysis/i, 22],
  [/external analysis/i, 27],
  [/deep analysis|genre|chords|structure/i, 32],
  [/gemini/i, 38],
  [/fast sample lane/i, 42],
  [/generating .*ACE sample batch/i, 48],
  [/submitting reference-conditioned|submitting .*generation task/i, 55],
  [/waiting for task/i, 62],
  [/downloading candidate/i, 84],
  [/scoring candidate/i, 88],
  [/ACE generation finished|selecting proxy audio/i, 91],
  [/preparing Suno proxy package|preparing generated proxy|suno-proxy/i, 94],
  [/Suno proxy package ready/i, 98],
];

function createRun(input) {
  const caps = getAceCapabilities();
  const id = new Date().toISOString().replace(/\D/g, '').slice(0, 14) + '-' + Math.random().toString(16).slice(2, 8);
  const reference = String(input.reference || '').trim();
  const prompt = String(input.prompt || 'same tempo and key area as the reference.').trim();
  let similarityLevel = normalizeLevel(input.similarityLevel || 'medium-high');
  const referenceStart = clampNumber(input.referenceStart, 0, 600, 8);
  const duration = clampNumber(input.duration, 10, caps.maxDurationSeconds, 30);
  const candidates = Math.round(clampNumber(input.candidates, 1, caps.maxCandidates, Math.min(4, caps.maxCandidates)));
  let referenceStrength = clampNumber(input.referenceStrength, 0, 1, 0.32);
  let coverNoiseStrength = clampNumber(input.coverNoiseStrength, 0, 1, 0.14);
  const aceSteps = Math.round(clampNumber(input.aceSteps, caps.steps.min, caps.steps.max, caps.steps.default));
  const aceGuidance = clampNumber(input.aceGuidance, caps.guidance.min, caps.guidance.max, caps.guidance.default);
  let aceSeed = Math.round(clampNumber(input.aceSeed, caps.seed.min, caps.seed.max, caps.seed.default));
  const vocals = input.vocals !== false && input.vocals !== 'false' && input.vocals !== 0 && input.vocals !== '0';
  // Temporarily disable the raw reconstruction path while the normal inspired pipeline is stabilized.
  // Keep this second pipeline: it is promising, but it still needs careful fine tuning before exposure.
  const reconstructionDiagnostic = false;
  const downgradedUnsafeCloneControls = !reconstructionDiagnostic && referenceStrength >= 0.95 && coverNoiseStrength >= 0.95;
  if (downgradedUnsafeCloneControls) {
    similarityLevel = NON_DIAGNOSTIC_NEAR_COPY.similarityLevel;
    referenceStrength = NON_DIAGNOSTIC_NEAR_COPY.referenceStrength;
    coverNoiseStrength = NON_DIAGNOSTIC_NEAR_COPY.coverNoiseStrength;
    aceSeed = NON_DIAGNOSTIC_NEAR_COPY.aceSeed;
  }
  const geminiBrief = reconstructionDiagnostic ? false : truthyCheckbox(input.geminiBrief);
  const geminiControl = reconstructionDiagnostic ? false : truthyCheckbox(input.geminiControl);
  const requestedDir = String(input.outputDir || '').trim();
  const outputDir = requestedDir && path.isAbsolute(requestedDir)
    ? path.resolve(requestedDir)
    : path.resolve(
        repoRoot,
        'tmp',
        String(input.outputName || `ace-ui-${path.basename(reference || 'reference', path.extname(reference || ''))}-${id}`)
          .replace(/[^a-z0-9._-]+/gi, '-')
          .replace(/^-+|-+$/g, '')
      );

  const run = {
    id,
    status: 'queued',
    progress: 3,
    step: 'Queued',
    createdAt: new Date().toISOString(),
    input: {
      reference,
      prompt,
      similarityLevel,
      referenceStart,
      duration,
      candidates,
      referenceStrength,
      coverNoiseStrength,
      aceSteps,
      aceGuidance,
      aceSeed,
      vocals,
      geminiBrief,
      geminiControl,
      reconstructionDiagnostic,
      outputDir,
    },
    events: [],
    outputBuffer: '',
    files: {},
    error: null,
    reportedArtifacts: {},
    downgradedUnsafeCloneControls,
  };
  runs.set(id, run);
  prepareAndStartRun(run);
  return run;
}

async function prepareAndStartRun(run) {
  try {
    updateRun(run, 'queued', 3, 'Starting ACE server');
    addEvent(run, 'progress', 'starting ACE server');
    await ensureAceReady(run);
    startRun(run);
  } catch (error) {
    failRun(run, error.message || String(error));
  }
}

async function ensureAceReady(run) {
  if (autoStartAce) {
    await startAceServer();
  } else {
    addEvent(run, 'trace', 'ACE auto-start disabled; expecting separate ACE-Step terminal on 127.0.0.1:8001');
  }
  const deadline = Date.now() + 180000;
  while (Date.now() < deadline) {
    const health = await getAceHealth();
    if (health.running) {
      updateRun(run, 'queued', 4, 'ACE server ready');
      addEvent(run, 'progress', 'ACE server ready');
      return;
    }
    updateRun(run, 'queued', 4, 'Waiting for ACE server to become ready');
    addEvent(run, 'progress', health.error ? `ACE not ready: ${health.error}` : 'ACE not ready yet');
    await sleep(3000);
  }
  throw new Error('ACE server did not become ready within 180 seconds.');
}

async function startAceServer() {
  if (aceStartPromise) return aceStartPromise;
  aceStartPromise = startAceServerInner().finally(() => {
    aceStartPromise = null;
  });
  return aceStartPromise;
}

async function startAceServerInner() {
  const health = await getAceHealth();
  if (health.running) {
    aceState.status = 'running';
    aceState.message = 'ACE server is already running';
    return getAceStatusPayload();
  }
  if (aceState.child && !aceState.child.killed) {
    aceState.status = 'starting';
    aceState.message = 'ACE server is starting';
    return getAceStatusPayload();
  }

  aceState.status = 'starting';
  aceState.message = 'Starting ACE server';
  aceState.startedByUi = true;
  addAceLog('Starting ACE server with scripts/start-ace-step-api.sh');

  const child = spawn('bash', [aceStarter], {
    cwd: repoRoot,
    env: process.env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  aceState.child = child;

  child.stdout.on('data', (chunk) => handleAceLog(chunk.toString()));
  child.stderr.on('data', (chunk) => handleAceLog(chunk.toString()));
  child.on('error', (error) => {
    aceState.status = 'failed';
    aceState.message = error.message || String(error);
    addAceLog(`ACE server error: ${aceState.message}`);
  });
  child.on('exit', (code, signal) => {
    if (aceState.child === child) aceState.child = null;
    if (signal) {
      aceState.status = 'stopped';
      aceState.message = `ACE server stopped by ${signal}`;
    } else if (code === 0) {
      aceState.status = 'stopped';
      aceState.message = 'ACE server stopped';
    } else {
      aceState.status = 'failed';
      aceState.message = `ACE server exited with code ${code}`;
    }
    addAceLog(aceState.message);
  });

  return getAceStatusPayload();
}

async function stopAceServer({ managedOnly = false } = {}) {
  const activeRun = [...runs.values()].some((run) => run.status === 'running' || run.status === 'queued');
  if (activeRun) {
    aceState.message = 'Not stopping ACE while a generation run is active';
    addAceLog(aceState.message);
    return getAceStatusPayload();
  }

  let stopped = false;
  if (aceState.child && !aceState.child.killed) {
    aceState.child.kill('SIGTERM');
    stopped = true;
  }
  if (!managedOnly) {
    const pids = await findAcePids();
    for (const pid of pids) {
      try {
        process.kill(pid, 'SIGTERM');
        stopped = true;
      } catch (_) {}
    }
  }

  aceState.status = 'stopping';
  aceState.message = stopped ? 'Stopping ACE server' : 'No ACE server process found';
  addAceLog(aceState.message);
  return getAceStatusPayload();
}

async function restartAceServer() {
  await stopAceServer({ managedOnly: false });
  await sleep(1200);
  return startAceServer();
}

async function getAceStatusPayload() {
  const health = await getAceHealth();
  const activeRun = [...runs.values()].some((run) => run.status === 'running' || run.status === 'queued');
  if (health.running) {
    aceState.status = 'running';
    aceState.message = health.loadedModel ? `Running: ${health.loadedModel}` : 'Running';
  } else if (activeRun) {
    aceState.status = 'busy';
    aceState.message = health.error ? `ACE is busy or warming up: ${health.error}` : 'ACE is busy or warming up';
  } else if (aceState.child && !aceState.child.killed) {
    aceState.status = aceState.status === 'stopping' ? 'stopping' : 'starting';
    aceState.message = health.error ? `ACE process exists, waiting for health: ${health.error}` : 'ACE process exists, waiting for health';
  } else if (aceState.status !== 'starting' && aceState.status !== 'stopping') {
    const pids = await findAcePids();
    if (pids.length) {
      aceState.status = 'busy';
      aceState.message = health.error ? `ACE process is alive but health timed out: ${health.error}` : 'ACE process is alive but health is not responding';
    } else {
      aceState.status = 'stopped';
      aceState.message = health.error || 'Stopped';
    }
  }
  return {
    status: aceState.status,
    message: aceState.message,
    url: aceUrl,
    managed: Boolean(aceState.child),
    startedByUi: aceState.startedByUi,
    logs: aceState.logs.slice(-40),
    health,
    capabilities: getAceCapabilities(),
  };
}

function getAceCapabilities() {
  const totalMemoryGb = detectSystemMemoryGb();
  const memoryClassGb = Math.max(8, Math.round(totalMemoryGb / 8) * 8);
  const model = process.env.PROMPT2MIDI_ACE_STEP_MODEL || 'acestep-v15-turbo';
  const isTurbo = /turbo/i.test(model);
  const isAppleSilicon = process.platform === 'darwin' && process.arch === 'arm64';
  const cpuModel = detectCpuModel();
  const hardwareLabel = isAppleSilicon
    ? `Apple Silicon Mac, about ${memoryClassGb}GB unified memory`
    : `${cpuModel}, about ${memoryClassGb}GB RAM`;

  const maxCandidates = memoryClassGb >= 32 ? 6 : 4;
  const maxDurationSeconds = memoryClassGb >= 64 ? 240 : memoryClassGb >= 32 ? 180 : memoryClassGb >= 16 ? 120 : 60;
  const steps = isTurbo
    ? { min: 1, max: 8, default: 8, note: 'Turbo ACE clamps requested steps above 8, so 8 is the real maximum.' }
    : { min: 8, max: memoryClassGb >= 64 ? 64 : memoryClassGb >= 32 ? 48 : 32, default: memoryClassGb >= 32 ? 32 : 24, note: 'Non-turbo ACE can use more steps when memory allows.' };
  const guidance = isTurbo
    ? { min: 1, max: 1, default: 1, note: 'Turbo ACE overrides guidance to 1.0, so this is fixed for the current model.' }
    : { min: 1, max: 20, default: 7, note: 'Guidance affects prompt strength on non-turbo ACE models.' };
  const seed = { min: -1, max: 9999, default: -1, note: 'Seed is not hardware-limited. -1 means random; fixed numbers make tests repeatable.' };

  return {
    hardwareLabel,
    model,
    memoryGb: Number(totalMemoryGb.toFixed(1)),
    memoryClassGb,
    isTurbo,
    maxCandidates,
    maxDurationSeconds,
    steps,
    guidance,
    seed,
    message: `${hardwareLabel}. Current model: ${model}. ${isTurbo ? 'Turbo mode caps effective steps at 8 and fixes guidance at 1.0; more memory mainly helps longer clips and more candidates.' : 'Higher memory allows longer clips, more candidates, and more diffusion steps.'}`,
  };
}

function detectSystemMemoryGb() {
  if (process.platform === 'darwin') {
    try {
      const bytes = Number(execFileSync('/usr/sbin/sysctl', ['-n', 'hw.memsize'], {
        encoding: 'utf8',
        stdio: ['ignore', 'pipe', 'ignore'],
      }).trim());
      if (Number.isFinite(bytes) && bytes > 0) return bytes / (1024 ** 3);
    } catch {}
  }
  return os.totalmem() / (1024 ** 3);
}

function detectCpuModel() {
  if (process.platform === 'darwin') {
    try {
      const value = execFileSync('/usr/sbin/sysctl', ['-n', 'machdep.cpu.brand_string'], {
        encoding: 'utf8',
        stdio: ['ignore', 'pipe', 'ignore'],
      }).trim();
      if (value) return value;
    } catch {}
  }
  return (os.cpus()[0] && os.cpus()[0].model) || 'local CPU';
}

function getAceHealth() {
  return new Promise((resolve) => {
    const req = request(`${aceUrl.replace(/\/$/, '')}/health`, { method: 'GET', timeout: 2500 }, (res) => {
      let body = '';
      res.on('data', (chunk) => { body += chunk.toString(); });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(body);
          const data = parsed.data || parsed;
          resolve({
            running: res.statusCode >= 200 && res.statusCode < 300,
            statusCode: res.statusCode,
            loadedModel: data.loaded_model || null,
            modelsInitialized: Boolean(data.models_initialized),
            raw: parsed,
          });
        } catch (error) {
          resolve({ running: false, statusCode: res.statusCode, error: error.message || String(error) });
        }
      });
    });
    req.on('timeout', () => req.destroy(new Error('ACE health check timed out')));
    req.on('error', (error) => resolve({ running: false, error: error.message || String(error) }));
    req.end();
  });
}

function findAcePids() {
  return new Promise((resolve) => {
    const child = spawn('ps', ['axo', 'pid=,command='], { stdio: ['ignore', 'pipe', 'ignore'] });
    let output = '';
    child.stdout.on('data', (chunk) => { output += chunk.toString(); });
    child.on('exit', () => {
      const pids = [];
      for (const line of output.split(/\r?\n/)) {
        if (!/acestep-api/.test(line) || !/--port 8001/.test(line)) continue;
        const match = line.trim().match(/^(\d+)/);
        if (match) pids.push(Number(match[1]));
      }
      resolve(pids);
    });
    child.on('error', () => resolve([]));
  });
}

function handleAceLog(text) {
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    addAceLog(line);
    if (/Uvicorn running|Application startup complete|models_initialized/i.test(line)) {
      aceState.status = 'running';
      aceState.message = 'ACE server is running';
    }
  }
}

function addAceLog(message) {
  aceState.logs.push({ at: new Date().toISOString(), message });
  aceState.logs = aceState.logs.slice(-80);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function startRun(run) {
  const { input } = run;
  if (!path.isAbsolute(input.reference) || !fs.existsSync(input.reference)) {
    failRun(run, `Reference file does not exist or is not absolute: ${input.reference}`);
    return;
  }

  fs.mkdirSync(input.outputDir, { recursive: true });
  const args = [
    runner,
    '--reference', input.reference,
    '--output-dir', input.outputDir,
    '--similarity-level', input.similarityLevel,
    '--duration', String(input.duration),
    '--candidates', String(input.candidates),
    '--reference-start', String(input.referenceStart),
    '--prompt', input.prompt,
  ];
  if (input.vocals) args.push('--vocals');
  else args.push('--instrumental');
  if (input.geminiControl) args.push('--gemini-control');
  else if (input.geminiBrief) args.push('--gemini-brief');

  const env = {
    ...process.env,
    PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH: String(input.referenceStrength),
    PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH: String(input.coverNoiseStrength),
    PROMPT2MIDI_ACE_STEP_STEPS: String(input.aceSteps),
    PROMPT2MIDI_ACE_STEP_GUIDANCE: String(input.aceGuidance),
    PROMPT2MIDI_ACE_STEP_SEED: String(input.aceSeed),
    PROMPT2MIDI_ACE_STEP_RECONSTRUCTION_DIAGNOSTIC: input.reconstructionDiagnostic ? '1' : '0',
    PROMPT2MIDI_DISABLE_GEMINI: input.reconstructionDiagnostic ? '1' : process.env.PROMPT2MIDI_DISABLE_GEMINI,
    PROMPT2MIDI_TRACE_PROGRESS: '1',
    PROMPT2MIDI_RUN_ID: run.id,
  };

  updateRun(run, 'running', 5, 'Starting clean ACE proxy lane');
  addEvent(run, 'trace', `ui api pid ${process.pid}; started ${serverStartedAt}`);
  addEvent(run, 'trace', `run uuid ${run.id}`);
  addEvent(run, 'trace', `output dir ${input.outputDir}`);
  addEvent(run, 'trace', `requested controls: similarity=${input.similarityLevel}; reference_guidance=${input.referenceStrength}; audio_start_amount=${input.coverNoiseStrength}; steps=${input.aceSteps}; guidance=${input.aceGuidance}; seed=${input.aceSeed}; ref_start=${input.referenceStart}s; duration=${input.duration}s; candidates=${input.candidates}`);
  if (run.downgradedUnsafeCloneControls) {
    addEvent(run, 'warning', 'Diagnostic was off but source controls were 1/1; downgraded to normal near-identical controls 0.42/0.20 to avoid an accidental clone.');
  }
  if (input.candidates > 1 && input.aceSeed >= 0) {
    addEvent(run, 'warning', 'Fixed seed with multiple ACE cover candidates can repeat candidates; use seed -1 for varied candidates.');
  }
  addEvent(run, 'trace', input.reconstructionDiagnostic
    ? 'Reconstruction diagnostic: enabled; Gemini disabled; ACE prompt uses minimal reconstruction wording'
    : 'Reconstruction diagnostic: disabled');
  addEvent(run, 'trace', input.geminiControl
    ? 'Gemini mode: brief + experimental ACE controls enabled'
    : input.geminiBrief
      ? 'Gemini mode: smart ACE brief enabled'
      : 'Gemini mode: disabled');
  const layerTrace = requestedLayerTrace(input.prompt);
  if (layerTrace) addEvent(run, 'trace', layerTrace);
  addEvent(run, 'command', `node ${args.map(shellish).join(' ')}`);

  const child = spawn(process.execPath, args, {
    cwd: repoRoot,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  run.pid = child.pid;

  child.stdout.on('data', (chunk) => handleOutput(run, chunk.toString()));
  child.stderr.on('data', (chunk) => handleOutput(run, chunk.toString()));
  child.on('error', (error) => failRun(run, error.message || String(error)));
  child.on('exit', (code, signal) => {
    flushOutput(run);
    collectFiles(run);
    if (signal) {
      failRun(run, `Stopped by signal ${signal}`);
      return;
    }
    if (code === 0) {
      updateRun(run, 'succeeded', 100, 'Done');
      addEvent(run, 'done', 'Generated ACE candidates and Suno proxy package');
    } else {
      failRun(run, `Pipeline exited with code ${code}`);
    }
  });
}

function handleOutput(run, text) {
  run.outputBuffer = (run.outputBuffer || '') + text.replace(/\r/g, '\n');
  const lines = run.outputBuffer.split('\n');
  run.outputBuffer = lines.pop() || '';
  for (const rawLine of lines) {
    processOutputLine(run, rawLine);
  }
  collectFiles(run);
}

function flushOutput(run) {
  if (!run.outputBuffer) return;
  processOutputLine(run, run.outputBuffer);
  run.outputBuffer = '';
}

function processOutputLine(run, rawLine) {
  const line = rawLine.trim();
    // Skip blank lines and spinner frames
  if (!line || /^[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]$/.test(line)) return;

  if (line.startsWith('progress: ')) {
    const step = line.slice('progress: '.length);
    updateRun(run, 'running', progressFor(step, run.progress), step);
    addEvent(run, 'progress', step);
  } else if (/^[◆✓!]\s+/.test(line)) {
    const step = line.replace(/^[◆✓!]\s+/, '').trim();
    updateRun(run, 'running', progressFor(step, run.progress), step);
    addEvent(run, 'progress', step);
  } else if (line.startsWith('trace: ')) {
    addEvent(run, 'trace', line.slice('trace: '.length));
  } else if (/ACE-Step API is not reachable/i.test(line)) {
    updateRun(run, 'running', run.progress, 'Waiting for ACE server');
    addEvent(run, 'warning', line);
  } else if (/error|failed|traceback/i.test(line)) {
    addEvent(run, 'error', line);
  } else if (/warning/i.test(line)) {
    addEvent(run, 'warning', line);
  } else if (/^\{/.test(line) || /^\[/.test(line)) {
    // skip raw JSON blobs — too noisy
  } else {
    // Capture all other pipeline stdout so nothing is hidden from the user
    addEvent(run, 'log', line);
  }
}

function progressFor(step, current) {
  for (const [pattern, value] of STEP_PROGRESS) {
    if (pattern.test(step)) return Math.max(current || 0, value);
  }
  if (/waiting for task/i.test(step)) return Math.min(82, (current || 62) + 2);
  return Math.max(current || 0, 10);
}

function requestedLayerTrace(prompt) {
  const text = String(prompt || '').toLowerCase().replace(/-/g, ' ');
  const layers = [];
  if (/\b(cow\s*bell|cowbell)\b/.test(text)) layers.push('cowbell');
  if (/\b(vocal\s+chops?|voice\s+chops?|chopped\s+vocals?)\b/.test(text)) layers.push('vocal chops');
  if (/\b(tribal\s+percussion|tribal\s+drums?|congas?|bongos?|hand\s+percussion|shakers?|tambourines?|clave|wood\s+hits?|toms?)\b/.test(text)) {
    layers.push('continuous fast tribal percussion');
  }
  if (!layers.length) return '';
  return `requested layers detected: ${layers.join(', ')}; these are promoted into the ACE caption, but ACE may still ignore small layers`;
}

function truthyCheckbox(value) {
  return value === true
    || value === 1
    || value === '1'
    || value === 'true'
    || value === 'on'
    || value === 'checked';
}

function collectFiles(run) {
  const exportsDir = path.join(run.input.outputDir, 'exports');
  const packageDir = path.join(run.input.outputDir, 'suno-proxy-package');
  const candidates = [];
  for (let index = 1; index <= 6; index += 1) {
    const candidate = path.join(exportsDir, `candidate-${index}.wav`);
    if (fs.existsSync(candidate)) candidates.push(candidate);
  }
  run.files = {
    outputDir: run.input.outputDir,
    exportsDir: fs.existsSync(exportsDir) ? exportsDir : null,
    candidates,
    manifest: exists(path.join(exportsDir, 'candidate-manifest.json')),
    geminiBrief: exists(path.join(run.input.outputDir, 'gemini-ace-brief.json')),
    preflight: exists(path.join(exportsDir, 'ace-preflight.json')),
    referenceSection: exists(path.join(exportsDir, 'reference-section.wav')),
    sunoPackageDir: fs.existsSync(packageDir) ? packageDir : null,
    sunoUploadWav: exists(path.join(packageDir, 'suno-upload-proxy.wav')),
    sunoUploadMp3: exists(path.join(packageDir, 'suno-upload-proxy.mp3')),
    sunoPrompt: exists(path.join(packageDir, 'suno-proxy-prompt.md')),
  };
  collectDebugArtifacts(run, exportsDir);
}

function collectDebugArtifacts(run, exportsDir) {
  if (!run.reportedArtifacts) run.reportedArtifacts = {};

  const promptPath = path.join(exportsDir, 'ace-effective-prompt.txt');
  if (!run.reportedArtifacts.effectivePrompt && fs.existsSync(promptPath)) {
    run.reportedArtifacts.effectivePrompt = true;
    const prompt = fs.readFileSync(promptPath, 'utf8').replace(/\s+/g, ' ').trim();
    addEvent(run, 'trace', `effective ACE prompt: ${truncate(prompt, 900)}`);
    addEvent(run, 'trace', `effective ACE prompt file: ${promptPath}`);
  }

  const manifestPath = path.join(exportsDir, 'candidate-manifest.json');
  if (!run.reportedArtifacts.manifest && fs.existsSync(manifestPath)) {
    run.reportedArtifacts.manifest = true;
    try {
      const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
      const sim = manifest.similarity || {};
      addEvent(
        run,
        'trace',
        `effective ACE controls: level=${sim.level || 'unknown'}; task=${sim.task_type || 'unknown'}; requested_similarity=${fmt(sim.target_similarity)}; effective_similarity=${fmt(sim.reference_similarity)}; reference_guidance=${fmt(sim.audio_cover_strength)}; audio_start_amount=${fmt(sim.cover_noise_strength)}; steps=${fmt(sim.inference_steps)}; guidance=${fmt(sim.guidance_scale)}; seed=${fmt(sim.seed)}; reconstruction_diagnostic=${sim.reconstruction_diagnostic === true ? 'on' : 'off'}`
      );
      const candidates = Array.isArray(manifest.candidates) ? manifest.candidates : [];
      if (candidates.length) {
        addEvent(run, 'trace', `candidate metrics: ${candidateMetrics(candidates)}`);
      }
      addEvent(run, 'trace', `candidate manifest file: ${manifestPath}`);
    } catch (error) {
      addEvent(run, 'warning', `Could not read candidate manifest debug info: ${error.message || String(error)}`);
    }
  }
}

function candidateMetrics(candidates) {
  return candidates.map((candidate) => {
    const q = candidate.quality || {};
    const refDetails = q.reference_similarity_details || {};
    const referenceSimilarity = refDetails.score ?? q.reference_similarity;
    const gate = q.level_gate || {};
    const gateText = gate.passed === false ? 'fail' : 'pass';
    return `c${candidate.index}: quality=${fmt(q.score)} selection=${fmt(q.selection_score)} groove=${fmt(referenceSimilarity)} gate=${gateText}`;
  }).join('; ');
}

function fmt(value) {
  const number = Number.parseFloat(value);
  return Number.isFinite(number) ? number.toFixed(3) : 'n/a';
}

function truncate(value, limit) {
  const text = String(value || '');
  if (text.length <= limit) return text;
  return text.slice(0, limit - 1).trimEnd() + '…';
}

function updateRun(run, status, progress, step) {
  run.status = status;
  run.progress = Math.max(0, Math.min(100, Math.round(progress)));
  run.step = step;
  run.updatedAt = new Date().toISOString();
}

function addEvent(run, type, message) {
  const at = new Date().toISOString();
  const started = run.createdAt ? new Date(run.createdAt).getTime() : Date.now();
  run.events.push({ at, type, message, runId: run.id, elapsedMs: Math.max(0, Date.now() - started) });
  run.events = run.events.slice(-500);
}

function failRun(run, message) {
  updateRun(run, 'failed', 100, 'Failed');
  run.error = message;
  addEvent(run, 'error', message);
}

function normalizeLevel(value) {
  const level = String(value || '').trim().toLowerCase();
  return LEVELS.has(level) ? level : 'medium-high';
}

function clampNumber(value, min, max, fallback) {
  const parsed = Number.parseFloat(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(min, Math.min(max, parsed));
}

function exists(file) {
  return fs.existsSync(file) ? file : null;
}

function pickPath(type) {
  const script = type === 'folder'
    ? 'POSIX path of (choose folder with prompt "Choose output folder:")'
    : 'POSIX path of (choose file with prompt "Choose reference track:")';
  return new Promise((resolve) => {
    const child = spawn('osascript', ['-e', script], { stdio: ['ignore', 'pipe', 'pipe'] });
    let out = '';
    child.stdout.on('data', (chunk) => { out += chunk.toString(); });
    child.on('exit', () => resolve(out.trim() || null));
    child.on('error', () => resolve(null));
  });
}

function shellish(value) {
  const text = String(value);
  return /[\s"']/g.test(text) ? JSON.stringify(text) : text;
}

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
  });
  res.end(body);
}

async function readBody(req) {
  let body = '';
  for await (const chunk of req) body += chunk;
  return body ? JSON.parse(body) : {};
}

function safeRepoPath(filePath) {
  const resolved = path.resolve(String(filePath || ''));
  if (resolved.startsWith(repoRoot + path.sep)) return resolved;
  for (const run of runs.values()) {
    const outDir = run.input && run.input.outputDir;
    if (outDir && resolved.startsWith(outDir + path.sep)) return resolved;
  }
  return null;
}

function serveFile(req, res, filePath) {
  const safePath = safeRepoPath(filePath);
  if (!safePath || !fs.existsSync(safePath)) {
    sendJson(res, 404, { error: 'File not found.' });
    return;
  }
  const ext = path.extname(safePath).toLowerCase();
  const type = ext === '.wav' ? 'audio/wav' : ext === '.mp3' ? 'audio/mpeg' : ext === '.md' ? 'text/markdown; charset=utf-8' : 'application/octet-stream';
  const fileSize = fs.statSync(safePath).size;
  const rangeHeader = req.headers.range;

  if (rangeHeader) {
    const [startStr, endStr] = rangeHeader.replace(/bytes=/, '').split('-');
    const start = parseInt(startStr, 10);
    const end = endStr ? parseInt(endStr, 10) : fileSize - 1;
    res.writeHead(206, {
      'Content-Type': type,
      'Content-Range': `bytes ${start}-${end}/${fileSize}`,
      'Accept-Ranges': 'bytes',
      'Content-Length': end - start + 1,
    });
    fs.createReadStream(safePath, { start, end }).pipe(res);
  } else {
    res.writeHead(200, {
      'Content-Type': type,
      'Accept-Ranges': 'bytes',
      'Content-Length': fileSize,
    });
    fs.createReadStream(safePath).pipe(res);
  }
}

function createApp() {
  return createServer(async (req, res) => {
    try {
      const url = new URL(req.url, `http://${req.headers.host || '127.0.0.1'}`);
      if (req.method === 'GET' && url.pathname === '/') {
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end(html());
        return;
      }
      if (req.method === 'GET' && url.pathname === '/api/health') {
        sendJson(res, 200, {
          ok: true,
          pid: process.pid,
          startedAt: serverStartedAt,
          cwd: repoRoot,
          geminiKeyPresent: Boolean(process.env.GEMINI_API_KEY),
        });
        return;
      }
      if (req.method === 'GET' && url.pathname === '/api/ace/status') {
        sendJson(res, 200, await getAceStatusPayload());
        return;
      }
      if (req.method === 'GET' && url.pathname === '/api/ace/capabilities') {
        sendJson(res, 200, getAceCapabilities());
        return;
      }
      if (req.method === 'POST' && url.pathname === '/api/ace/start') {
        sendJson(res, 202, await startAceServer());
        return;
      }
      if (req.method === 'POST' && url.pathname === '/api/ace/stop') {
        const body = await readBody(req).catch(() => ({}));
        sendJson(res, 202, await stopAceServer({ managedOnly: Boolean(body.managedOnly) }));
        return;
      }
      if (req.method === 'POST' && url.pathname === '/api/ace/restart') {
        sendJson(res, 202, await restartAceServer());
        return;
      }
      if (req.method === 'POST' && url.pathname === '/api/pick-file') {
        sendJson(res, 200, { path: await pickPath('file') });
        return;
      }
      if (req.method === 'POST' && url.pathname === '/api/pick-folder') {
        sendJson(res, 200, { path: await pickPath('folder') });
        return;
      }
      if (req.method === 'POST' && url.pathname === '/api/runs') {
        const run = createRun(await readBody(req));
        sendJson(res, 202, serializeRun(run));
        return;
      }
      const runMatch = url.pathname.match(/^\/api\/runs\/([^/]+)$/);
      if (req.method === 'GET' && runMatch) {
        const run = runs.get(runMatch[1]);
        if (!run) sendJson(res, 404, { error: 'Run not found.' });
        else sendJson(res, 200, serializeRun(run));
        return;
      }
      if (req.method === 'GET' && url.pathname === '/file') {
        serveFile(req, res, url.searchParams.get('path'));
        return;
      }
      sendJson(res, 404, { error: 'Not found.' });
    } catch (error) {
      sendJson(res, 500, { error: error.message || String(error) });
    }
  });
}

function serializeRun(run) {
  collectFiles(run);
  return {
    id: run.id,
    createdAt: run.createdAt,
    status: run.status,
    progress: run.progress,
    step: run.step,
    input: run.input,
    files: run.files,
    error: run.error,
    events: run.events,
  };
}

function html() {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ACE Proxy Pipeline</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0c0f13;
      --surface: #141820;
      --surface-2: #1a1f28;
      --surface-3: #1f2632;
      --line: #252d3a;
      --text: #e2e8f0;
      --muted: #64748b;
      --muted-2: #94a3b8;
      --accent: #22c55e;
      --accent-dim: rgba(34,197,94,0.08);
      --accent-border: rgba(34,197,94,0.3);
      --warn: #f59e0b;
      --bad: #ef4444;
      --radius: 12px;
      --radius-sm: 7px;
      --footer-h: 54px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      font-size: 14px;
      line-height: 1.5;
      min-height: 100vh;
      padding-bottom: var(--footer-h);
    }

    /* ── Header ── */
    header {
      position: sticky; top: 0;
      display: flex; align-items: center; gap: 10px;
      padding: 0 22px; height: 52px;
      background: var(--bg);
      border-bottom: 1px solid var(--line);
      z-index: 40;
    }
    .logo-icon {
      width: 27px; height: 27px; border-radius: 7px;
      background: var(--accent);
      display: flex; align-items: center; justify-content: center; flex-shrink: 0;
    }
    h1 { font-size: 16px; font-weight: 700; letter-spacing: -0.2px; }
    .header-ace { margin-left: auto; display: flex; align-items: center; gap: 6px; }
    .pill {
      display: inline-flex; align-items: center;
      padding: 3px 9px; border-radius: 99px;
      font-size: 11px; font-weight: 700;
      background: var(--surface-3); border: 1px solid var(--line); color: var(--muted);
      white-space: nowrap; cursor: default;
    }
    .pill.running { color: #052010; background: var(--accent); border-color: var(--accent); }
    .pill.starting, .pill.stopping, .pill.busy { color: #2a1a00; background: var(--warn); border-color: var(--warn); }
    .pill.failed { color: #fff; background: var(--bad); border-color: var(--bad); }
    .btn-ace {
      border: 1px solid var(--line); border-radius: 5px; background: var(--surface-3);
      color: var(--muted-2); padding: 4px 9px; font: inherit; font-size: 11px; font-weight: 600;
      cursor: pointer; transition: opacity 0.15s;
    }
    .btn-ace:hover { opacity: 0.75; }

    /* ── Main ── */
    main { padding: 30px 22px 14px; }
    .form-wrap { max-width: 560px; margin: 0 auto; }
    .section-label {
      font-size: 10px; font-weight: 600; color: var(--muted);
      text-transform: uppercase; letter-spacing: 0.8px;
      margin-bottom: 16px;
    }

    /* ── Fields ── */
    .field { margin-top: 13px; }
    .field-label { display: block; font-size: 12px; font-weight: 500; color: var(--muted-2); margin-bottom: 6px; }
    input[type="text"], input[type="number"], textarea, select {
      width: 100%; background: var(--surface-2); border: 1px solid var(--line);
      border-radius: var(--radius-sm); color: var(--text);
      padding: 8px 10px; font: inherit; font-size: 13px; outline: none;
      transition: border-color 0.15s;
    }
    input[type="text"]:focus, input[type="number"]:focus, textarea:focus, select:focus { border-color: var(--accent); }
    input[type="number"] { -moz-appearance: textfield; }
    input[type="number"]::-webkit-inner-spin-button,
    input[type="number"]::-webkit-outer-spin-button { -webkit-appearance: none; }
    textarea { min-height: 66px; resize: vertical; }
    select {
      cursor: pointer; appearance: none; -webkit-appearance: none;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 10 10'%3E%3Cpath fill='%2364748b' d='M5 7L1 3h8L5 7z'/%3E%3C/svg%3E");
      background-repeat: no-repeat; background-position: right 9px center; padding-right: 26px;
    }
    .row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }
    .slider-row { display: grid; grid-template-columns: 1fr 56px; gap: 10px; align-items: center; margin-top: 6px; }
    input[type="range"] {
      width: 100%; padding: 0; accent-color: var(--accent); cursor: pointer; border: none;
      background: linear-gradient(to right, #22c55e 0%, #22c55e 42%, #f59e0b 58%, #ef4444 100%);
      border-radius: 999px;
    }
    .slider-number { width: 56px !important; text-align: center; padding: 5px 6px !important; font-size: 12px !important; font-variant-numeric: tabular-nums; }
    .risk-label { margin-left: 6px; font-size: 10px; font-weight: 700; letter-spacing: 0.02em; text-transform: uppercase; }
    .risk-safe { color: #4ade80; }
    .risk-medium { color: #fbbf24; }
    .risk-high { color: #f87171; }

    /* ── Drop zones ── */
    .drop-zone {
      border: 1.5px dashed var(--line); border-radius: var(--radius); padding: 14px;
      transition: border-color 0.18s, background 0.18s; background: var(--surface-2);
    }
    .drop-zone.drag-over { border-color: var(--accent); background: var(--accent-dim); }
    .drop-zone.has-value { border-color: var(--accent-border); border-style: solid; }
    .dz-header { display: flex; align-items: center; gap: 10px; margin-bottom: 9px; }
    .dz-icon { color: var(--muted); flex-shrink: 0; transition: color 0.18s; }
    .drop-zone.has-value .dz-icon { color: var(--accent); }
    .dz-title { font-size: 13px; font-weight: 600; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .dz-hint { font-size: 11px; color: var(--muted); margin-top: 1px; }

    /* ── Misc ── */
    .divider { height: 1px; background: var(--line); margin: 20px 0; }
    .check-row { display: flex; align-items: center; gap: 8px; margin-top: 13px; cursor: pointer; }
    .check-row input[type="checkbox"] { width: 15px; height: 15px; accent-color: var(--accent); cursor: pointer; }
    .check-row span { font-size: 13px; color: var(--muted-2); }
    .check-sm { display: flex; align-items: center; gap: 6px; margin-top: 9px; cursor: pointer; }
    .check-sm input[type="checkbox"] { width: 13px; height: 13px; accent-color: var(--accent); cursor: pointer; }
    .check-sm span { font-size: 11px; color: var(--muted); }
    .btn-row { display: flex; gap: 8px; margin-top: 18px; }
    .btn-primary, .btn-secondary {
      border: none; border-radius: var(--radius-sm);
      padding: 11px 16px; font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; transition: opacity 0.15s;
    }
    .btn-primary { background: var(--accent); color: #052010; flex: 1; }
    .btn-secondary { background: var(--surface-3); color: var(--muted-2); border: 1px solid var(--line); }
    .btn-primary:disabled, .btn-secondary:disabled { opacity: 0.45; cursor: not-allowed; }
    .btn-primary:not(:disabled):hover, .btn-secondary:not(:disabled):hover { opacity: 0.85; }
    .hint { font-size: 11px; color: var(--muted); line-height: 1.5; margin-top: 14px; }

    /* ── Sticky progress footer ── */
    .progress-footer {
      position: fixed; bottom: 0; left: 0; right: 0;
      height: var(--footer-h);
      background: var(--surface); border-top: 1px solid var(--line);
      display: flex; align-items: center; gap: 14px; padding: 0 18px;
      z-index: 110;
    }
    .pf-step {
      font-size: 12px; font-weight: 600; color: var(--text);
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      min-width: 48px; max-width: 200px; flex-shrink: 0;
    }
    .pf-track { flex: 1; height: 4px; border-radius: 99px; background: var(--surface-3); overflow: hidden; }
    .pf-fill {
      height: 100%; width: 0%;
      background: linear-gradient(90deg, var(--accent), #38bdf8);
      border-radius: 99px; transition: width 0.35s ease;
    }
    .pf-right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
    .pf-pct { font-size: 12px; color: var(--muted); font-variant-numeric: tabular-nums; min-width: 34px; text-align: right; }
    .pf-logs-btn {
      display: flex; align-items: center; gap: 5px;
      border: 1px solid var(--line); border-radius: var(--radius-sm);
      background: var(--surface-2); color: var(--muted-2);
      padding: 5px 11px; font: inherit; font-size: 12px; font-weight: 600;
      cursor: pointer; transition: all 0.15s; white-space: nowrap;
    }
    .pf-logs-btn:hover { opacity: 0.8; }
    .pf-logs-btn.active { color: var(--accent); border-color: var(--accent-border); background: var(--accent-dim); }
    .pf-logs-btn.running { color: var(--accent); border-color: var(--accent-border); animation: pulse-btn 1.8s ease-in-out infinite; }
    @keyframes pulse-btn { 0%,100% { opacity: 1; } 50% { opacity: 0.55; } }

    /* ── Backdrop ── */
    .backdrop {
      position: fixed; inset: 0;
      background: rgba(0,0,0,0.5);
      opacity: 0; pointer-events: none;
      transition: opacity 0.28s; z-index: 90;
    }
    .backdrop.visible { opacity: 1; pointer-events: auto; }

    /* ── Bottom sheet ── */
    .bottom-sheet {
      position: fixed; bottom: var(--footer-h); left: 0; right: 0;
      height: 62vh; min-height: 320px;
      background: var(--surface);
      border-radius: 16px 16px 0 0;
      box-shadow: 0 -1px 0 var(--line), 0 -8px 32px rgba(0,0,0,0.4);
      transform: translateY(100%);
      transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      z-index: 100; display: flex; flex-direction: column;
    }
    .bottom-sheet.open { transform: translateY(0); }
    .sheet-pull {
      flex-shrink: 0; display: flex; flex-direction: column; align-items: center;
      padding: 10px 0 8px; cursor: pointer;
    }
    .sheet-pull-bar { width: 36px; height: 4px; border-radius: 99px; background: var(--line); }
    .sheet-header {
      flex-shrink: 0; display: flex; align-items: center; justify-content: space-between;
      padding: 0 18px 10px; border-bottom: 1px solid var(--line);
    }
    .sheet-title { font-size: 14px; font-weight: 700; }
    .sheet-close {
      border: none; background: none; color: var(--muted); font-size: 18px;
      line-height: 1; padding: 2px 6px; border-radius: 4px; cursor: pointer; transition: color 0.15s;
    }
    .sheet-close:hover { color: var(--text); }
    .sheet-body { flex: 1; overflow-y: auto; padding: 16px 18px 24px; }

    /* ── Events + files (inside sheet) ── */
    .error-text { color: var(--bad); font-size: 12px; margin-bottom: 12px; }
    .events { list-style: none; }
    .events li {
      padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,0.04);
      font-size: 11px; display: flex; gap: 8px; align-items: baseline;
    }
    .events li:last-child { border-bottom: none; }
    .ev-type { font-weight: 700; color: var(--muted-2); flex-shrink: 0; }
    .ev-type.progress, .ev-type.done { color: var(--accent); }
    .ev-type.warning { color: var(--warn); }
    .ev-type.error { color: var(--bad); }
    .ev-type.trace { color: #38bdf8; }
    .ev-msg { color: var(--muted-2); overflow-wrap: anywhere; }
    .ev-type.error { color: var(--bad); }
    .ev-type.warning { color: var(--warn); }
    .ev-type.done { color: var(--accent); }
    .ev-msg { color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .files { display: grid; gap: 10px; margin-top: 16px; }
    .file-card { border: 1px solid var(--line); border-radius: var(--radius-sm); padding: 10px; background: var(--surface-2); }
    .file-label { font-size: 11px; font-weight: 600; color: var(--muted-2); margin-bottom: 6px; }
    audio { width: 100%; height: 32px; display: block; }

    @media (max-width: 600px) {
      header { padding: 0 14px; }
      main { padding: 20px 14px 12px; }
      .header-ace .btn-ace { display: none; }
    }
  </style>
</head>
<body>

<header>
  <div class="logo-icon">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#052010" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
      <path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>
    </svg>
  </div>
  <h1>ACE Proxy Pipeline</h1>
  <div class="header-ace">
    <span id="aceStatus" class="pill" title="">...</span>
    <button id="aceStart" class="btn-ace" type="button">Start</button>
    <button id="aceStop" class="btn-ace" type="button">Stop</button>
    <button id="aceRestart" class="btn-ace" type="button">Restart</button>
  </div>
</header>

<main>
  <div class="form-wrap">
    <div class="section-label">Generate Proxy</div>

    <div class="drop-zone" id="refDropZone">
      <div class="dz-header">
        <svg class="dz-icon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>
        </svg>
        <div style="overflow:hidden;min-width:0">
          <div class="dz-title" id="refDropTitle">Drop reference track here</div>
          <div class="dz-hint" id="refDropHint">Drag audio file from Finder &mdash; or paste path below</div>
        </div>
      </div>
      <input id="reference" type="text" value="/Users/danilulmashev/Documents/GitHub/prompt2midi/test/fixtures/MJ-testing.m4a">
    </div>

    <div class="field">
      <label class="field-label" for="prompt">Prompt direction</label>
      <textarea id="prompt">same tempo and key area as the reference.</textarea>
    </div>

    <div class="divider"></div>

    <div class="row-2">
      <div>
        <label class="field-label" for="similarity">Similarity</label>
        <select id="similarity">
          <option>low</option><option>medium-low</option><option>medium</option>
          <option selected>medium-high</option><option>high</option><option>very-high</option><option>near-identical</option>
        </select>
      </div>
      <div>
        <label class="field-label" for="referenceStart">Ref start (s)</label>
        <input id="referenceStart" type="number" min="0" step="0.5" value="8">
      </div>
    </div>

    <div class="row-2" style="margin-top:10px">
      <div>
        <label class="field-label" for="duration">Duration (s)</label>
        <input id="duration" type="number" min="10" max="45" step="1" value="30">
      </div>
      <div>
        <label class="field-label" for="candidates">Candidates</label>
        <input id="candidates" type="number" min="1" max="4" step="1" value="4">
      </div>
    </div>

    <div class="field">
      <label class="field-label">Reference guidance &mdash; <span id="refLabel" style="color:var(--text);font-variant-numeric:tabular-nums">0.32</span></label>
      <div class="slider-row">
        <input id="referenceStrength" type="range" min="0" max="1" step="0.01" value="0.32">
        <input id="referenceStrengthNumber" class="slider-number" type="number" min="0" max="1" step="0.01" value="0.32">
      </div>
    </div>

    <div class="field">
      <label class="field-label">Audio start amount &mdash; <span id="noiseLabel" style="color:var(--text);font-variant-numeric:tabular-nums">0.14</span></label>
      <div class="slider-row">
        <input id="coverNoiseStrength" type="range" min="0" max="1" step="0.01" value="0.14">
        <input id="coverNoiseStrengthNumber" class="slider-number" type="number" min="0" max="1" step="0.01" value="0.14">
      </div>
    </div>

    <div class="field">
      <label class="field-label">Steps &mdash; <span id="stepsLabel" style="color:var(--text);font-variant-numeric:tabular-nums">12</span></label>
      <div class="slider-row">
        <input id="aceSteps" type="range" min="1" max="100" step="1" value="12">
        <input id="aceStepsNumber" class="slider-number" type="number" min="1" max="100" step="1" value="12">
      </div>
    </div>

    <div class="field">
      <label class="field-label">Guidance &mdash; <span id="guidanceLabel" style="color:var(--text);font-variant-numeric:tabular-nums">7.0</span></label>
      <div class="slider-row">
        <input id="aceGuidance" type="range" min="1" max="20" step="0.1" value="7">
        <input id="aceGuidanceNumber" class="slider-number" type="number" min="1" max="20" step="0.1" value="7">
      </div>
    </div>

    <div class="field">
      <label class="field-label">Seed &mdash; <span id="seedLabel" style="color:var(--text);font-variant-numeric:tabular-nums">-1</span></label>
      <div class="slider-row">
        <input id="aceSeed" type="range" min="-1" max="999999" step="1" value="-1">
        <input id="aceSeedNumber" class="slider-number" type="number" min="-1" max="999999" step="1" value="-1">
      </div>
    </div>

    <div class="divider"></div>

    <div class="drop-zone" id="outDropZone" style="padding:11px 13px">
      <div class="dz-header" style="margin-bottom:8px">
        <svg class="dz-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>
        </svg>
        <div style="overflow:hidden;min-width:0">
          <div class="dz-title" id="outDropTitle">Drop output folder here</div>
          <div class="dz-hint" id="outDropHint">or type a name (saved inside tmp/)</div>
        </div>
      </div>
      <input id="outputName" type="text" placeholder="optional, defaults to ace-ui-reference-date">
    </div>

    <label class="check-row">
      <input id="vocals" type="checkbox" checked>
      <span>Vocals / hook role enabled</span>
    </label>

    <label class="check-row">
      <input id="geminiBrief" type="checkbox">
      <span>Gemini smart ACE brief</span>
    </label>

    <label class="check-row">
      <input id="geminiControl" type="checkbox">
      <span>Experimental: let Gemini suggest ACE controls</span>
    </label>
    <p class="hint">Gemini uses local analysis + your direction to write a better ACE brief. Control mode is experimental and clamps suggestions to the safe slider ranges.</p>

    <div class="btn-row">
      <button class="btn-primary" id="run">Run Pipeline</button>
      <button class="btn-secondary" id="reset" type="button">Reset</button>
    </div>

    <label class="check-sm">
      <input id="autoStopAce" type="checkbox" checked>
      <span>Stop UI-managed ACE server when this tab closes</span>
    </label>
    <p class="hint">Fast ACE proxy lane only &mdash; skips MIDI, stems, bass scaffolds, MusicGen, and arrangement generation.</p>
  </div>
</main>

<!-- Sticky footer -->
<div class="progress-footer">
  <span id="step" class="pf-step">Idle</span>
  <div class="pf-track"><div id="bar" class="pf-fill"></div></div>
  <div class="pf-right">
    <span id="percent" class="pf-pct">0%</span>
    <button class="pf-logs-btn" id="logsBtn" type="button">
      <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
        <path d="M2 4h12M2 8h12M2 12h8"/>
      </svg>
      Logs
    </button>
  </div>
</div>

<!-- Backdrop -->
<div class="backdrop" id="backdrop"></div>

<!-- Bottom sheet -->
<div class="bottom-sheet" id="bottomSheet">
  <div class="sheet-pull" id="sheetPull"><div class="sheet-pull-bar"></div></div>
  <div class="sheet-header">
    <span class="sheet-title">Run Log</span>
    <button class="sheet-close" id="sheetClose" type="button">&times;</button>
  </div>
  <div class="sheet-body">
    <div id="error" class="error-text"></div>
    <ul id="events" class="events"></ul>
    <div id="files" class="files"></div>
  </div>
</div>

<script>
var droppedOutputDir = null;
var currentRun = null;
var timer = null;
var aceTimer = null;
var sheetOpen = false;

// ── Sheet ──
function openSheet() {
  document.getElementById('bottomSheet').classList.add('open');
  document.getElementById('backdrop').classList.add('visible');
  document.getElementById('logsBtn').classList.add('active');
  sheetOpen = true;
}
function closeSheet() {
  document.getElementById('bottomSheet').classList.remove('open');
  document.getElementById('backdrop').classList.remove('visible');
  document.getElementById('logsBtn').classList.remove('active');
  sheetOpen = false;
}
function toggleSheet() { if (sheetOpen) closeSheet(); else openSheet(); }

document.getElementById('logsBtn').addEventListener('click', toggleSheet);
document.getElementById('sheetClose').addEventListener('click', closeSheet);
document.getElementById('sheetPull').addEventListener('click', closeSheet);
document.getElementById('backdrop').addEventListener('click', closeSheet);

// ── Drop path helper (Finder drag on macOS) ──
function getDropPath(e) {
  var uriList = e.dataTransfer.getData('text/uri-list');
  if (!uriList) return null;
  var lines = uriList.split('\\n');
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i].trim();
    if (line.slice(0, 7) === 'file://') {
      var raw = line.slice(7);
      if (raw.length > 0 && raw.charCodeAt(raw.length - 1) === 13) raw = raw.slice(0, -1);
      return decodeURIComponent(raw);
    }
  }
  return null;
}

// ── File drop zone ──
function setupFileDropZone(zoneId, inputId, titleId, hintId) {
  var zone = document.getElementById(zoneId);
  var input = document.getElementById(inputId);
  var title = document.getElementById(titleId);
  var hint = document.getElementById(hintId);
  var defTitle = title.textContent;
  var defHint = hint.textContent;

  function applyPath(p) {
    input.value = p;
    title.textContent = p.split('/').pop() || p;
    hint.textContent = p;
    zone.classList.add('has-value');
  }

  function onDragOver(e) { e.preventDefault(); zone.classList.add('drag-over'); }
  function onDragLeave() { zone.classList.remove('drag-over'); }
  function onDrop(e) {
    e.preventDefault(); zone.classList.remove('drag-over');
    var p = getDropPath(e);
    if (p) { applyPath(p); return; }
    var files = e.dataTransfer.files;
    if (files.length > 0) { title.textContent = files[0].name; hint.textContent = 'Path not accessible — verify below'; zone.classList.add('has-value'); }
  }
  zone.addEventListener('dragover', onDragOver);
  zone.addEventListener('dragleave', onDragLeave);
  zone.addEventListener('drop', onDrop);
  input.addEventListener('dragover', onDragOver);
  input.addEventListener('dragleave', onDragLeave);
  input.addEventListener('drop', onDrop);
  input.addEventListener('input', function() {
    if (input.value.trim()) { title.textContent = input.value.trim().split('/').pop() || input.value.trim(); hint.textContent = input.value.trim(); zone.classList.add('has-value'); }
    else { title.textContent = defTitle; hint.textContent = defHint; zone.classList.remove('has-value'); }
  });
  if (input.value.trim()) applyPath(input.value.trim());
}

// ── Folder drop zone ──
function setupFolderDropZone(zoneId, inputId, titleId, hintId) {
  var zone = document.getElementById(zoneId);
  var input = document.getElementById(inputId);
  var title = document.getElementById(titleId);
  var hint = document.getElementById(hintId);
  var defTitle = title.textContent;
  var defHint = hint.textContent;

  function onFolderDragOver(e) { e.preventDefault(); zone.classList.add('drag-over'); }
  function onFolderDragLeave() { zone.classList.remove('drag-over'); }
  function onFolderDrop(e) {
    e.preventDefault(); zone.classList.remove('drag-over');
    var p = getDropPath(e);
    if (p) {
      droppedOutputDir = p;
      var name = p.split('/').pop() || p;
      title.textContent = name; hint.textContent = p; input.value = name;
      zone.classList.add('has-value');
    }
  }
  zone.addEventListener('dragover', onFolderDragOver);
  zone.addEventListener('dragleave', onFolderDragLeave);
  zone.addEventListener('drop', onFolderDrop);
  input.addEventListener('dragover', onFolderDragOver);
  input.addEventListener('dragleave', onFolderDragLeave);
  input.addEventListener('drop', onFolderDrop);
  input.addEventListener('input', function() {
    droppedOutputDir = null;
    if (input.value.trim()) zone.classList.add('has-value');
    else { title.textContent = defTitle; hint.textContent = defHint; zone.classList.remove('has-value'); }
  });
}

setupFileDropZone('refDropZone', 'reference', 'refDropTitle', 'refDropHint');
setupFolderDropZone('outDropZone', 'outputName', 'outDropTitle', 'outDropHint');

// ── Sliders ──
function syncPair(rangeId, numberId, labelId, decimals = 2) {
  var range = document.getElementById(rangeId);
  var number = document.getElementById(numberId);
  var label = document.getElementById(labelId);
  function set(v) {
    var value = Number(v);
    range.value = value;
    number.value = value;
    label.textContent = value.toFixed(decimals);
    var pct = (value - Number(range.min)) / (Number(range.max) - Number(range.min));
    if (pct >= 0.72) range.style.accentColor = '#ef4444';
    else if (pct >= 0.45) range.style.accentColor = '#f59e0b';
    else range.style.accentColor = '#22c55e';
  }
  range.addEventListener('input', function() { set(range.value); });
  number.addEventListener('input', function() { set(number.value); });
  set(range.value);
}
syncPair('referenceStrength', 'referenceStrengthNumber', 'refLabel');
syncPair('coverNoiseStrength', 'coverNoiseStrengthNumber', 'noiseLabel');
syncPair('aceSteps', 'aceStepsNumber', 'stepsLabel', 0);
syncPair('aceGuidance', 'aceGuidanceNumber', 'guidanceLabel', 1);
syncPair('aceSeed', 'aceSeedNumber', 'seedLabel', 0);

document.getElementById('geminiControl').addEventListener('change', function() {
  if (this.checked) document.getElementById('geminiBrief').checked = true;
});

// ── Reset ──
document.getElementById('reset').addEventListener('click', function() {
  document.getElementById('similarity').value = 'medium-high';
  document.getElementById('referenceStart').value = '8';
  document.getElementById('duration').value = '30';
  document.getElementById('candidates').value = '4';
  document.getElementById('referenceStrength').value = document.getElementById('referenceStrengthNumber').value = '0.32';
  document.getElementById('coverNoiseStrength').value = document.getElementById('coverNoiseStrengthNumber').value = '0.14';
  document.getElementById('aceSteps').value = document.getElementById('aceStepsNumber').value = '12';
  document.getElementById('aceGuidance').value = document.getElementById('aceGuidanceNumber').value = '7';
  document.getElementById('aceSeed').value = document.getElementById('aceSeedNumber').value = '-1';
  document.getElementById('stepsLabel').textContent = '12';
  document.getElementById('guidanceLabel').textContent = '7.0';
  document.getElementById('seedLabel').textContent = '-1';
  document.getElementById('refLabel').textContent = '0.32';
  document.getElementById('noiseLabel').textContent = '0.14';
  document.getElementById('vocals').checked = true;
  document.getElementById('geminiBrief').checked = false;
  document.getElementById('geminiControl').checked = false;
  document.getElementById('prompt').value = 'same tempo and key area as the reference.';
});

// ── Run ──
document.getElementById('run').addEventListener('click', async function() {
  document.getElementById('run').disabled = true;
  document.getElementById('error').textContent = '';
  document.getElementById('events').innerHTML = '';
  document.getElementById('files').innerHTML = '';
  var payload = {
    reference: document.getElementById('reference').value,
    prompt: document.getElementById('prompt').value,
    similarityLevel: document.getElementById('similarity').value,
    referenceStart: Number(document.getElementById('referenceStart').value),
    duration: Number(document.getElementById('duration').value),
    candidates: Number(document.getElementById('candidates').value),
    referenceStrength: Number(document.getElementById('referenceStrength').value),
    coverNoiseStrength: Number(document.getElementById('coverNoiseStrength').value),
    aceSteps: Number(document.getElementById('aceSteps').value),
    aceGuidance: Number(document.getElementById('aceGuidance').value),
    aceSeed: Number(document.getElementById('aceSeed').value),
    vocals: document.getElementById('vocals').checked,
    geminiBrief: document.getElementById('geminiBrief').checked,
    geminiControl: document.getElementById('geminiControl').checked,
    outputName: document.getElementById('outputName').value,
    outputDir: droppedOutputDir || null,
  };
  try {
    var res = await fetch('/api/runs', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
    var run = await res.json();
    if (run.error) { document.getElementById('error').textContent = run.error; document.getElementById('run').disabled = false; openSheet(); return; }
    currentRun = run.id;
    render(run);
    openSheet();
    document.getElementById('logsBtn').classList.add('running');
    if (timer) clearInterval(timer);
    timer = setInterval(poll, 1500);
  } catch (err) {
    document.getElementById('error').textContent = err.message;
    document.getElementById('run').disabled = false;
    openSheet();
  }
});

// ── ACE controls ──
document.getElementById('aceStart').addEventListener('click', async function() {
  await fetch('/api/ace/start', { method: 'POST' }); pollAce();
});
document.getElementById('aceStop').addEventListener('click', async function() {
  await fetch('/api/ace/stop', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ managedOnly: false }) }); pollAce();
});
document.getElementById('aceRestart').addEventListener('click', async function() {
  await fetch('/api/ace/restart', { method: 'POST' }); pollAce();
});

async function pollAce() {
  var res = await fetch('/api/ace/status');
  var s = await res.json();
  var pill = document.getElementById('aceStatus');
  pill.className = 'pill ' + (s.status || 'unknown');
  pill.textContent = String(s.status || 'unknown').toUpperCase();
  pill.title = s.message || '';
}

// ── Poll + Render ──
async function poll() {
  if (!currentRun) return;
  var res = await fetch('/api/runs/' + currentRun);
  var run = await res.json();
  render(run);
  if (run.status === 'succeeded' || run.status === 'failed') {
    clearInterval(timer); timer = null;
    document.getElementById('run').disabled = false;
    document.getElementById('logsBtn').classList.remove('running');
  }
}

function render(run) {
  document.getElementById('bar').style.width = (run.progress || 0) + '%';
  document.getElementById('percent').textContent = (run.progress || 0) + '%';
  document.getElementById('step').textContent = run.step || run.status;
  document.getElementById('error').textContent = run.error || '';
  document.getElementById('events').innerHTML = (run.events || []).slice().reverse().map(function(ev) {
    return '<li><span class="ev-type ' + escapeHtml(ev.type) + '">' + escapeHtml(ev.type) + '</span><span class="ev-msg">' + escapeHtml(ev.message) + '</span></li>';
  }).join('');
  var files = run.files || {};
  var html = (files.candidates || []).map(function(file, i) {
    return '<div class="file-card"><div class="file-label">Candidate ' + (i + 1) + '</div><audio controls src="/file?path=' + encodeURIComponent(file) + '"></audio></div>';
  }).join('');
  if (files.sunoUploadWav) html += '<div class="file-card"><div class="file-label">Suno upload proxy</div><audio controls src="/file?path=' + encodeURIComponent(files.sunoUploadWav) + '"></audio></div>';
  document.getElementById('files').innerHTML = html;
}

function escapeHtml(value) {
  return String(value || '').replace(/[&<>"']/g, function(c) {
    return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c];
  });
}

// ── pagehide ──
window.addEventListener('pagehide', function() {
  if (!document.getElementById('autoStopAce').checked) return;
  if (navigator.sendBeacon) navigator.sendBeacon('/api/ace/stop', new Blob([JSON.stringify({ managedOnly: true })], { type: 'application/json' }));
});

// ── ACE status polling ──
(function() {
  var start = ${autoStartAce ? "fetch('/api/ace/start', { method: 'POST' })" : "Promise.resolve()"};
  start.finally(function() {
  pollAce();
  aceTimer = setInterval(pollAce, 10000);
  });
})();
</script>
</body>
</html>`;
}

createApp().listen(port, '127.0.0.1', () => {
  console.log(`ACE proxy UI running at http://127.0.0.1:${port}`);
  if (autoStartAce) {
    startAceServer().catch((error) => {
      aceState.status = 'failed';
      aceState.message = error.message || String(error);
    });
  } else {
    aceState.status = 'stopped';
    aceState.message = 'ACE auto-start disabled; start scripts/start-ace-step-model-api.sh in another terminal.';
  }
});

async function shutdown() {
  await stopAceServer({ managedOnly: true });
  process.exit(0);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
