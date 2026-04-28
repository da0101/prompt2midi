const COLORS = {
  reset: '\x1b[0m',
  dim: '\x1b[2m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
  green: '\x1b[32m',
  magenta: '\x1b[35m',
  red: '\x1b[31m',
  yellow: '\x1b[33m'
};

function createPipelineLogger(jobId) {
  const startedAt = Date.now();
  const stageStarts = new Map();

  function line(color, icon, label, detail = '') {
    const elapsed = `${((Date.now() - startedAt) / 1000).toFixed(1)}s`.padStart(6);
    const prefix = `${COLORS.dim}${elapsed}${COLORS.reset} ${color}${icon} ${label}${COLORS.reset}`;
    console.log(detail ? `${prefix} ${detail}` : prefix);
  }

  return {
    banner(input) {
      console.log('');
      line(COLORS.cyan, '▶', `job ${jobId}`, input.audioPath ? `audio=${input.audioPath}` : 'prompt-only');
    },
    stage(name, detail = '') {
      stageStarts.set(name, Date.now());
      line(COLORS.blue, '◆', name, detail);
    },
    done(name, detail = '') {
      const stageStart = stageStarts.get(name) || startedAt;
      line(COLORS.green, '✓', name, `${detail}${detail ? ' · ' : ''}${Date.now() - stageStart}ms`);
    },
    warn(detail) {
      line(COLORS.yellow, '!', 'warning', detail);
    },
    info(detail) {
      line(COLORS.magenta, '·', 'detail', detail);
    },
    fail(error) {
      line(COLORS.red, '✕', `job ${jobId}`, error && (error.stack || error.message || error));
    },
    success(detail = '') {
      line(COLORS.green, '■', `job ${jobId} complete`, `${detail}${detail ? ' · ' : ''}${Date.now() - startedAt}ms total`);
      console.log('');
    }
  };
}

module.exports = { createPipelineLogger };
