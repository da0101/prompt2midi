const { spawn } = require('node:child_process');
const path = require('node:path');
const { prepareAudioForAnalysis } = require('./audioInput');

const repoRoot = path.resolve(__dirname, '..', '..');
const analysisScript = path.join(repoRoot, 'analysis', 'analyze.py');
const outputRoot = path.join(repoRoot, 'tmp', 'jobs');

async function runAnalysis(audioPath, jobId, log = null, userPrompt = '', similarityLevel = '') {
  const outputDir = path.join(outputRoot, jobId);
  if (log) log.stage('02.1 prepare audio', audioPath);
  const prepared = await prepareAudioForAnalysis(audioPath, outputDir);
  if (log) {
    log.done('02.1 prepare audio', prepared.analysisPath === audioPath ? 'native analysis file' : 'decoded with ffmpeg');
    for (const warning of prepared.warnings || []) log.warn(warning);
  }
  return runPythonAnalysis(prepared.analysisPath, outputDir, {
    originalPath: audioPath,
    warnings: prepared.warnings,
    userPrompt,
    similarityLevel
  }, log);
}

function runPythonAnalysis(audioPath, outputDir, inputInfo, log = null) {
  return new Promise((resolve, reject) => {
    if (log) log.stage('02.2 python engine', 'feature extraction + transcription');
    const userPromptArgs = inputInfo.userPrompt ? ['--user-prompt', inputInfo.userPrompt] : [];
    const similarityArgs = inputInfo.similarityLevel ? ['--similarity-level', inputInfo.similarityLevel] : [];
    const child = spawn('python3', [analysisScript, '--audio', audioPath, '--output-dir', outputDir, ...userPromptArgs, ...similarityArgs], {
      cwd: repoRoot,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString('utf8');
    });
    child.stderr.on('data', (chunk) => {
      const text = chunk.toString('utf8');
      stderr += text;
      if (log) streamPythonLog(text, log);
    });
    child.on('error', (error) => {
      reject(Object.assign(error, { code: 'python_unavailable' }));
    });
    child.on('close', (code) => {
      let payload;
      try {
        payload = JSON.parse(stdout);
      } catch (error) {
        return reject({
          code: 'invalid_analysis_output',
          message: stderr || stdout || 'Python analysis did not return JSON.'
        });
      }

      if (code !== 0 || !payload.ok) {
        const analysisError = payload.error || {};
        return reject({
          code: analysisError.code || 'analysis_failed',
          message: analysisError.message || stderr || 'Python analysis failed.'
        });
      }

      const analysis = payload.analysis || {};
      if (log) {
        log.done('02.2 python engine', summarizePayload(payload));
        for (const warning of analysis.warnings || []) log.warn(warning);
        for (const warning of (analysis.stem_separation && analysis.stem_separation.warnings) || []) log.warn(warning);
        for (const warning of (analysis.model_transcription && analysis.model_transcription.warnings) || []) log.warn(warning);
        const stems = analysis.stem_separation || {};
        if (stems.method) {
          const stemNames = Array.isArray(stems.stems) && stems.stems.length > 0 ? stems.stems.join(',') : 'none';
          log.info(`stem separation: ${stems.available ? 'on' : 'off'} method=${stems.method} stems=${stemNames}`);
        }
        const comp = payload.composition || {};
        if (comp.style) {
          log.info(`composition: style=${comp.style} key=${comp.key} bpm=${comp.bpm} bars=${comp.bars}`);
          for (const [track, filePath] of Object.entries(comp.midi || {})) {
            log.info(`composition output ${track}: ${filePath}`);
          }
        }
        const full = payload.full_arrangement || {};
        if (full.status) {
          log.info(`full arrangement: sections=${full.section_count || 0} bars=${full.total_bars || 'unknown'} level=${full.similarity_level || 'medium'}`);
          for (const [label, filePath] of Object.entries(full.paths || {})) {
            if (filePath) log.info(`full arrangement output ${label}: ${filePath}`);
          }
        }
        for (const asset of (payload.midi_assets || []).filter((item) => item.is_recommended_output)) {
          log.info(`recommended output ${asset.label || asset.key}: ${asset.path}${asset.note_count ? ` (${asset.note_count} notes)` : ''}`);
        }
      }
      if (inputInfo.originalPath && inputInfo.originalPath !== audioPath) {
        analysis.original_source_path = inputInfo.originalPath;
        analysis.decoded_source_path = audioPath;
      }
      if (inputInfo.warnings && inputInfo.warnings.length > 0) {
        analysis.warnings = [...(analysis.warnings || []), ...inputInfo.warnings];
      }

      resolve({
        analysis,
        composition: payload.composition || null,
        full_arrangement: payload.full_arrangement || null,
        suno_prompt: payload.suno_prompt || null,
        export_dir: payload.export_dir || null,
        midi_files: payload.midi_files || {},
        export_files: payload.export_files || {},
        midi_assets: payload.midi_assets || [],
        midi_notes: payload.midi_notes || []
      });
    });
  });
}

function streamPythonLog(text, log) {
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    if (/warning/i.test(trimmed)) log.warn(trimmed);
    else if (/^progress:/i.test(trimmed)) log.info(trimmed.replace(/^progress:\s*/i, ''));
    else log.info(`python: ${trimmed}`);
  }
}

function summarizePayload(payload) {
  const analysis = payload.analysis || {};
  const model = analysis.model_transcription || {};
  const stems = analysis.stem_separation || {};
  const files = Object.keys(payload.midi_files || {}).length;
  return `bpm=${analysis.bpm || 'unknown'} key=${analysis.key || 'unknown'} stems=${stems.available ? 'on' : 'off'} model=${model.available ? 'on' : 'off'} midi=${files}`;
}

module.exports = { runAnalysis };
