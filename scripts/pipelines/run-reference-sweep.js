#!/usr/bin/env node

const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..', '..');
const runner = path.join(repoRoot, 'scripts', 'pipelines', 'run-reference-pipeline.js');
const DEFAULT_LEVELS = ['low', 'medium-low', 'medium', 'medium-high', 'high', 'near-identical'];

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printHelp();
    return 0;
  }

  const reference = args.reference || args.audio;
  const outputDir = args.outputDir || args.output;
  const prompt = args.prompt || '';
  const duration = args.duration || args.sampleDuration || 'full';
  const candidates = Number.parseInt(args.candidates || '4', 10);
  const levels = args.levels ? args.levels.split(',').map((item) => item.trim()).filter(Boolean) : DEFAULT_LEVELS;
  const startAt = args.startAt || '';
  const skipExisting = args.skipExisting !== 'false';

  if (!reference || !outputDir) return fail('Missing required --reference and --output-dir.');
  if (!path.isAbsolute(reference)) return fail('--reference must be an absolute path.');
  if (!Number.isInteger(candidates) || candidates < 1 || candidates > 6) return fail('--candidates must be 1-6.');

  fs.mkdirSync(outputDir, { recursive: true });
  const summary = {
    reference,
    output_dir: path.resolve(outputDir),
    duration,
    candidates_per_level: candidates,
    levels,
    runs: [],
  };

  let started = !startAt;
  for (const level of levels) {
    for (let index = 1; index <= candidates; index += 1) {
      const candidateId = `${level}/candidate-${index}`;
      if (!started && candidateId !== startAt && level !== startAt) continue;
      started = true;

      const candidateDir = path.join(outputDir, level, `candidate-${index}`);
      const wavPath = path.join(candidateDir, 'exports', 'candidate-1.wav');
      if (skipExisting && fs.existsSync(wavPath)) {
        console.error(`sweep: skipping existing ${candidateId}`);
        summary.runs.push({ level, candidate: index, status: 'skipped_existing', path: wavPath });
        writeSummary(outputDir, summary);
        continue;
      }

      console.error(`sweep: starting ${candidateId}`);
      const code = await runOne({ reference, candidateDir, level, prompt, duration });
      const status = code === 0 ? 'succeeded' : 'failed';
      summary.runs.push({ level, candidate: index, status, path: wavPath, quality: readQuality(candidateDir) });
      writeSummary(outputDir, summary);
      if (code !== 0) return code;
    }
  }

  return 0;
}

function runOne({ reference, candidateDir, level, prompt, duration }) {
  const childArgs = [
    runner,
    '--reference',
    reference,
    '--output-dir',
    candidateDir,
    '--similarity-level',
    level,
    '--duration',
    duration,
    '--prompt',
    prompt,
    '--ace',
    '--candidates',
    '1',
  ];
  return new Promise((resolve) => {
    const child = spawn('node', childArgs, {
      cwd: repoRoot,
      env: process.env,
      stdio: 'inherit',
    });
    child.on('exit', (code, signal) => {
      if (signal) process.kill(process.pid, signal);
      resolve(code || 0);
    });
    child.on('error', (error) => {
      console.error(`sweep: failed to launch ${level}: ${error.message}`);
      resolve(1);
    });
  });
}

function writeSummary(outputDir, summary) {
  fs.writeFileSync(path.join(outputDir, 'sweep-summary.json'), `${JSON.stringify(summary, null, 2)}\n`);
}

function readQuality(candidateDir) {
  const manifestPath = path.join(candidateDir, 'exports', 'candidate-manifest.json');
  if (!fs.existsSync(manifestPath)) return null;
  try {
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    const candidate = (manifest.candidates || [])[0] || {};
    return {
      suggested: manifest.suggested_candidate,
      gate: candidate.quality && candidate.quality.level_gate,
      score: candidate.quality && candidate.quality.score,
      selection_score: candidate.quality && candidate.quality.selection_score,
      pulse_score: candidate.quality && candidate.quality.pulse_score,
      timbre_score: candidate.quality && candidate.quality.timbre_score,
      warnings: (candidate.quality && candidate.quality.warnings) || [],
    };
  } catch (error) {
    return { error: error.message };
  }
}

function parseArgs(argv) {
  const parsed = {};
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--help' || arg === '-h') parsed.help = true;
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
  npm run reference:sweep -- --reference "/absolute/path/to/song.mp3" --output-dir tmp/my-sweep --prompt "direction" --duration full --candidates 4

Options:
  --reference <path>         Absolute WAV/MP3 reference path.
  --output-dir <path>        Sweep output root.
  --prompt <text>            Creative direction passed to every level.
  --duration <seconds|full>  Generated candidate length. Default: full.
  --candidates <n>           Candidates per level. Default: 4.
  --levels <csv>             Override levels. Default: all six named levels.
  --start-at <id>            Resume at level or level/candidate-n.
  --skip-existing <false>    By default existing candidate WAVs are skipped.`);
}

main().then((code) => {
  process.exitCode = code;
}).catch((error) => fail(error.message || String(error)));
