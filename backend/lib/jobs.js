const crypto = require('node:crypto');

function createJobStore() {
  const jobs = new Map();

  return {
    create(input) {
      const id = crypto.randomUUID();
      const now = new Date().toISOString();
      const job = {
        id,
        input,
        status: 'queued',
        progress: 0,
        message: 'Queued.',
        result: null,
        error: null,
        created_at: now,
        updated_at: now
      };
      jobs.set(id, job);
      return job;
    },

    get(id) {
      if (!id) return null;
      return jobs.get(id) || null;
    },

    update(id, patch) {
      const job = jobs.get(id);
      if (!job) return null;
      Object.assign(job, patch, { updated_at: new Date().toISOString() });
      return job;
    },

    all() {
      return Array.from(jobs.values());
    }
  };
}

module.exports = { createJobStore };
