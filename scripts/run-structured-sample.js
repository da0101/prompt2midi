#!/usr/bin/env node

const { spawn } = require('node:child_process');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..');
const runner = path.join(repoRoot, 'analysis', 'structured_render.py');

async function main() {
  const args = process.argv.slice(2);
  if (args.includes('--help') || args.includes('-h')) {
    printHelp();
    return 0;
  }
  if (!hasArg(args, '--reference') || !hasArg(args, '--output-dir')) {
    printHelp();
    return 1;
  }

  const childArgs = [runner, ...args];
  if (!hasArg(args, '--duration')) childArgs.push('--duration', '30');
  if (!hasArg(args, '--candidates')) childArgs.push('--candidates', '4');
  if (!hasArg(args, '--similarity-level')) childArgs.push('--similarity-level', 'medium');

  return new Promise((resolve) => {
    const child = spawn('python3', childArgs, {
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
  npm run sample:structured -- --reference "/absolute/path/song.wav" --output-dir tmp/test --similarity-level low --prompt "dark electro funk, no copied vocal"

Defaults:
  --duration 30
  --candidates 4
  --similarity-level medium

This renders audio in the local pipeline. It does not require Ableton or ACE-Step.`);
}

main().then((code) => {
  process.exitCode = code;
}).catch((error) => {
  console.error(`error: ${error.message || String(error)}`);
  process.exitCode = 1;
});
