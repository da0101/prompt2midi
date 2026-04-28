const { spawn } = require('node:child_process');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..', '..');
const analysisScript = path.join(repoRoot, 'analysis', 'analyze.py');
const outputRoot = path.join(repoRoot, 'tmp', 'jobs');

function runAnalysis(audioPath, jobId) {
  return new Promise((resolve, reject) => {
    const outputDir = path.join(outputRoot, jobId);
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

      resolve({
        analysis: payload.analysis,
        midi_files: payload.midi_files || {}
      });
    });
  });
}

module.exports = { runAnalysis };
