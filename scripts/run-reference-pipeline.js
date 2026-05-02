#!/usr/bin/env node

const { spawn } = require('node:child_process');
const path = require('node:path');
const { prepareAudioForAnalysis, validateAudioPath } = require('../backend/lib/audioInput');

const repoRoot = path.resolve(__dirname, '..');
const analyzeScript = path.join(repoRoot, 'analysis', 'analyze.py');
const LEVELS = new Set(['low', 'medium-low', 'medium', 'medium-high', 'high', 'very-high', 'near-identical', 'identical']);

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
