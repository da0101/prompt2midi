#!/usr/bin/env node

const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..', '..');

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printHelp();
    return 0;
  }

  const reference = args.reference || args.audio;
  const outputDir = args.outputDir || args.output;
  const start = Number.parseFloat(args.start || '0');
  const duration = Number.parseFloat(args.duration || '30');
  const segments = Number.parseInt(args.segments || '2', 10);
  const maxNewTokens = Number.parseInt(args.maxNewTokens || '3000', 10);
  const repetitionPenalty = Number.parseFloat(args.repetitionPenalty || '1.1');
  const prompt = args.prompt || '';
  const genre = args.genre || defaultGenre(prompt);
  const lyrics = args.lyrics || defaultLyrics();

  if (!reference || !outputDir) return fail('Missing required --reference and --output-dir.');
  if (!path.isAbsolute(reference)) return fail('--reference must be an absolute path.');
  if (!fs.existsSync(reference)) return fail(`Reference file does not exist: ${reference}`);
  if (!Number.isFinite(start) || start < 0) return fail('--start must be a non-negative number.');
  if (!Number.isFinite(duration) || duration <= 0 || duration > 30) {
    return fail('--duration must be > 0 and <= 30 for YuE ICL.');
  }
  if (!Number.isInteger(segments) || segments < 1 || segments > 24) return fail('--segments must be 1-24.');
  if (!Number.isInteger(maxNewTokens) || maxNewTokens < 100 || maxNewTokens > 6000) {
    return fail('--max-new-tokens must be 100-6000.');
  }
  if (!Number.isFinite(repetitionPenalty) || repetitionPenalty < 1 || repetitionPenalty > 2) {
    return fail('--repetition-penalty must be between 1 and 2.');
  }

  const packageDir = path.resolve(outputDir);
  fs.mkdirSync(packageDir, { recursive: true });

  const referenceSection = path.join(packageDir, 'reference-30s.wav');
  await cutReference({ reference, referenceSection, start, duration });

  const stems = findExistingStems(args);
  if (stems.vocals) fs.copyFileSync(stems.vocals, path.join(packageDir, 'vocals.wav'));
  if (stems.instrumental) fs.copyFileSync(stems.instrumental, path.join(packageDir, 'instrumental.wav'));

  fs.writeFileSync(path.join(packageDir, 'genre.txt'), `${genre.trim()}\n`);
  fs.writeFileSync(path.join(packageDir, 'lyrics.txt'), `${lyrics.trim()}\n`);
  const runConfig = { promptEndTime: duration, segments, maxNewTokens, repetitionPenalty };
  fs.writeFileSync(path.join(packageDir, 'run-yue-single-track.sh'), singleTrackScript(runConfig));
  fs.writeFileSync(path.join(packageDir, 'run-yue-dual-track.sh'), dualTrackScript(runConfig));
  fs.writeFileSync(path.join(packageDir, 'README.md'), readme({
    reference,
    start,
    duration,
    segments,
    maxNewTokens,
    prompt,
    hasDualTrack: Boolean(stems.vocals && stems.instrumental),
  }));
  fs.writeFileSync(path.join(packageDir, 'manifest.json'), `${JSON.stringify({
    created_at: new Date().toISOString(),
    reference_audio: reference,
    reference_section: referenceSection,
    prompt,
    genre,
    duration_seconds: duration,
    prompt_start_time: 0,
    prompt_end_time: duration,
    yue_segments: segments,
    yue_max_new_tokens: maxNewTokens,
    yue_repetition_penalty: repetitionPenalty,
    yue_mode: stems.vocals && stems.instrumental ? 'dual_track_or_single_track' : 'single_track',
    files: {
      reference: 'reference-30s.wav',
      vocals: stems.vocals ? 'vocals.wav' : null,
      instrumental: stems.instrumental ? 'instrumental.wav' : null,
      genre: 'genre.txt',
      lyrics: 'lyrics.txt',
      single_track_script: 'run-yue-single-track.sh',
      dual_track_script: 'run-yue-dual-track.sh',
    },
  }, null, 2)}\n`);

  await chmodExecutable(path.join(packageDir, 'run-yue-single-track.sh'));
  await chmodExecutable(path.join(packageDir, 'run-yue-dual-track.sh'));

  console.log(JSON.stringify({
    ok: true,
    package_dir: packageDir,
    run_first: stems.vocals && stems.instrumental ? 'run-yue-dual-track.sh' : 'run-yue-single-track.sh',
    note: stems.vocals && stems.instrumental
      ? 'Dual-track package is ready.'
      : 'No vocal/instrumental stems were provided, so start with single-track ICL.',
  }, null, 2));
  return 0;
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

async function cutReference({ reference, referenceSection, start, duration }) {
  const ffmpeg = process.env.PROMPT2MIDI_FFMPEG || 'ffmpeg';
  const args = [
    '-y',
    '-hide_banner',
    '-loglevel',
    'error',
    '-ss',
    String(start),
    '-i',
    reference,
    '-t',
    String(duration),
    '-ac',
    '2',
    '-ar',
    '44100',
    referenceSection,
  ];
  await run(ffmpeg, args);
}

function findExistingStems(args) {
  const vocals = args.vocals || args.vocalTrack || '';
  const instrumental = args.instrumental || args.instrumentalTrack || args.noVocals || '';
  return {
    vocals: vocals && fs.existsSync(vocals) ? path.resolve(vocals) : null,
    instrumental: instrumental && fs.existsSync(instrumental) ? path.resolve(instrumental) : null,
  };
}

async function chmodExecutable(filePath) {
  try {
    await fs.promises.chmod(filePath, 0o755);
  } catch {
    // Non-fatal on filesystems that do not support chmod.
  }
}

function run(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd: repoRoot, stdio: 'inherit' });
    child.on('exit', (code, signal) => {
      if (signal) reject(new Error(`${command} stopped by ${signal}`));
      else if (code === 0) resolve();
      else reject(new Error(`${command} exited with code ${code}`));
    });
    child.on('error', reject);
  });
}

function defaultGenre(prompt) {
  const extra = prompt ? `; user direction: ${prompt}` : '';
  return [
    'electro-funk',
    '1980s dance-pop',
    'post-disco',
    'tight syncopated bass groove',
    'punchy gated drums',
    'crisp hi-hats',
    'minor-key dramatic synth stabs',
    'high-energy pop-funk arrangement',
    'clean professional mix',
    'new original song, not a cover',
    'do not copy the reference singer, lyrics, melody, or hook',
  ].join(', ') + extra;
}

function defaultLyrics() {
  return `[verse]
Neon lines on the street, moving sharp in the night
Every step hits the floor like a flash of white light

[pre-chorus]
Hold the tension, keep it tight
Turn the corner into midnight

[chorus]
Run with the rhythm, cut through the dark
New fire rising with a brand new spark

[outro]
No copied words, no copied melody, original vocal idea only`;
}

function singleTrackScript({ promptEndTime, segments, maxNewTokens, repetitionPenalty }) {
  return `#!/usr/bin/env bash
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
YUE_ROOT="\${YUE_ROOT:-$HOME/YuE}"
CUDA_IDX="\${CUDA_IDX:-0}"
OUTPUT_DIR="\${OUTPUT_DIR:-$PACKAGE_DIR/output-single-track}"

if [ ! -f "$YUE_ROOT/inference/infer.py" ]; then
  echo "YuE repo not found at $YUE_ROOT."
  echo "Install it first on the GPU machine, then rerun:"
  echo "  git clone https://github.com/multimodal-art-projection/YuE.git $YUE_ROOT"
  echo "  cd $YUE_ROOT"
  echo "  follow the official YuE CUDA/FlashAttention setup instructions"
  exit 2
fi

mkdir -p "$OUTPUT_DIR"
cd "$YUE_ROOT/inference"

python infer.py \\
  --cuda_idx "$CUDA_IDX" \\
  --stage1_model "\${YUE_STAGE1_MODEL:-m-a-p/YuE-s1-7B-anneal-en-icl}" \\
  --stage2_model "\${YUE_STAGE2_MODEL:-m-a-p/YuE-s2-1B-general}" \\
  --genre_txt "$PACKAGE_DIR/genre.txt" \\
  --lyrics_txt "$PACKAGE_DIR/lyrics.txt" \\
  --run_n_segments "\${YUE_SEGMENTS:-${segments}}" \\
  --stage2_batch_size "\${YUE_STAGE2_BATCH_SIZE:-4}" \\
  --output_dir "$OUTPUT_DIR" \\
  --max_new_tokens "\${YUE_MAX_NEW_TOKENS:-${maxNewTokens}}" \\
  --repetition_penalty "\${YUE_REPETITION_PENALTY:-${repetitionPenalty}}" \\
  --use_audio_prompt \\
  --audio_prompt_path "$PACKAGE_DIR/reference-30s.wav" \\
  --prompt_start_time 0 \\
  --prompt_end_time ${promptEndTime}
`;
}

function dualTrackScript({ promptEndTime, segments, maxNewTokens, repetitionPenalty }) {
  return `#!/usr/bin/env bash
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
YUE_ROOT="\${YUE_ROOT:-$HOME/YuE}"
CUDA_IDX="\${CUDA_IDX:-0}"
OUTPUT_DIR="\${OUTPUT_DIR:-$PACKAGE_DIR/output-dual-track}"

if [ ! -f "$PACKAGE_DIR/vocals.wav" ] || [ ! -f "$PACKAGE_DIR/instrumental.wav" ]; then
  echo "Missing vocals.wav or instrumental.wav."
  echo "Use run-yue-single-track.sh, or rebuild this package with --vocals and --instrumental."
  exit 2
fi

if [ ! -f "$YUE_ROOT/inference/infer.py" ]; then
  echo "YuE repo not found at $YUE_ROOT."
  echo "Install it first on the GPU machine, then rerun:"
  echo "  git clone https://github.com/multimodal-art-projection/YuE.git $YUE_ROOT"
  echo "  cd $YUE_ROOT"
  echo "  follow the official YuE CUDA/FlashAttention setup instructions"
  exit 2
fi

mkdir -p "$OUTPUT_DIR"
cd "$YUE_ROOT/inference"

python infer.py \\
  --cuda_idx "$CUDA_IDX" \\
  --stage1_model "\${YUE_STAGE1_MODEL:-m-a-p/YuE-s1-7B-anneal-en-icl}" \\
  --stage2_model "\${YUE_STAGE2_MODEL:-m-a-p/YuE-s2-1B-general}" \\
  --genre_txt "$PACKAGE_DIR/genre.txt" \\
  --lyrics_txt "$PACKAGE_DIR/lyrics.txt" \\
  --run_n_segments "\${YUE_SEGMENTS:-${segments}}" \\
  --stage2_batch_size "\${YUE_STAGE2_BATCH_SIZE:-4}" \\
  --output_dir "$OUTPUT_DIR" \\
  --max_new_tokens "\${YUE_MAX_NEW_TOKENS:-${maxNewTokens}}" \\
  --repetition_penalty "\${YUE_REPETITION_PENALTY:-${repetitionPenalty}}" \\
  --use_dual_tracks_prompt \\
  --vocal_track_prompt_path "$PACKAGE_DIR/vocals.wav" \\
  --instrumental_track_prompt_path "$PACKAGE_DIR/instrumental.wav" \\
  --prompt_start_time 0 \\
  --prompt_end_time ${promptEndTime}
`;
}

function readme({ reference, start, duration, segments, maxNewTokens, prompt, hasDualTrack }) {
  return `# YuE ICL Test Package

Reference: ${reference}
Reference window: ${start}s to ${start + duration}s
YuE generation segments: ${segments}
Max new tokens per run: ${maxNewTokens}
User direction: ${prompt || '(none)'}

## Where to run this

Run this folder on a CUDA GPU machine. Recommended first choice: RunPod pod with RTX 4090, A6000, A40, L40S, A100, or H100.

## Files

- reference-30s.wav: mixed reference prompt for single-track ICL
- genre.txt: style and safety brief
- lyrics.txt: original lyrics scaffold, no copied lyrics
- run-yue-single-track.sh: YuE mix-prompt ICL command
- run-yue-dual-track.sh: YuE vocal+instrumental ICL command
${hasDualTrack ? '- vocals.wav / instrumental.wav: dual-track prompt stems\n' : '- dual-track stems are not included yet\n'}
## First command to try on the GPU machine

\`\`\`bash
bash ${hasDualTrack ? 'run-yue-dual-track.sh' : 'run-yue-single-track.sh'}
\`\`\`

## GPU setup outline

\`\`\`bash
git clone https://github.com/multimodal-art-projection/YuE.git "$HOME/YuE"
cd "$HOME/YuE"
# Follow the official YuE CUDA, PyTorch, requirements, and flash-attn setup for your GPU image.
\`\`\`

The generated WAVs will appear under output-single-track/ or output-dual-track/.

## Scaling to full songs

Keep the reference prompt window at 30 seconds, but increase generated structure with:

\`\`\`bash
YUE_SEGMENTS=8 YUE_MAX_NEW_TOKENS=3000 bash run-yue-single-track.sh
\`\`\`

For the final product target, this package should be fed by a full arrangement analysis file that describes intro, hook, break, breakdown, drop, and outro timing.
`;
}

function fail(message) {
  console.error(`error: ${message}`);
  process.exitCode = 2;
  return 2;
}

function printHelp() {
  console.log(`Usage:
  npm run yue:prepare -- --reference "/absolute/path/song.wav" --output-dir tmp/yue-tests/name --start 0 --duration 30 --prompt "same groove, new bass variation"

Options:
  --reference <path>       Absolute reference audio path.
  --output-dir <path>      Package output directory.
  --start <seconds>        Reference window start. Default: 0.
  --duration <seconds>     Reference prompt duration, max 30. Default: 30.
  --segments <n>           YuE generation segments. Default: 2 for first tests; increase later for full songs.
  --max-new-tokens <n>     YuE token budget. Default: 3000.
  --repetition-penalty <n> YuE repetition penalty. Default: 1.1.
  --prompt <text>          Creative direction appended to genre.txt.
  --genre <text>           Override genre.txt content.
  --lyrics <text>          Override lyrics.txt content.
  --vocals <path>          Optional existing vocals stem for dual-track ICL.
  --instrumental <path>    Optional existing instrumental/no-vocals stem for dual-track ICL.`);
}

main().then((code) => {
  process.exitCode = code;
}).catch((error) => fail(error.message || String(error)));
