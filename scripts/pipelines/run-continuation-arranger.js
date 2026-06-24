#!/usr/bin/env node

const { spawn } = require('node:child_process');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..', '..');
const ANALYSIS_PYTHON = process.env.PROMPT2MIDI_ANALYSIS_PYTHON || process.env.PROMPT2MIDI_PYTHON || 'python3';

async function main() {
  const args = process.argv.slice(2);
  if (args.includes('--help') || args.includes('-h')) {
    printHelp();
    return 0;
  }
  if (!hasArg(args, '--input-dir') || !hasArg(args, '--output-dir')) {
    printHelp();
    return 1;
  }

  const childArgs = ['-m', 'analysis.arrangement_continuation.continuation_arranger', ...args];
  if (!hasArg(args, '--target-duration')) childArgs.push('--target-duration', '360');
  if (!hasArg(args, '--continue-from')) childArgs.push('--continue-from', 'auto');

  return new Promise((resolve) => {
    const child = spawn(ANALYSIS_PYTHON, childArgs, {
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

function hasArg(args, name) {
  return args.includes(name);
}

function printHelp() {
  console.log(`Usage:
  npm run arrange:continue -- --input-dir "/path/to/suno-stems" --output-dir tmp/arranged --target-duration 360 --bpm 128
  npm run arrange:continue -- --input-dir "/path/to/suno-stems" --output-dir tmp/arranged --target-duration 380 --bpm 128 --blueprint-audio "/path/to/ace-demo.wav"

Inputs:
  A folder containing WAV stems exported from Suno/ACE. Stem roles are inferred from filenames.

Defaults:
  --target-duration 360
  --continue-from auto
  vocals are muted unless --include-vocals is passed
  --blueprint-audio is optional; when provided, its energy curve shapes the appended continuation
  --prepend-intro-bars can add a DJ intro from Suno's own stem material
  --source-end-trim-bars can remove Suno's terminal ending hit before continuing
  --blueprint-breakdown-bars and --blueprint-outro-bars default to 16
  --drum-substems tries optional DrumSep kick/snare/cymbals/toms separation
  --arrangement-mode suno-blocks preserves Suno grammar and reuses its own 16-bar blocks for the second half
  --arrangement-mode prebreak-diagnostic renders only a strict bar-locked first-half/pre-break/breakdown test
  --preserve-source-bars, --pre-break-source-start-bars, and --breakdown-source-start-bars address source material in zero-based bars

Output:
  arranged-full-mix.wav
  arranged-stems/*.wav
  arrangement-map.json
  arrangement-report.md`);
}

main().then((code) => {
  process.exitCode = code;
}).catch((error) => {
  console.error(`error: ${error.message || String(error)}`);
  process.exitCode = 1;
});
