#!/usr/bin/env node

const fs = require('node:fs');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..', '..');
const feedbackLog = path.join(repoRoot, '.platform', 'work', 'listen-feedback.jsonl');

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printHelp();
    return 0;
  }
  if (!args.manifest) return fail('Missing --manifest.');
  const manifestPath = path.resolve(args.manifest);
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const pick = args.pick ? Number.parseInt(args.pick, 10) : null;
  if (pick !== null && (!Number.isInteger(pick) || pick < 1 || pick > (manifest.candidate_count || 0))) {
    return fail(`--pick must be between 1 and ${manifest.candidate_count || 0}.`);
  }

  const feedback = {
    status: 'recorded',
    recorded_at: new Date().toISOString(),
    user_pick: pick,
    accepted_for_level: parseBoolean(args.accepted),
    notes: args.notes || '',
    tags: splitTags(args.tags),
  };
  manifest.feedback = feedback;
  manifest.status = pick ? 'user_selected' : 'feedback_recorded';
  manifest.selected_candidate = pick ? candidateRef(manifest, pick) : null;
  fs.writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);

  fs.mkdirSync(path.dirname(feedbackLog), { recursive: true });
  fs.appendFileSync(feedbackLog, `${JSON.stringify({
    run_id: manifest.run_id,
    reference_audio: manifest.reference_audio,
    output_dir: manifest.output_dir,
    level: manifest.similarity && manifest.similarity.level,
    manifest: manifestPath,
    feedback,
  })}\n`);

  console.log(`Recorded feedback for ${manifest.run_id}`);
  return 0;
}

function candidateRef(manifest, pick) {
  const candidate = (manifest.candidates || []).find((item) => item.index === pick);
  return candidate ? { index: pick, path: candidate.path } : { index: pick, path: null };
}

function parseArgs(argv) {
  const parsed = {};
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--help' || arg === '-h') parsed.help = true;
    else if (arg.startsWith('--')) {
      const key = toCamel(arg.slice(2));
      const value = argv[index + 1];
      if (!value || value.startsWith('--')) return fail(`Missing value for ${arg}.`);
      parsed[key] = value;
      index += 1;
    } else {
      return fail(`Unknown argument: ${arg}`);
    }
  }
  return parsed;
}

function toCamel(name) {
  return name.replace(/-([a-z])/g, (_, char) => char.toUpperCase());
}

function parseBoolean(value) {
  if (value === undefined) return null;
  const normalized = String(value).toLowerCase();
  if (['1', 'true', 'yes', 'y', 'accepted'].includes(normalized)) return true;
  if (['0', 'false', 'no', 'n', 'rejected'].includes(normalized)) return false;
  return null;
}

function splitTags(value) {
  return String(value || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function fail(message) {
  console.error(`error: ${message}`);
  process.exitCode = 2;
  return 2;
}

function printHelp() {
  console.log(`Usage:
  npm run feedback -- --manifest tmp/run/exports/candidate-manifest.json --pick 3 --accepted yes --notes "best groove" --tags "good-bass,usable"

Options:
  --manifest <path>    Path to candidate-manifest.json.
  --pick <n>           User-selected candidate number.
  --accepted <yes/no>  Whether the run works for the intended level.
  --notes <text>       Listening notes.
  --tags <csv>         Optional comma-separated tags.`);
}

main();
