#!/usr/bin/env node

const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..');
const referenceRunner = path.join(repoRoot, 'scripts', 'run-reference-pipeline.js');
const proxyPackager = path.join(repoRoot, 'scripts', 'prepare-suno-proxy.js');

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printHelp();
    return 0;
  }

  const reference = args.reference || args.audio;
  const outputDir = args.outputDir || args.output;
  const prompt = args.prompt || defaultPrompt();
  const level = args.similarityLevel || args.level || 'medium-high';
  const duration = args.duration || '30';
  const candidates = args.candidates || '4';
  const packCandidate = Number.parseInt(args.packCandidate || args.selectCandidate || '0', 10);

  if (!reference || !outputDir) return fail('Missing required --reference and --output-dir.');
  if (!path.isAbsolute(reference)) return fail('--reference must be an absolute path.');
  if (!fs.existsSync(reference)) return fail(`Reference file does not exist: ${reference}`);

  const runDir = path.resolve(outputDir);
  fs.mkdirSync(runDir, { recursive: true });
  const generationReference = await prepareReferenceForGeneration(reference, runDir);

  const generationArgs = [
    referenceRunner,
    '--reference',
    generationReference,
    '--output-dir',
    runDir,
    '--similarity-level',
    level,
    '--prompt',
    prompt,
    '--fast-sample',
    '--ace',
    '--candidates',
    candidates,
    '--duration',
    duration,
  ];
  if (args.vocals) generationArgs.push('--vocals');
  if (args.instrumental) generationArgs.push('--instrumental');
  if (args.referenceStart) generationArgs.push('--reference-start', args.referenceStart);
  if (args.referenceStrategy) generationArgs.push('--reference-strategy', args.referenceStrategy);
  if (packCandidate > 0) generationArgs.push('--select-candidate', String(packCandidate));
  if (args.steps) generationArgs.push('--steps', args.steps);
  if (args.guidance) generationArgs.push('--guidance', args.guidance);

  process.env.PROMPT2MIDI_RICH_REFERENCE_COVER = process.env.PROMPT2MIDI_RICH_REFERENCE_COVER || '1';
  process.env.PROMPT2MIDI_REFERENCE_SECTION_STRATEGY = process.env.PROMPT2MIDI_REFERENCE_SECTION_STRATEGY || 'early_character';

  const generationCode = await run('node', generationArgs);
  if (generationCode !== 0) return generationCode;

  const proxyAudio = chooseProxyAudio(runDir, packCandidate);
  if (!proxyAudio) return fail(`No generated ACE proxy candidate found under ${path.join(runDir, 'exports')}.`);

  const packageDir = path.join(runDir, 'suno-proxy-package');
  const packageArgs = [
    proxyPackager,
    '--reference',
    reference,
    '--proxy-audio',
    proxyAudio,
    '--output-dir',
    packageDir,
    '--duration',
    duration,
    '--prompt',
    prompt,
  ];
  const packageCode = await run('node', packageArgs);
  if (packageCode !== 0) return packageCode;

  console.log(JSON.stringify({
    ok: true,
    reference_local_only: reference,
    generated_proxy_audio: proxyAudio,
    suno_package_dir: packageDir,
    upload: path.join(packageDir, 'suno-upload-proxy.wav'),
    prompt: path.join(packageDir, 'suno-proxy-prompt.md'),
  }, null, 2));
  return 0;
}

function chooseProxyAudio(runDir, explicitCandidate) {
  const exportsDir = path.join(runDir, 'exports');
  if (explicitCandidate > 0) {
    const explicit = path.join(exportsDir, `candidate-${explicitCandidate}.wav`);
    if (fs.existsSync(explicit)) return explicit;
  }
  const manifestPath = path.join(exportsDir, 'candidate-manifest.json');
  if (fs.existsSync(manifestPath)) {
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    const selected = manifest.selected_candidate && manifest.selected_candidate.path;
    const suggested = manifest.suggested_candidate && manifest.suggested_candidate.path;
    if (selected && fs.existsSync(selected)) return selected;
    if (suggested && fs.existsSync(suggested)) return suggested;
  }
  const sample = path.join(exportsDir, 'sample.wav');
  if (fs.existsSync(sample)) return sample;
  for (let index = 1; index <= 6; index += 1) {
    const candidate = path.join(exportsDir, `candidate-${index}.wav`);
    if (fs.existsSync(candidate)) return candidate;
  }
  return null;
}

async function prepareReferenceForGeneration(reference, runDir) {
  const extension = path.extname(reference).toLowerCase();
  if (extension === '.wav' || extension === '.wave' || extension === '.mp3') {
    return reference;
  }
  const decoded = path.join(runDir, 'local-reference-for-ace.wav');
  const ffmpeg = process.env.PROMPT2MIDI_FFMPEG || 'ffmpeg';
  const code = await run(ffmpeg, [
    '-y',
    '-hide_banner',
    '-loglevel',
    'error',
    '-i',
    reference,
    '-vn',
    '-ac',
    '2',
    '-ar',
    '44100',
    decoded,
  ]);
  if (code !== 0) throw new Error(`Could not decode reference audio for ACE generation with ${ffmpeg}.`);
  return decoded;
}

function parseArgs(argv) {
  const parsed = {};
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--help' || arg === '-h') parsed.help = true;
    else if (arg === '--vocals') parsed.vocals = true;
    else if (arg === '--instrumental') parsed.instrumental = true;
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

function run(command, args) {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      cwd: repoRoot,
      env: process.env,
      stdio: 'inherit',
    });
    child.on('exit', (code, signal) => {
      if (signal) process.kill(process.pid, signal);
      resolve(code || 0);
    });
    child.on('error', (error) => {
      console.error(`error: ${error.message}`);
      resolve(1);
    });
  });
}

function defaultPrompt() {
  return [
    'Create a complete new original 1980s electro-funk dance-pop proxy demo',
    '30-second full hook-section arrangement, not a bass-only sketch',
    'sleek late-80s dance-pop and electro-funk feel, not generic retro synthwave',
    'tight staccato 16th-note bass pocket with funky low-end movement answering the kick',
    'hard snare/clap backbeat on 2 and 4, crisp hats, tight percussion fills, and clean transitions',
    'dramatic minor-key tension, synth-brass stabs, layered keys, plucked synth or rhythm-guitar comping, and short accent hits',
    'verse-to-hook motion with call-and-response instrumental or vocal-hook energy',
    'high energy club-pop attitude with a strong new hook contour and full-band impact',
    'include short original vocal chops or a new vocal-hook texture if musically stable',
    'no famous singer imitation',
    'no copied lyrics',
    'no copied melody',
    'no copied master recording',
  ].join(', ');
}

function printHelp() {
  console.log(`Usage:
  npm run suno:proxy-run -- --reference "/absolute/path/MJ-testing.m4a" --output-dir tmp/mj-proxy-v1 --duration 30

Flow:
  1. Analyze the original reference locally.
  2. Generate ACE proxy candidates.
  3. Package only the generated proxy demo for Suno.
  4. Never package the original reference as the Suno upload.

Options:
  --prompt <text>               Copyright-safe style direction.
  --similarity-level <level>    Defaults to medium-high for close but copyright-safer proxy demos.
  --duration <seconds>          Defaults to 30.
  --candidates <n>              Defaults to 4.
  --pack-candidate <n>          Package a specific candidate after generation.
  --vocals                      Ask ACE for a new vocal hook; default is instrumental proxy for stability.
  --reference-start <seconds>   Force the local reference section used to condition ACE.
  --reference-strategy <name>   Section picker: early_character or stable_energy. Defaults to early_character.
  --steps <n>                   ACE inference steps.
  --guidance <n>                ACE guidance scale.`);
}

function fail(message) {
  console.error(`error: ${message}`);
  process.exitCode = 2;
  return 2;
}

main().then((code) => {
  process.exitCode = code;
}).catch((error) => {
  console.error(`error: ${error.message || String(error)}`);
  process.exitCode = 1;
});
