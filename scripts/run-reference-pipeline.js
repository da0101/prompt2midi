#!/usr/bin/env node

const { spawn } = require('node:child_process');
const path = require('node:path');
const { prepareAudioForAnalysis, validateAudioPath } = require('../backend/lib/audioInput');

const repoRoot = path.resolve(__dirname, '..');
const analyzeScript = path.join(repoRoot, 'analysis', 'analyze.py');
const ANALYSIS_PYTHON = process.env.PROMPT2MIDI_ANALYSIS_PYTHON || 'python3';
const LEVELS = new Set(['low', 'medium-low', 'medium', 'medium-high', 'high', 'very-high', 'near-identical', 'identical']);

function makeProgressRenderer() {
  const isTTY = Boolean(process.stderr.isTTY);
  const FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];

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

  let frame = 0;
  let current = '';
  let color = C.cyan;
  let timer = null;

  function clearLine() { process.stderr.write('\r\x1b[2K'); }

  function tick() {
    frame++;
    process.stderr.write(`\r\x1b[2K${color}${FRAMES[frame % FRAMES.length]}${C.reset} ${current}`);
  }

  // Begin a new step — completes the previous one as ✓
  function step(text) {
    done(true);
    current = text;
    color = stepColor(text);
    if (isTTY) {
      tick();
      timer = setInterval(tick, 80);
    } else {
      process.stderr.write(`  ◆ ${text}\n`);
    }
  }

  // Mark the current step done (✓ green or ✗ red)
  function done(success = true) {
    if (timer) { clearInterval(timer); timer = null; }
    if (!current) return;
    if (isTTY) {
      const icon = success ? `${C.green}✓${C.reset}` : `${C.yellow}!${C.reset}`;
      process.stderr.write(`\r\x1b[2K${icon} ${C.dim}${current}${C.reset}\n`);
    }
    current = '';
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

  return { step, done, warn, error, other };
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
  if (args.vocals && args.instrumental) {
    return fail('Use either --vocals or --instrumental, not both.');
  }
  if (args.vocals) env.PROMPT2MIDI_ACE_STEP_FORCE_VOCALS = '1';
  if (args.instrumental) env.PROMPT2MIDI_ACE_STEP_FORCE_INSTRUMENTAL = '1';
  if (args.candidates) env.PROMPT2MIDI_ACE_STEP_CANDIDATES = args.candidates;
  if (args.steps) env.PROMPT2MIDI_ACE_STEP_STEPS = args.steps;
  if (args.guidance) env.PROMPT2MIDI_ACE_STEP_GUIDANCE = args.guidance;
  if (args.duration || args.sampleDuration) env.PROMPT2MIDI_REFERENCE_SAMPLE_DURATION = args.duration || args.sampleDuration;
  if (args.referenceStart) env.PROMPT2MIDI_REFERENCE_SECTION_START = args.referenceStart;
  if (args.referenceStrategy) env.PROMPT2MIDI_REFERENCE_SECTION_STRATEGY = args.referenceStrategy;
  if (args.selectCandidate) env.PROMPT2MIDI_ACE_STEP_SELECT_CANDIDATE = args.selectCandidate;
  if (args.autoSelect) env.PROMPT2MIDI_ACE_STEP_AUTO_SELECT = '1';
  if (args.controlScaffold) env.PROMPT2MIDI_ACE_STEP_CONTROL_SCAFFOLD = '1';
  if (args.noControlScaffold) env.PROMPT2MIDI_DISABLE_CONTROL_SCAFFOLD = '1';
  if (args.bassProxySource) env.PROMPT2MIDI_ACE_STEP_BASS_PROXY_REFERENCE = '1';

  const childArgs = [
    analyzeScript,
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
    else if (arg === '--vocals') parsed.vocals = true;
    else if (arg === '--instrumental') parsed.instrumental = true;
    else if (arg === '--control-scaffold') parsed.controlScaffold = true;
    else if (arg === '--no-control-scaffold') parsed.noControlScaffold = true;
    else if (arg === '--bass-proxy-source') parsed.bassProxySource = true;
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
  --vocals                      Force a new original vocal-hook role in ACE, useful when fast lane skips vocal detection.
  --instrumental                Force instrumental ACE output even when the reference has vocals.
  --candidates <n>              ACE candidate count. Defaults to 4 normal candidates; max 6.
  --duration <seconds|full>     Generated candidate length. Defaults to 30 seconds; use full/reference for source length.
  --sample-duration <value>     Alias for --duration.
  --reference-start <seconds>   Force the local reference section used to condition ACE.
  --reference-strategy <name>   Section picker: stable_energy or early_character.
  --select-candidate <n>        Promote a specific generated candidate to sample.wav after auditioning.
  --auto-select <yes>           Use advisory quality scoring to create sample.wav automatically.
  --steps <n>                   ACE diffusion steps.
  --guidance <n>                ACE guidance scale.
  --control-scaffold            Generate an in-key bass/drum control scaffold and use it as ACE's cover reference.
  --no-control-scaffold         Disable automatic scaffold routing for bass-lock prompts.
  --bass-proxy-source           Experimental diagnostic only. Uses high-passed reference + generated bass guide; automatically skipped for rich/vocal references unless PROMPT2MIDI_ALLOW_EXPERIMENTAL_RICH_BASS_PROXY=1.

Every audio run writes these full-song SUNO control artifacts under <output-dir>/exports:
  arrangement-map.json
  analysis-report.md
  suno-structure-prompt.md
  full-arrangement-guide.mid

Optional analyzer/provider flags:
  PROMPT2MIDI_ALLIN1=/path/to/allin1
  PROMPT2MIDI_ESSENTIA_EXTRACTOR=/path/to/essentia_streaming_extractor_music
  PROMPT2MIDI_ENABLE_FULL_ACE_GUIDE=1  # render section-by-section full-arrangement-guide.wav with ACE`);
}

main().catch((error) => fail(error.message || String(error)));
