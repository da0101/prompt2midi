const { spawn } = require('node:child_process');
const path = require('node:path');
const { prepareAudioForAnalysis } = require('./audioInput');

const repoRoot = path.resolve(__dirname, '..', '..');
const analysisScript = path.join(repoRoot, 'analysis', 'analyze.py');
const outputRoot = path.join(repoRoot, 'tmp', 'jobs');

async function runAnalysis(audioPath, jobId) {
  const outputDir = path.join(outputRoot, jobId);
  const prepared = await prepareAudioForAnalysis(audioPath, outputDir);
  return runPythonAnalysis(prepared.analysisPath, outputDir, {
    originalPath: audioPath,
    warnings: prepared.warnings
  });
}

function runPythonAnalysis(audioPath, outputDir, inputInfo) {
  return new Promise((resolve, reject) => {
    const child = spawn('python3', [analysisScript, '--audio', audioPath, '--output-dir', outputDir], {
      cwd: repoRoot,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString('utf8');
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString('utf8');
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
      if (inputInfo.originalPath && inputInfo.originalPath !== audioPath) {
        analysis.original_source_path = inputInfo.originalPath;
        analysis.decoded_source_path = audioPath;
      }
      if (inputInfo.warnings && inputInfo.warnings.length > 0) {
        analysis.warnings = [...(analysis.warnings || []), ...inputInfo.warnings];
      }

      resolve({
        analysis,
        midi_files: payload.midi_files || {},
        midi_notes: payload.midi_notes || []
      });
    });
  });
}

module.exports = { runAnalysis };
