#!/usr/bin/env node

const { spawn } = require('node:child_process');
const path = require('node:path');
const { prepareAudioForAnalysis, validateAudioPath } = require('../../backend/lib/audioInput');

const repoRoot = path.resolve(__dirname, '..', '..');
const ANALYSIS_PYTHON = process.env.PROMPT2MIDI_ANALYSIS_PYTHON || process.env.PROMPT2MIDI_PYTHON || 'python3';
const LEVELS = new Set(['low', 'medium-low', 'medium', 'medium-high', 'high', 'very-high', 'near-identical', 'identical']);

const STEP_PROGRESS = [
  [/preparing reference audio/i, 4],
  [/reading audio|feature extraction/i, 8],
  [/enhanced analysis/i, 14],
  [/external analysis/i, 20],
  [/beat grid/i, 24],
  [/loading CLAP genre model|Hugging Face cache/i, 31],
  [/running CLAP genre classifier/i, 32],
  [/detecting chord progression/i, 34],
  [/detecting arrangement structure/i, 35],
  [/deep analysis|detecting genre|chords|structure/i, 30],
  [/midi sketch/i, 36],
  [/heuristic bass|reference groove/i, 42],
  [/stem separation/i, 50],
  [/model transcription/i, 58],
  [/reference transform/i, 64],
  [/composition/i, 70],
  [/full arrangement: writing/i, 74],
  [/full arrangement guide: rendering section/i, 76],
  [/ace-step: effective controls/i, 78],
  [/ace-step: submitting/i, 80],
  [/ace-step: waiting/i, 84],
  [/ace-step: downloading candidate/i, 88],
  [/ace-step: scoring candidate/i, 91],
  [/audio generation/i, 94],
];

function makeProgressRenderer() {
  const isTTY = Boolean(process.stderr.isTTY);
  const machineReadable = process.env.PROMPT2MIDI_TRACE_PROGRESS === '1';
  const frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
  const animationMs = Math.max(120, Number.parseInt(process.env.PROMPT2MIDI_PROGRESS_ANIMATION_MS || '250', 10));
  const waitAnimationMs = Math.max(1000, Number.parseInt(process.env.PROMPT2MIDI_PROGRESS_WAIT_ANIMATION_MS || '5000', 10));
  const heartbeatMs = Math.max(5000, Number.parseInt(process.env.PROMPT2MIDI_PROGRESS_HEARTBEAT_MS || '15000', 10));

  // ANSI helpers — empty strings when not a TTY so plain text still works
  const C = isTTY
    ? { reset: '\x1b[0m', bold: '\x1b[1m', dim: '\x1b[2m',
        cyan: '\x1b[36m', green: '\x1b[32m', yellow: '\x1b[33m',
        red: '\x1b[31m', magenta: '\x1b[35m', blue: '\x1b[34m' }
    : Object.fromEntries(['reset','bold','dim','cyan','green','yellow','red','magenta','blue'].map(k => [k, '']));

  // Pick a color per step category based on keywords in the label
  function stepColor(text) {
    const t = text.toLowerCase();
    if (/stem|demucs|vocal strip/.test(t)) return C.yellow;
    if (/ace-step|ace step|generation|candidate/.test(t)) return C.green;
    if (/midi|bass|groove|chord|melody/.test(t)) return C.magenta;
    if (/instrument|production type/.test(t)) return C.blue;
    return C.cyan;
  }

  const startedAt = Date.now();
  const records = [];
  let current = null;
  let timer = null;
  let heartbeatTimer = null;
  let percent = 0;
  const allowAnimation = isTTY
    && process.env.PROMPT2MIDI_PROGRESS_ANIMATION !== '0'
    && !process.env.CI
    && !process.env.TERM_PROGRAM?.toLowerCase().includes('dumb');

  function clearLine() { process.stderr.write('\r\x1b[2K'); }

  function elapsedMs() {
    return Date.now() - startedAt;
  }

  function fmtMs(ms) {
    if (ms < 1000) return `${ms}ms`;
    const seconds = ms / 1000;
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ${(seconds - minutes * 60).toFixed(1)}s`;
  }

  function timestamp() {
    return new Date().toLocaleTimeString();
  }

  function progressFor(text) {
    const section = text.match(/full arrangement guide: rendering section\s+(\d+)\/(\d+)/i);
    if (section) {
      const index = Number.parseInt(section[1], 10);
      const total = Math.max(1, Number.parseInt(section[2], 10));
      return Math.max(percent, Math.min(92, 76 + ((index - 1) / total) * 16));
    }
    const candidate = text.match(/candidate\s+(\d+)/i);
    if (candidate && /ace-step/i.test(text)) {
      const index = Number.parseInt(candidate[1], 10);
      return Math.max(percent, Math.min(93, 86 + index * 2));
    }
    for (const [pattern, value] of STEP_PROGRESS) {
      if (pattern.test(text)) return Math.max(percent, value);
    }
    if (/waiting for task/i.test(text)) return Math.min(88, Math.max(percent, percent + 0.5));
    return Math.min(96, Math.max(percent, percent + 2));
  }

  function bar(value, frame = null) {
    const width = 20;
    const filled = Math.max(0, Math.min(width, Math.round((value / 100) * width)));
    const empty = width - filled;
    const pulse = frame === null || empty <= 0 ? -1 : filled + (frame % empty);
    let cells = '';
    for (let i = 0; i < width; i += 1) {
      if (i < filled) cells += `${C.green}█${C.reset}`;
      else if (i === pulse) cells += `${C.cyan}●${C.reset}`;
      else cells += `${C.dim}░${C.reset}`;
    }
    return `${C.dim}[${C.reset}${cells}${C.dim}]${C.reset}`;
  }

  function canonical(text) {
    if (/ace-step: waiting for task/i.test(text)) return 'ace-step: waiting for task';
    return text.replace(/[0-9a-f]{8}-[0-9a-f-]{27,}/ig, '<task>');
  }

  function currentLabel() {
    if (!current) return '';
    if (/ace-step: waiting for task/i.test(current.text) && current.updates > 1) {
      const match = current.text.match(/task\s+([0-9a-f-]+)/i);
      const task = match ? ` ${match[1].slice(0, 8)}` : '';
      return `ace-step: waiting for task${task} (${current.updates} polls)`;
    }
    return current.text;
  }

  function truncate(text, maxLength) {
    const value = String(text || '');
    if (value.length <= maxLength) return value;
    return `${value.slice(0, Math.max(1, maxLength - 1)).trimEnd()}…`;
  }

  function liveLine() {
    if (!current) return;
    const elapsed = fmtMs(Date.now() - current.startedAt);
    const columns = Math.max(60, Number(process.stderr.columns || 100));
    const fixedWidth = 52;
    const label = truncate(currentLabel(), Math.max(24, columns - fixedWidth));
    const icon = `${C.cyan}${frames[current.frame % frames.length]}${C.reset}`;
    return formatLine(icon, percent, elapsed, label, current.frame);
  }

  function formatLine(icon, value, elapsed, label, frame = null) {
    const pct = `${String(Math.round(value)).padStart(3)}%`;
    const time = String(elapsed || '').padStart(8);
    return `${icon} ${bar(value, frame)} ${pct} ${C.dim}${time}${C.reset}  ${label}`;
  }

  function renderCurrent() {
    if (!current) return;
    const elapsed = fmtMs(Date.now() - current.startedAt);
    if (!isTTY) {
      process.stderr.write(`${formatLine('⠋', percent, elapsed, currentLabel())}\n`);
      return;
    }
    clearLine();
    process.stderr.write(liveLine());
  }

  function startAnimation() {
    if (!allowAnimation || timer) {
      startHeartbeat();
      return;
    }
    const intervalMs = /ace-step: waiting for task/i.test(current?.text || '') ? waitAnimationMs : animationMs;
    timer = setInterval(() => {
      if (!current) return;
      current.frame += 1;
      renderCurrent();
    }, intervalMs);
  }

  function stopAnimation() {
    if (!timer) return;
    clearInterval(timer);
    timer = null;
  }

  function startHeartbeat() {
    if (isTTY || heartbeatTimer || process.env.PROMPT2MIDI_PROGRESS_HEARTBEAT === '0') return;
    heartbeatTimer = setInterval(() => {
      if (!current) return;
      current.frame += 1;
      process.stderr.write(`${formatLine(frames[current.frame % frames.length], percent, fmtMs(Date.now() - current.startedAt), currentLabel(), current.frame)}\n`);
    }, heartbeatMs);
  }

  function stopHeartbeat() {
    if (!heartbeatTimer) return;
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }

  function finishCurrent(success = true) {
    if (!current || !isTTY) return;
    const icon = success ? `${C.green}✓${C.reset}` : `${C.yellow}!${C.reset}`;
    const elapsed = fmtMs(Date.now() - current.startedAt);
    const columns = Math.max(60, Number(process.stderr.columns || 100));
    const label = truncate(currentLabel(), Math.max(24, columns - 52));
    process.stderr.write(
      `\r\x1b[2K${formatLine(icon, percent, elapsed, label)}\n`
    );
  }

  // Begin a new step. Rendering is event-driven, with no animation loop, so terminals
  // that preserve carriage returns do not fill with high-frequency spinner frames.
  function step(text) {
    if (machineReadable) {
      process.stderr.write(`progress: ${text}\n`);
      return;
    }
    const nextPercent = progressFor(text);
    const key = canonical(text);
    if (current && current.key === key) {
      current.text = text;
      current.updates += 1;
      percent = Math.max(percent, nextPercent);
      return;
    }
    done(true);
    percent = Math.max(percent, nextPercent);
    current = {
      key,
      text,
      startedAt: Date.now(),
      at: timestamp(),
      color: stepColor(text),
      updates: 1,
      percent,
      frame: 0,
    };
    renderCurrent();
    startAnimation();
  }

  // Mark the current step done (✓ green or ✗ red)
  function done(success = true) {
    if (!current) return;
    stopAnimation();
    stopHeartbeat();
    const durationMs = Date.now() - current.startedAt;
    records.push({
      label: currentLabel(),
      started_at: current.at,
      duration_ms: durationMs,
      percent: Math.round(percent),
      success,
    });
    finishCurrent(success);
    current = null;
  }

  function warn(line) {
    done(true);
    process.stderr.write(`${C.yellow}  ⚠  ${line}${C.reset}\n`);
  }

  function error(line) {
    done(false);
    process.stderr.write(`${C.red}  ✗  ${line}${C.reset}\n`);
  }

  function other(line) {
    done(true);
    process.stderr.write(`     ${line}\n`);
  }

  function summary(outputDir) {
    done(true);
    const totalMs = elapsedMs();
    const summaryPath = path.join(outputDir, 'pipeline-timings.json');
    const payload = {
      started_at: new Date(startedAt).toISOString(),
      finished_at: new Date().toISOString(),
      total_ms: totalMs,
      steps: records,
    };
    try {
      require('node:fs').writeFileSync(summaryPath, JSON.stringify(payload, null, 2) + '\n', 'utf8');
    } catch (_) {}
    process.stderr.write(`\n${C.bold}Performance summary${C.reset} ${C.dim}(timings saved to ${summaryPath})${C.reset}\n`);
    process.stderr.write(`${C.green}${bar(100)} 100%${C.reset} total ${C.bold}${fmtMs(totalMs)}${C.reset}\n`);
    for (const record of records) {
      process.stderr.write(
        `  ${String(record.percent).padStart(3)}%  ${record.started_at}  ${fmtMs(record.duration_ms).padStart(8)}  ${record.label}\n`
      );
    }
  }

  return { step, done, warn, error, other, summary };
}


async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printHelp();
    return 0;
  }

  const reference = args.reference || args.audio;
  const outputDir = args.outputDir || args.output;
  const prompt = args.prompt || '';
  const level = args.similarityLevel || args.level || '';
  const fastSample = Boolean(args.fastSample || args.fast);
  const fullArrangement = Boolean(args.fullArrangement || args.arrangementLock || args.fullGuide);

  if (!reference || !outputDir) {
    printHelp();
    return fail('Missing required --reference and --output-dir.');
  }
  if (!path.isAbsolute(reference)) {
    return fail('--reference must be an absolute path.');
  }
  if (level && !LEVELS.has(level)) {
    return fail('--similarity-level must be low, medium-low, medium, medium-high, high, very-high, near-identical, or identical.');
  }

  const validationError = await validateAudioPath(reference);
  if (validationError) {
    return fail(validationError.message);
  }

  const prepared = await prepareAudioForAnalysis(reference, outputDir);
  for (const warning of prepared.warnings || []) {
    console.error(`warning: ${warning}`);
  }

  const env = { ...process.env };
  if (level) env.PROMPT2MIDI_REFERENCE_SIMILARITY_LEVEL = level;
  if (args.ace || args.enableAceStep) env.PROMPT2MIDI_ENABLE_ACE_STEP = '1';
  if (fullArrangement) {
    env.PROMPT2MIDI_ENABLE_ACE_STEP = '1';
    env.PROMPT2MIDI_ENABLE_FULL_ACE_GUIDE = '1';
    env.PROMPT2MIDI_SKIP_REFERENCE_SAMPLE = '1';
    if (!env.PROMPT2MIDI_FULL_GUIDE_SIMILARITY_LEVEL) {
      env.PROMPT2MIDI_FULL_GUIDE_SIMILARITY_LEVEL = 'medium-low';
    }
  }
  if (args.allin1Docker) env.PROMPT2MIDI_ENABLE_ALLIN1_DOCKER = '1';
  if (args.vocals && args.instrumental) {
    return fail('Use either --vocals or --instrumental, not both.');
  }
  if (args.vocals) env.PROMPT2MIDI_ACE_STEP_FORCE_VOCALS = '1';
  if (args.instrumental) env.PROMPT2MIDI_ACE_STEP_FORCE_INSTRUMENTAL = '1';
  if (args.candidates) env.PROMPT2MIDI_ACE_STEP_CANDIDATES = args.candidates;
  if (args.steps) env.PROMPT2MIDI_ACE_STEP_STEPS = args.steps;
  if (args.guidance) env.PROMPT2MIDI_ACE_STEP_GUIDANCE = args.guidance;
  if (args.seed) env.PROMPT2MIDI_ACE_STEP_SEED = args.seed;
  if (args.duration || args.sampleDuration) env.PROMPT2MIDI_REFERENCE_SAMPLE_DURATION = args.duration || args.sampleDuration;
  if (args.referenceConditioningDuration) env.PROMPT2MIDI_REFERENCE_CONDITIONING_DURATION = args.referenceConditioningDuration;
  if (args.referenceStart) env.PROMPT2MIDI_REFERENCE_SECTION_START = args.referenceStart;
  if (args.referenceStrategy) env.PROMPT2MIDI_REFERENCE_SECTION_STRATEGY = args.referenceStrategy;
  if (args.selectCandidate) env.PROMPT2MIDI_ACE_STEP_SELECT_CANDIDATE = args.selectCandidate;
  if (args.autoSelect) env.PROMPT2MIDI_ACE_STEP_AUTO_SELECT = '1';
  if (args.controlScaffold) env.PROMPT2MIDI_ACE_STEP_CONTROL_SCAFFOLD = '1';
  if (args.noControlScaffold) env.PROMPT2MIDI_DISABLE_CONTROL_SCAFFOLD = '1';
  if (args.bassProxySource) env.PROMPT2MIDI_ACE_STEP_BASS_PROXY_REFERENCE = '1';

  const childArgs = [
    '-m', 'analysis.analyze',
    '--audio', prepared.analysisPath,
    '--output-dir', outputDir,
  ];
  if (level) childArgs.push('--similarity-level', level);
  if (prompt) childArgs.push('--user-prompt', prompt);
  if (fastSample) childArgs.push('--fast-sample');

  const renderer = makeProgressRenderer();
  const startTime = Date.now();
  const startLabel = new Date(startTime).toLocaleTimeString();

  const C = process.stderr.isTTY
    ? { reset: '\x1b[0m', bold: '\x1b[1m', dim: '\x1b[2m', cyan: '\x1b[36m', green: '\x1b[32m', yellow: '\x1b[33m' }
    : Object.fromEntries(['reset','bold','dim','cyan','green','yellow'].map(k => [k, '']));

  process.stderr.write(`${C.dim}started ${startLabel}${C.reset}\n`);

  return new Promise((resolve) => {
    const fs = require('node:fs');
    const outputJsonPath = require('node:path').join(outputDir, 'run-output.json');
    let stdoutBuf = '';

    const child = spawn(ANALYSIS_PYTHON, childArgs, {
      cwd: repoRoot,
      env,
      stdio: ['inherit', 'pipe', 'pipe'],
    });

    // Collect stdout silently — write to run-output.json, never print to terminal
    child.stdout.on('data', (chunk) => { stdoutBuf += chunk.toString(); });

    let buf = '';
    child.stderr.on('data', (chunk) => {
      buf += chunk.toString();
      const lines = buf.split('\n');
      buf = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        if (line.startsWith('progress: ')) {
          renderer.step(line.slice('progress: '.length));
        } else if (/^(warning|warn):/i.test(line)) {
          renderer.warn(line);
        } else if (/^(error|exception|traceback)/i.test(line)) {
          renderer.error(line);
        } else {
          renderer.other(line);
        }
      }
    });

    child.on('exit', (code, signal) => {
      if (buf.trim()) renderer.other(buf);
      renderer.done(code === 0);

      // Write stdout JSON to file
      if (stdoutBuf.trim()) {
        try { fs.writeFileSync(outputJsonPath, stdoutBuf, 'utf8'); } catch (_) {}
      }
      renderer.summary(outputDir);

      // Timing summary
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      const endLabel = new Date().toLocaleTimeString();
      process.stderr.write(
        `${C.dim}finished ${endLabel} — elapsed ${C.bold}${elapsed}s${C.reset}${C.dim} — output: ${outputDir}${C.reset}\n`
      );

      if (signal) process.kill(process.pid, signal);
      process.exitCode = code || 0;
      resolve(process.exitCode);
    });
    child.on('error', (err) => {
      renderer.done(false);
      resolve(fail(err.message));
    });
  });
}

function parseArgs(argv) {
  const parsed = {};
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--help' || arg === '-h') parsed.help = true;
    else if (arg === '--ace' || arg === '--enable-ace-step') parsed.enableAceStep = true;
    else if (arg === '--fast-sample' || arg === '--fast') parsed.fastSample = true;
    else if (arg === '--full-arrangement' || arg === '--arrangement-lock' || arg === '--full-guide') parsed.fullArrangement = true;
    else if (arg === '--vocals') parsed.vocals = true;
    else if (arg === '--instrumental') parsed.instrumental = true;
    else if (arg === '--control-scaffold') parsed.controlScaffold = true;
    else if (arg === '--no-control-scaffold') parsed.noControlScaffold = true;
    else if (arg === '--bass-proxy-source') parsed.bassProxySource = true;
    else if (arg === '--allin1-docker') parsed.allin1Docker = true;
    else if (arg.startsWith('--')) {
      const key = toCamel(arg.slice(2));
      const value = argv[index + 1];
      if (!value || value.startsWith('--')) fail(`Missing value for ${arg}.`);
      parsed[key] = value;
      index += 1;
    } else {
      fail(`Unknown argument: ${arg}`);
    }
  }
  return parsed;
}

function toCamel(name) {
  return name.replace(/-([a-z])/g, (_, char) => char.toUpperCase());
}

function fail(message) {
  console.error(`error: ${message}`);
  process.exitCode = 2;
  return 2;
}

function printHelp() {
  console.log(`Usage:
  npm run reference -- --reference "/absolute/path/to/song.wav" --output-dir tmp/my-run --similarity-level high --prompt "tight club mix, no vocals" --ace

Options:
  --reference <path>            Absolute WAV/MP3 reference path. MP3 requires ffmpeg.
  --output-dir <path>           Output directory for analysis, MIDI, prompt, arrangement map, and candidates.
  --prompt <text>               Creative direction added to detected metadata.
  --similarity-level <level>    Optional. low, medium-low, medium, medium-high, high, very-high, near-identical, or identical. Omit to let the prompt drive controls.
  --ace                         Enable ACE-Step generation; requires npm run ace-step:start in another terminal.
  --fast-sample                 Fast ACE calibration lane: skip stems, transcription, MIDI, and arrangement outputs.
  --full-arrangement            Render section-by-section full-length Arrangement Lock audio with ACE, stitch full-arrangement-guide.wav, and skip the short sample lane.
  --vocals                      Force a new original vocal-hook role in ACE, useful when fast lane skips vocal detection.
  --instrumental                Force instrumental ACE output even when the reference has vocals.
  --candidates <n>              ACE candidate count. Defaults to 4 normal candidates; max 6.
  --duration <seconds|full>     Generated candidate length. Defaults to 30 seconds; use full/reference for source length.
                               ACE-Step cannot reliably render past ~6:10 (370s); longer requests are clamped to that ceiling.
  --sample-duration <value>     Alias for --duration.
  --reference-conditioning-duration <seconds>
                               Use a shorter/longer source-conditioning window than the generated candidate length.
  --reference-start <seconds>   Force the local reference section used to condition ACE.
  --reference-strategy <name>   Section picker: stable_energy or early_character.
  --select-candidate <n>        Promote a specific generated candidate to sample.wav after auditioning.
  --auto-select <yes>           Use advisory quality scoring to create sample.wav automatically.
  --steps <n>                   ACE diffusion steps.
  --guidance <n>                ACE guidance scale.
  --seed <n|-1>                 ACE seed. -1 keeps random generation.
  --control-scaffold            Generate an in-key bass/drum control scaffold and use it as ACE's cover reference.
  --no-control-scaffold         Disable automatic scaffold routing for bass-lock prompts.
  --bass-proxy-source           Experimental diagnostic only. Uses high-passed reference + generated bass guide; automatically skipped for rich/vocal references unless PROMPT2MIDI_ALLOW_EXPERIMENTAL_RICH_BASS_PROXY=1.
  --allin1-docker               Run the optional All-In-One structure analyzer inside Docker. The pipeline still falls back to the internal beat-grid/section analyzer if Docker fails.

Every audio run writes these full-song SUNO control artifacts under <output-dir>/exports:
  arrangement-map.json
  analysis-report.md
  suno-structure-prompt.md
  full-arrangement-guide.mid

Optional analyzer/provider flags:
  PROMPT2MIDI_ALLIN1=/path/to/allin1
  PROMPT2MIDI_ENABLE_ALLIN1_DOCKER=1
  PROMPT2MIDI_ALLIN1_DOCKER_PLATFORM=linux/amd64
  PROMPT2MIDI_ESSENTIA_EXTRACTOR=/path/to/essentia_streaming_extractor_music
  PROMPT2MIDI_ENABLE_FULL_ACE_GUIDE=1  # render section-by-section full-arrangement-guide.wav with ACE`);
}

main().catch((error) => fail(error.message || String(error)));
