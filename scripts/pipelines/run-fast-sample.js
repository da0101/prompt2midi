#!/usr/bin/env node

const { spawn } = require('node:child_process');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..', '..');
const runner = path.join(repoRoot, 'scripts', 'pipelines', 'run-reference-pipeline.js');

async function main() {
  const args = process.argv.slice(2);
  if (args.includes('--help') || args.includes('-h')) {
    printHelp();
    return 0;
  }
  const childArgs = [
    runner,
    ...args,
    '--fast-sample',
    '--ace',
  ];
  if (!hasArg(args, '--candidates')) childArgs.push('--candidates', '4');
  if (!hasArg(args, '--duration') && !hasArg(args, '--sample-duration')) childArgs.push('--duration', '15');

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
  npm run sample:fast -- --reference "/absolute/path/song.mp3" --output-dir tmp/test --similarity-level low --prompt "electro house, new vocal hook"

Defaults:
  --ace enabled
  --fast-sample enabled
  --duration 15
  --candidates 4`);
}

main().then((code) => {
  process.exitCode = code;
}).catch((error) => {
  console.error(`error: ${error.message || String(error)}`);
  process.exitCode = 1;
});
