#!/usr/bin/env node

const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { generateAceBrief } = require('../../backend/lib/geminiAceBriefGenerator');

const repoRoot = path.resolve(__dirname, '..', '..');
const referenceRunner = path.join(repoRoot, 'scripts', 'pipelines', 'run-reference-pipeline.js');
const proxyPackager = path.join(repoRoot, 'scripts', 'packaging', 'prepare-suno-proxy.js');
const STABLE_CONTINUATION_SOURCE_CONTROLS = {
  referenceStrength: 0.56,
  coverNoiseStrength: 0.2,
};

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printHelp();
    return 0;
  }

  const reference = args.reference || args.audio;
  const outputDir = args.outputDir || args.output;
  const prompt = args.prompt || defaultPrompt();
  let level = args.similarityLevel || args.level || 'medium-high';
  let effectivePrompt = prompt;
  const duration = args.duration || '30';
  const candidates = args.candidates || '4';
  const packCandidate = Number.parseInt(args.packCandidate || args.selectCandidate || '0', 10);
  const fullTrackStrategy = normalizeFullTrackStrategy(args.fullTrackStrategy || process.env.PROMPT2MIDI_FULL_TRACK_STRATEGY || 'continuation');

  if (!reference || !outputDir) return fail('Missing required --reference and --output-dir.');
  if (!path.isAbsolute(reference)) return fail('--reference must be an absolute path.');
  if (!fs.existsSync(reference)) return fail(`Reference file does not exist: ${reference}`);

  const runDir = path.resolve(outputDir);
  fs.mkdirSync(runDir, { recursive: true });
  console.error('progress: preparing reference audio for ACE generation');
  const generationReference = await prepareReferenceForGeneration(reference, runDir);
  console.error('progress: reference audio ready for ACE generation');
  const geminiEnabled = Boolean(args.geminiBrief || args.geminiControl);
  if (geminiEnabled) {
    const gemini = await buildGeminiBrief({
      generationReference,
      runDir,
      prompt,
      level,
      duration,
      candidates,
      args,
    });
    if (gemini && gemini.status === 'succeeded') {
      effectivePrompt = mergeGeminiPrompt(prompt, gemini.ace_prompt_addition);
      if (args.geminiControl && gemini.ace_controls) {
        const controls = gemini.ace_controls;
        if (controls.reference_strength !== undefined) {
          process.env.PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH = String(controls.reference_strength);
        }
        if (controls.cover_noise_strength !== undefined) {
          process.env.PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH = String(controls.cover_noise_strength);
        }
        if (controls.similarity_level) level = controls.similarity_level;
        console.error(`progress: Gemini experimental controls applied${controls.reason ? ` — ${controls.reason}` : ''}`);
      }
      console.error('progress: Gemini ACE brief added to generation prompt');
    } else if (gemini) {
      console.error(`warning: Gemini ACE brief skipped: ${gemini.reason || gemini.error || gemini.status}`);
    }
  }

  process.env.PROMPT2MIDI_RICH_REFERENCE_COVER = process.env.PROMPT2MIDI_RICH_REFERENCE_COVER || '1';
  process.env.PROMPT2MIDI_REFERENCE_SECTION_STRATEGY = process.env.PROMPT2MIDI_REFERENCE_SECTION_STRATEGY || 'early_character';

  const generationOptions = {
    generationReference,
    runDir,
    level,
    effectivePrompt,
    candidates,
    duration,
    packCandidate,
    args,
  };
  let proxyAudio = null;
  let usedOneShotFull = false;
  const shouldTryOneShot = args.extendFullTrack && String(duration).toLowerCase() === 'full' && fullTrackStrategy !== 'continuation';
  if (shouldTryOneShot) {
    console.error('progress: full-track strategy: trying experimental one-shot full render first');
    const oneShotEnv = { ...process.env };
    delete oneShotEnv.PROMPT2MIDI_REFERENCE_SAMPLE_MAX_DURATION;
    oneShotEnv.PROMPT2MIDI_FULL_TRACK_STRATEGY = 'one-shot';
    const oneShotCode = await runReferenceGeneration(generationOptions, oneShotEnv);
    if (oneShotCode === 0) {
      proxyAudio = chooseProxyAudio(runDir, packCandidate);
      usedOneShotFull = Boolean(proxyAudio);
      if (usedOneShotFull) console.error('progress: full-track strategy: one-shot full render succeeded');
    }
    if (!usedOneShotFull) {
      if (fullTrackStrategy === 'one-shot') return oneShotCode || fail('One-shot full render finished without a generated proxy candidate.');
      console.error('warning: one-shot full render failed or produced no candidate; falling back to continuation strategy');
    }
  }

  if (!proxyAudio) {
    const fallbackEnv = { ...process.env };
    if (args.extendFullTrack && String(duration).toLowerCase() === 'full') {
      fallbackEnv.PROMPT2MIDI_REFERENCE_SAMPLE_MAX_DURATION = String(
        process.env.PROMPT2MIDI_REFERENCE_SAMPLE_MAX_DURATION || process.env.PROMPT2MIDI_FULL_TRACK_SEED_SECONDS || '120'
      );
      fallbackEnv.PROMPT2MIDI_FULL_TRACK_STRATEGY = 'continuation';
      clampContinuationSourceControls(fallbackEnv);
      console.error(`progress: full-track strategy: generating ${fallbackEnv.PROMPT2MIDI_REFERENCE_SAMPLE_MAX_DURATION}s coherent seed for continuation`);
    }
    const generationCode = await runReferenceGeneration(generationOptions, fallbackEnv);
    if (generationCode !== 0) return generationCode;
    proxyAudio = chooseProxyAudio(runDir, packCandidate);
  }
  if (!proxyAudio) return fail(`No generated ACE proxy candidate found under ${path.join(runDir, 'exports')}.`);

  if (args.extendFullTrack && String(duration).toLowerCase() === 'full' && !usedOneShotFull && process.env.PROMPT2MIDI_ENABLE_REPAINT_EXTENSION === '1') {
    proxyAudio = await extendProxyToReferenceLength({
      proxyAudio,
      reference,
      runDir,
      effectivePrompt,
    });
  } else if (args.extendFullTrack && String(duration).toLowerCase() === 'full' && !usedOneShotFull) {
    console.error('warning: full-track repaint extension skipped by default on local MPS to avoid GPU out-of-memory; packaging the coherent seed and full SUNO prompt instead');
  }

  let candidateAssets = null;
  if (args.mapStems || process.env.PROMPT2MIDI_MAP_ACE_STEMS === '1') {
    candidateAssets = await mapCandidateAssets({
      runDir,
      effectivePrompt,
      level,
    });
    if (!candidateAssets.ok) return candidateAssets.code || 1;
  }

  const packageDir = path.join(runDir, 'suno-proxy-package');
  console.error('progress: preparing Suno proxy package');
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
    effectivePrompt,
  ];
  const packageCode = await run('node', packageArgs);
  if (packageCode !== 0) return packageCode;
  console.error('progress: Suno proxy package ready');

  console.log(JSON.stringify({
    ok: true,
    reference_local_only: reference,
    generated_proxy_audio: proxyAudio,
    suno_package_dir: packageDir,
    upload: path.join(packageDir, 'suno-upload-proxy.wav'),
    prompt: path.join(packageDir, 'suno-proxy-prompt.md'),
    ace_candidate_assets: candidateAssets ? candidateAssets.manifest : null,
    gemini: geminiEnabled ? path.join(runDir, 'gemini-ace-brief.json') : null,
  }, null, 2));
  return 0;
}

async function runReferenceGeneration(options, env) {
  const generationArgs = buildGenerationArgs(options);
  console.error('progress: local analysis and ACE generation started');
  const generationCode = await run('node', generationArgs, env);
  if (generationCode === 0) console.error('progress: ACE generation finished; selecting proxy audio');
  return generationCode;
}

function buildGenerationArgs({ generationReference, runDir, level, effectivePrompt, candidates, duration, packCandidate, args }) {
  const generationArgs = [
    referenceRunner,
    '--reference',
    generationReference,
    '--output-dir',
    runDir,
    '--similarity-level',
    level,
    '--prompt',
    effectivePrompt,
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
  if (args.seed) generationArgs.push('--seed', args.seed);
  return generationArgs;
}

async function mapCandidateAssets({ runDir, effectivePrompt, level }) {
  const candidates = collectCandidateAudios(runDir);
  if (!candidates.length) return { ok: false, code: fail(`No generated ACE candidates found under ${path.join(runDir, 'exports')}.`) };

  const root = path.join(runDir, 'ace-candidate-assets');
  fs.mkdirSync(root, { recursive: true });
  const manifest = {
    ok: true,
    method: 'per_candidate_ace_output_assets_v1',
    candidates: [],
    warnings: [
      'Stem/MIDI assets are generated from ACE candidate audio, not the original reference.',
      'Source transcription MIDI remains debug/review-only until the house-aware MIDI validator promotes it.',
    ],
  };

  for (const candidate of candidates) {
    const label = `candidate-${candidate.index}`;
    const candidateDir = path.join(root, label);
    const stemMapDir = path.join(candidateDir, 'stem-map');
    const analysisDir = path.join(candidateDir, 'analysis');
    fs.mkdirSync(candidateDir, { recursive: true });

    console.error(`progress: mapping stems for ${label}`);
    const mapCode = await run('uv', [
      'run',
      'python',
      '-m',
      'analysis.midi.ace_stem_mapping',
      '--audio',
      candidate.path,
      '--output-dir',
      stemMapDir,
    ]);
    if (mapCode !== 0) return { ok: false, code: mapCode };

    console.error(`progress: analyzing generated MIDI/debug assets for ${label}`);
    const analysisEnv = {
      ...process.env,
      PROMPT2MIDI_SKIP_REFERENCE_SAMPLE: '1',
    };
    const analysisCode = await run('uv', [
      'run',
      'python',
      '-m',
      'analysis.analyze',
      '--audio',
      candidate.path,
      '--output-dir',
      analysisDir,
      '--user-prompt',
      effectivePrompt,
      '--similarity-level',
      String(level || 'medium'),
    ], analysisEnv);
    if (analysisCode !== 0) return { ok: false, code: analysisCode };

    manifest.candidates.push({
      index: candidate.index,
      audio: candidate.path,
      suggested: candidate.suggested,
      selected: candidate.selected,
      stem_map: path.join(stemMapDir, 'ace-stem-midi-map.json'),
      stems_dir: path.join(stemMapDir, 'stems'),
      analysis_dir: analysisDir,
      analysis_exports: path.join(analysisDir, 'exports'),
      source_debug_midi: {
        bass: path.join(analysisDir, 'source-bass-transcription.mid'),
        drums: path.join(analysisDir, 'source-drum-groove.mid'),
        full_mix_model: path.join(analysisDir, 'model-transcription.mid'),
      },
      generated_midi_package: path.join(analysisDir, 'exports', 'midi'),
    });
  }

  const manifestPath = path.join(root, 'candidate-assets-manifest.json');
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  return { ok: true, manifest: manifestPath };
}

async function extendProxyToReferenceLength({ proxyAudio, reference, runDir, effectivePrompt }) {
  const targetDuration = await audioDurationSeconds(reference).catch(() => null);
  const proxyDuration = await audioDurationSeconds(proxyAudio).catch(() => null);
  if (!targetDuration || !proxyDuration) {
    console.error('warning: full-track extension skipped because audio duration could not be measured');
    return proxyAudio;
  }
  if (targetDuration <= proxyDuration + 5) {
    console.error(`progress: full-track extension skipped: generated proxy already covers ${proxyDuration.toFixed(1)}s of ${targetDuration.toFixed(1)}s`);
    return proxyAudio;
  }

  const extensionDir = path.join(runDir, 'exports', 'full-track-extension');
  const analysisJson = path.join(runDir, 'exports', 'fast-analysis.json');
  console.error(`progress: full-track extension: extending generated proxy from ${proxyDuration.toFixed(1)}s to ${targetDuration.toFixed(1)}s`);
  const code = await run(process.env.PROMPT2MIDI_ANALYSIS_PYTHON || process.env.PROMPT2MIDI_PYTHON || 'python3', [
    '-m',
    'analysis.generation.extend_repaint',
    '--source-audio',
    proxyAudio,
    '--output-dir',
    extensionDir,
    '--prompt',
    effectivePrompt,
    '--target-duration',
    String(targetDuration),
    '--analysis-json',
    analysisJson,
  ]);
  if (code !== 0) {
    process.exitCode = code;
    throw new Error(`Full-track extension exited with code ${code}`);
  }
  const extended = path.join(extensionDir, 'extended-full-track.wav');
  if (!fs.existsSync(extended)) {
    throw new Error(`Full-track extension finished but did not create ${extended}.`);
  }
  return extended;
}

function audioDurationSeconds(audioPath) {
  return new Promise((resolve, reject) => {
    const ffprobe = process.env.PROMPT2MIDI_FFPROBE || 'ffprobe';
    const child = spawn(ffprobe, [
      '-v',
      'error',
      '-show_entries',
      'format=duration',
      '-of',
      'default=nokey=1:noprint_wrappers=1',
      audioPath,
    ], { cwd: repoRoot, stdio: ['ignore', 'pipe', 'pipe'] });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => { stdout += chunk.toString(); });
    child.stderr.on('data', (chunk) => { stderr += chunk.toString(); });
    child.on('error', reject);
    child.on('exit', (code) => {
      if (code !== 0) {
        reject(new Error(stderr || `ffprobe exited with code ${code}`));
        return;
      }
      const value = Number.parseFloat(stdout.trim());
      if (!Number.isFinite(value)) reject(new Error(`Could not parse duration for ${audioPath}`));
      else resolve(value);
    });
  });
}

async function buildGeminiBrief({ generationReference, runDir, prompt, level, duration, args }) {
  const preflightDir = path.join(runDir, '_gemini-preflight');
  fs.mkdirSync(preflightDir, { recursive: true });
  console.error('progress: Gemini preflight analysis');
  const preflightArgs = [
    referenceRunner,
    '--reference',
    generationReference,
    '--output-dir',
    preflightDir,
    '--similarity-level',
    level,
    '--prompt',
    prompt,
    '--fast-sample',
    '--duration',
    duration,
  ];
  if (args.vocals) preflightArgs.push('--vocals');
  if (args.instrumental) preflightArgs.push('--instrumental');
  if (args.referenceStart) preflightArgs.push('--reference-start', args.referenceStart);
  if (args.referenceStrategy) preflightArgs.push('--reference-strategy', args.referenceStrategy);

  const env = { ...process.env };
  delete env.PROMPT2MIDI_ENABLE_ACE_STEP;
  delete env.PROMPT2MIDI_ENABLE_AUDIOCRAFT;
  delete env.PROMPT2MIDI_ENABLE_MUSICGEN;
  const code = await run('node', preflightArgs, env);
  if (code !== 0) return { status: 'failed', error: `preflight analysis exited with code ${code}` };

  const runOutputPath = path.join(preflightDir, 'run-output.json');
  if (!fs.existsSync(runOutputPath)) return { status: 'failed', error: 'preflight run-output.json missing' };
  const runOutput = JSON.parse(fs.readFileSync(runOutputPath, 'utf8'));
  if (!runOutput.ok) return { status: 'failed', error: runOutput.error && runOutput.error.message || 'preflight analysis failed' };

  console.error(args.geminiControl ? 'progress: Gemini ACE brief + experimental controls' : 'progress: Gemini ACE brief');
  try {
    return await generateAceBrief({
      analysis: runOutput.analysis || {},
      userPrompt: prompt,
      similarityLevel: level,
      duration: numericDuration(duration),
      referenceStart: args.referenceStart ? Number.parseFloat(args.referenceStart) : null,
      vocals: Boolean(args.vocals),
      controls: {
        reference_strength: Number.parseFloat(process.env.PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH || ''),
        cover_noise_strength: Number.parseFloat(process.env.PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH || ''),
      },
      allowControl: Boolean(args.geminiControl),
      outputDir: runDir,
    });
  } catch (error) {
    return { status: 'failed', error: error.message || String(error) };
  }
}

function mergeGeminiPrompt(userPrompt, geminiBrief) {
  const base = String(userPrompt || '').trim();
  const brief = String(geminiBrief || '').trim();
  if (!brief) return base;
  if (!base) return `Gemini producer brief for ACE: ${brief}`;
  return `${base}. Gemini producer brief for ACE: ${brief}`;
}

function numericDuration(value) {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : null;
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

function collectCandidateAudios(runDir) {
  const exportsDir = path.join(runDir, 'exports');
  const manifestPath = path.join(exportsDir, 'candidate-manifest.json');
  const byIndex = new Map();
  let selectedPath = null;
  let suggestedPath = null;
  if (fs.existsSync(manifestPath)) {
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    selectedPath = manifest.selected_candidate && manifest.selected_candidate.path || null;
    suggestedPath = manifest.suggested_candidate && manifest.suggested_candidate.path || null;
    for (const item of manifest.candidates || []) {
      const index = Number.parseInt(item.index || item.candidate || '0', 10);
      const candidatePath = item.path;
      if (index > 0 && candidatePath && fs.existsSync(candidatePath)) {
        byIndex.set(index, {
          index,
          path: candidatePath,
          selected: candidatePath === selectedPath,
          suggested: candidatePath === suggestedPath,
        });
      }
    }
  }
  for (let index = 1; index <= 12; index += 1) {
    const candidatePath = path.join(exportsDir, `candidate-${index}.wav`);
    if (fs.existsSync(candidatePath) && !byIndex.has(index)) {
      byIndex.set(index, {
        index,
        path: candidatePath,
        selected: candidatePath === selectedPath,
        suggested: candidatePath === suggestedPath,
      });
    }
  }
  return Array.from(byIndex.values()).sort((a, b) => a.index - b.index);
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
    else if (arg === '--gemini-brief') parsed.geminiBrief = true;
    else if (arg === '--gemini-control') {
      parsed.geminiBrief = true;
      parsed.geminiControl = true;
    }
    else if (arg === '--map-stems') parsed.mapStems = true;
    else if (arg === '--extend-full-track') parsed.extendFullTrack = true;
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

function normalizeFullTrackStrategy(value) {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'one-shot' || normalized === 'oneshot') return 'one-shot';
  if (normalized === 'continuation' || normalized === 'extend') return 'continuation';
  return 'continuation';
}

function clampContinuationSourceControls(env) {
  const currentReference = Number.parseFloat(env.PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH || '');
  const currentNoise = Number.parseFloat(env.PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH || '');
  const nextReference = Number.isFinite(currentReference)
    ? Math.min(currentReference, STABLE_CONTINUATION_SOURCE_CONTROLS.referenceStrength)
    : STABLE_CONTINUATION_SOURCE_CONTROLS.referenceStrength;
  const nextNoise = Number.isFinite(currentNoise)
    ? Math.min(currentNoise, STABLE_CONTINUATION_SOURCE_CONTROLS.coverNoiseStrength)
    : STABLE_CONTINUATION_SOURCE_CONTROLS.coverNoiseStrength;
  if (nextReference !== currentReference || nextNoise !== currentNoise) {
    console.error(
      `warning: full-track continuation fallback lowered source controls to ` +
      `${nextReference}/${nextNoise} for local generator stability`
    );
  }
  env.PROMPT2MIDI_ACE_STEP_REFERENCE_STRENGTH = String(nextReference);
  env.PROMPT2MIDI_ACE_STEP_COVER_NOISE_STRENGTH = String(nextNoise);
}

function run(command, args, env = process.env) {
  return new Promise((resolve) => {
    if (env.PROMPT2MIDI_TRACE_PROGRESS === '1' && path.basename(String(args[0] || '')) === 'run-reference-pipeline.js') {
      console.error(`trace: launching reference pipeline with trace progress enabled`);
    }
    const child = spawn(command, args, {
      cwd: repoRoot,
      env,
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
  --duration <seconds|full>     Defaults to 30; use full for one continuous reference-length render/package.
  --extend-full-track           With --duration full, extend the coherent seed toward the source duration using continuation chunks.
  --full-track-strategy <name>  auto, one-shot, or continuation. Auto tries one-shot first, then falls back.
  --candidates <n>              Defaults to 4.
  --pack-candidate <n>          Package a specific candidate after generation.
  --vocals                      Ask ACE for a new vocal hook; default is instrumental proxy for stability.
  --reference-start <seconds>   Force the local reference section used to condition ACE.
  --reference-strategy <name>   Section picker: early_character or stable_energy. Defaults to early_character.
  --steps <n>                   ACE inference steps.
  --guidance <n>                ACE guidance scale.
  --seed <n|-1>                 ACE seed. -1 keeps random generation.
  --map-stems                   Run ACE-output stem role detection and write ace-stem-midi-map.json.
  --gemini-brief                Use Gemini to create a richer ACE producer brief from local analysis + user direction.
  --gemini-control              Experimental: let Gemini suggest conservative ACE reference/noise controls too.`);
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
