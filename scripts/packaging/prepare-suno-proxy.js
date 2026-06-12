#!/usr/bin/env node

const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..', '..');
const ANALYSIS_PYTHON = process.env.PROMPT2MIDI_ANALYSIS_PYTHON || process.env.PROMPT2MIDI_PYTHON || 'python3';
const MIN_PROXY_DURATION_SECONDS = 6;
const MAX_PROXY_DURATION_SECONDS = 600;

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printHelp();
    return 0;
  }

  const reference = args.reference || args.audio;
  const proxyAudio = args.proxyAudio || args.proxy;
  const outputDir = args.outputDir || args.output;
  const duration = args.duration || '30';
  const prompt = args.prompt || '';
  const start = args.start;

  if (!reference || !proxyAudio || !outputDir) {
    return fail('Missing required --reference, --proxy-audio, and --output-dir.');
  }
  if (!path.isAbsolute(reference)) return fail('--reference must be an absolute path.');
  if (!path.isAbsolute(proxyAudio)) return fail('--proxy-audio must be an absolute path.');
  if (!fs.existsSync(reference)) return fail(`Reference file does not exist: ${reference}`);
  if (!fs.existsSync(proxyAudio)) return fail(`Proxy audio file does not exist: ${proxyAudio}`);

  const fullDuration = ['full', 'reference', 'track', 'source'].includes(String(duration).trim().toLowerCase());
  const durationNumber = fullDuration ? null : Number.parseFloat(duration);
  if (
    !fullDuration &&
    (!Number.isFinite(durationNumber) ||
      durationNumber < MIN_PROXY_DURATION_SECONDS ||
      durationNumber > MAX_PROXY_DURATION_SECONDS)
  ) {
    return fail(`--duration must be a number between ${MIN_PROXY_DURATION_SECONDS} and ${MAX_PROXY_DURATION_SECONDS} seconds, or full.`);
  }
  if (start !== undefined) {
    const startNumber = Number.parseFloat(start);
    if (!Number.isFinite(startNumber) || startNumber < 0) return fail('--start must be a non-negative number.');
  }

  const childArgs = [
    '-m',
    'analysis.packaging.suno_proxy_package',
    '--reference',
    reference,
    '--proxy-audio',
    proxyAudio,
    '--output-dir',
    path.resolve(outputDir),
    '--duration',
    fullDuration ? 'full' : String(durationNumber),
  ];
  if (prompt) childArgs.push('--prompt', prompt);
  if (start !== undefined) childArgs.push('--start', String(Number.parseFloat(start)));

  return run(ANALYSIS_PYTHON, childArgs);
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
      if (signal) process.kill(process.pid, signal);
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
  npm run suno:proxy -- --reference "/absolute/path/original.mp3" --proxy-audio "/absolute/path/generated-candidate.wav" --output-dir tmp/suno-proxy --prompt "finish as dark electro-funk dance-pop"

Meaning:
  --reference     Original reference used locally for analysis only.
  --proxy-audio   Newly generated proxy demo. This is the only audio prepared for Suno upload.
  --output-dir    Folder where the Suno proxy package will be written.
  --prompt        Optional copyright-safe direction for Suno.
  --duration      Upload length, 6-600 seconds, or full for the full proxy track; default 30.
  --start         Optional manual start time inside the proxy audio.

Output:
  suno-upload-proxy.wav/mp3
  suno-proxy-prompt.md
  suno-proxy-analysis.md
  suno-proxy-usage-steps.md
  suno-proxy-package.json`);
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
