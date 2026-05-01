#!/usr/bin/env node

const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..');
const pythonScript = path.join(repoRoot, 'analysis', 'suno_cover_package.py');

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printHelp();
    return 0;
  }

  const reference = args.reference || args.audio;
  const outputDir = args.outputDir || args.output;
  const duration = args.duration || '30';
  const prompt = args.prompt || '';
  const start = args.start;

  if (!reference || !outputDir) return fail('Missing required --reference and --output-dir.');
  if (!path.isAbsolute(reference)) return fail('--reference must be an absolute path.');
  if (!fs.existsSync(reference)) return fail(`Reference file does not exist: ${reference}`);

  const durationNumber = Number.parseFloat(duration);
  if (!Number.isFinite(durationNumber) || durationNumber < 6 || durationNumber > 60) {
    return fail('--duration must be a number between 6 and 60 seconds.');
  }
  if (start !== undefined) {
    const startNumber = Number.parseFloat(start);
    if (!Number.isFinite(startNumber) || startNumber < 0) {
      return fail('--start must be a non-negative number.');
    }
  }

  const childArgs = [
    pythonScript,
    '--reference',
    reference,
    '--output-dir',
    path.resolve(outputDir),
    '--duration',
    String(durationNumber),
  ];
  if (prompt) childArgs.push('--prompt', prompt);
  if (start !== undefined) childArgs.push('--start', String(Number.parseFloat(start)));

  return run(process.env.PROMPT2MIDI_PYTHON || 'python3', childArgs);
}

function parseArgs(argv) {
  const parsed = {};
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--help' || arg === '-h') {
      parsed.help = true;
    } else if (arg.startsWith('--')) {
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
      if (signal) {
        process.kill(process.pid, signal);
      }
      resolve(code || 0);
    });
    child.on('error', (error) => {
      console.error(`error: ${error.message}`);
      resolve(1);
    });
  });
}

function printHelp() {
  console.log(`Usage:
  npm run suno:prepare -- --reference "/absolute/path/song.mp3" --output-dir tmp/suno-song --prompt "make it darker, modern club mix"

Options:
  --reference    Absolute path to mp3/wav/m4a/flac reference audio
  --output-dir   Folder where the Suno package will be written
  --prompt       Optional human direction for the new Suno result
  --duration     Upload clip length, 6-60 seconds; default 30
  --start        Optional manual start time in seconds

Output:
  suno-upload-reference.wav/mp3
  suno-cover-prompt.md
  suno-cover-analysis.md
  suno-usage-steps.md
  suno-cover-package.json`);
}

function fail(message) {
  console.error(`error: ${message}`);
  process.exit(2);
}

main().then((code) => {
  process.exitCode = code;
}).catch((error) => {
  console.error(`error: ${error.message || String(error)}`);
  process.exitCode = 1;
});
