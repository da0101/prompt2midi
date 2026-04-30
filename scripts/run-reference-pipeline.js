#!/usr/bin/env node

const { spawn } = require('node:child_process');
const path = require('node:path');
const { prepareAudioForAnalysis, validateAudioPath } = require('../backend/lib/audioInput');

const repoRoot = path.resolve(__dirname, '..');
const analyzeScript = path.join(repoRoot, 'analysis', 'analyze.py');
const LEVELS = new Set(['low', 'medium-low', 'medium', 'medium-high', 'high', 'near-identical', 'identical']);

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printHelp();
    return 0;
  }

  const reference = args.reference || args.audio;
  const outputDir = args.outputDir || args.output;
  const prompt = args.prompt || '';
  const level = args.similarityLevel || args.level || 'medium';

  if (!reference || !outputDir) {
    printHelp();
    return fail('Missing required --reference and --output-dir.');
  }
  if (!path.isAbsolute(reference)) {
    return fail('--reference must be an absolute path.');
  }
  if (!LEVELS.has(level)) {
    return fail('--similarity-level must be low, medium-low, medium, medium-high, high, near-identical, or identical.');
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
  env.PROMPT2MIDI_REFERENCE_SIMILARITY_LEVEL = level;
  if (args.ace || args.enableAceStep) env.PROMPT2MIDI_ENABLE_ACE_STEP = '1';
  if (args.candidates) env.PROMPT2MIDI_ACE_STEP_CANDIDATES = args.candidates;
  if (args.steps) env.PROMPT2MIDI_ACE_STEP_STEPS = args.steps;
  if (args.guidance) env.PROMPT2MIDI_ACE_STEP_GUIDANCE = args.guidance;
  if (args.selectCandidate) env.PROMPT2MIDI_ACE_STEP_SELECT_CANDIDATE = args.selectCandidate;
  if (args.autoSelect) env.PROMPT2MIDI_ACE_STEP_AUTO_SELECT = '1';

  const childArgs = [
    analyzeScript,
    '--audio', prepared.analysisPath,
    '--output-dir', outputDir,
    '--similarity-level', level,
  ];
  if (prompt) childArgs.push('--user-prompt', prompt);

  return new Promise((resolve) => {
    const child = spawn('python3', childArgs, {
      cwd: repoRoot,
      env,
      stdio: 'inherit',
    });
    child.on('exit', (code, signal) => {
      if (signal) process.kill(process.pid, signal);
      process.exitCode = code || 0;
      resolve(process.exitCode);
    });
    child.on('error', (error) => resolve(fail(error.message)));
  });
}

function parseArgs(argv) {
  const parsed = {};
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--help' || arg === '-h') parsed.help = true;
    else if (arg === '--ace' || arg === '--enable-ace-step') parsed.enableAceStep = true;
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
  npm run reference -- --reference "/absolute/path/to/song.wav" --output-dir /tmp/prompt2midi-run --similarity-level high --prompt "tight club mix, no vocals" --ace

Options:
  --reference <path>            Absolute WAV/MP3 reference path. MP3 requires ffmpeg.
  --output-dir <path>           Output directory for analysis, MIDI, prompt, and candidates.
  --prompt <text>               Creative direction added to detected metadata.
  --similarity-level <level>    low, medium-low, medium, medium-high, high, near-identical, or identical.
  --ace                         Enable ACE-Step generation; requires npm run ace-step:start in another terminal.
  --candidates <n>              ACE candidate count.
  --select-candidate <n>        Promote a specific generated candidate to sample.wav after auditioning.
  --auto-select <yes>           Use advisory quality scoring to create sample.wav automatically.
  --steps <n>                   ACE diffusion steps.
  --guidance <n>                ACE guidance scale.`);
}

main().catch((error) => fail(error.message || String(error)));
