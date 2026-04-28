const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { describe, it } = require('node:test');
const { findFfmpeg } = require('../lib/audioInput');
const { createApp, promptOnlyAnalysis } = require('../server');

describe('prompt2midi local API', () => {
  it('starts a prompt-only job and returns producer prompt output', async () => {
    const server = await listen(createApp());
    try {
      const start = await request(server, 'POST', '/analyze', {
        prompt: 'dark groovy tech house at 124 BPM in A minor'
      });

      assert.equal(start.statusCode, 202);
      assert.equal(start.body.status, 'queued');
      assert.ok(start.body.job_id);

      const status = await waitForStatus(server, start.body.job_id, 'succeeded');
      assert.equal(status.body.progress, 100);

      const result = await request(server, 'GET', `/result?id=${start.body.job_id}`);
      assert.equal(result.statusCode, 200);
      assert.equal(result.body.result.analysis.bpm, 124);
      assert.equal(result.body.result.analysis.key, 'A minor');
      assert.match(result.body.result.interpretation.ai_music_prompt, /124 BPM/);
    } finally {
      await close(server);
    }
  });

  it('rejects missing input with a structured error', async () => {
    const server = await listen(createApp());
    try {
      const response = await request(server, 'POST', '/analyze', {});
      assert.equal(response.statusCode, 400);
      assert.equal(response.body.error.code, 'missing_input');
    } finally {
      await close(server);
    }
  });

  it('rejects invalid JSON as a client error', async () => {
    const server = await listen(createApp());
    try {
      const response = await rawRequest(server, 'POST', '/analyze', '{');
      assert.equal(response.statusCode, 400);
      assert.equal(response.body.error.code, 'invalid_json');
    } finally {
      await close(server);
    }
  });

  it('rejects unsupported audio paths before running analysis', async () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'prompt2midi-api-'));
    const textPath = path.join(tempDir, 'notes.txt');
    fs.writeFileSync(textPath, 'not audio');

    const server = await listen(createApp());
    try {
      const response = await request(server, 'POST', '/analyze', { audioPath: textPath });
      assert.equal(response.statusCode, 400);
      assert.equal(response.body.error.code, 'unsupported_format');
    } finally {
      await close(server);
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it('runs the real Python bridge for a WAV file', async () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'prompt2midi-api-'));
    const audioPath = path.join(tempDir, 'pulse.wav');
    writePulseWav(audioPath, 120);

    const server = await listen(createApp());
    try {
      const start = await request(server, 'POST', '/analyze', {
        audioPath,
        prompt: 'groovy reference'
      });

      assert.equal(start.statusCode, 202);
      await waitForStatus(server, start.body.job_id, 'succeeded', 80);

      const result = await request(server, 'GET', `/result?id=${start.body.job_id}`);
      assert.equal(result.statusCode, 200);
      assert.ok(result.body.result.analysis.bpm);
      assert.ok(result.body.result.analysis.bpm_confidence > 0);
      assert.ok(result.body.result.midi_files.reference_sketch.endsWith('reference-sketch.mid'));
      assert.ok(fs.existsSync(result.body.result.midi_files.reference_sketch));
      assert.ok(result.body.result.midi_files.bass_transcription.endsWith('bass-transcription.mid'));
      assert.ok(fs.existsSync(result.body.result.midi_files.bass_transcription));
      assert.match(result.body.result.midi_notes.join(' '), /experimental monophonic/i);
    } finally {
      await close(server);
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it('decodes MP3 through ffmpeg before running analysis when available', async (t) => {
    const ffmpeg = await findFfmpeg();
    if (!ffmpeg) {
      t.skip('ffmpeg is not installed');
      return;
    }

    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'prompt2midi-api-'));
    const wavPath = path.join(tempDir, 'pulse.wav');
    const mp3Path = path.join(tempDir, 'pulse.mp3');
    writePulseWav(wavPath, 120);
    const convert = spawnSync(ffmpeg, ['-y', '-hide_banner', '-loglevel', 'error', '-i', wavPath, mp3Path]);
    assert.equal(convert.status, 0, convert.stderr.toString());

    const server = await listen(createApp());
    try {
      const start = await request(server, 'POST', '/analyze', { audioPath: mp3Path });
      assert.equal(start.statusCode, 202);
      await waitForStatus(server, start.body.job_id, 'succeeded', 80);

      const result = await request(server, 'GET', `/result?id=${start.body.job_id}`);
      assert.equal(result.statusCode, 200);
      assert.equal(result.body.result.analysis.original_source_path, mp3Path);
      assert.ok(result.body.result.analysis.decoded_source_path.endsWith('decoded-input.wav'));
      assert.ok(result.body.result.analysis.warnings.some((warning) => warning.includes('ffmpeg')));
    } finally {
      await close(server);
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });
});

describe('prompt-only analysis', () => {
  it('extracts bpm and key when present', () => {
    const analysis = promptOnlyAnalysis('uplifting 132 BPM in F# minor');
    assert.equal(analysis.bpm, 132);
    assert.ok(analysis.bpm_confidence > 0);
    assert.equal(analysis.key, 'F# minor');
  });
});

function listen(server) {
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => resolve(server));
  });
}

function close(server) {
  return new Promise((resolve, reject) => {
    server.close((error) => error ? reject(error) : resolve());
  });
}

async function waitForStatus(server, jobId, expected, attempts = 20) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const response = await request(server, 'GET', `/status?id=${jobId}`);
    if (response.body.status === expected) return response;
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  throw new Error(`Timed out waiting for ${expected}`);
}

function request(server, method, path, body) {
  return rawRequest(server, method, path, body ? JSON.stringify(body) : undefined);
}

function rawRequest(server, method, path, body) {
  const { port } = server.address();
  return new Promise((resolve, reject) => {
    const req = globalThis.fetch(`http://127.0.0.1:${port}${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body
    });
    req.then(async (response) => {
      resolve({ statusCode: response.status, body: await response.json() });
    }, reject);
  });
}

function writePulseWav(filePath, bpm) {
  const sampleRate = 8000;
  const seconds = 4;
  const sampleCount = sampleRate * seconds;
  const dataSize = sampleCount * 2;
  const buffer = Buffer.alloc(44 + dataSize);

  buffer.write('RIFF', 0);
  buffer.writeUInt32LE(36 + dataSize, 4);
  buffer.write('WAVE', 8);
  buffer.write('fmt ', 12);
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20);
  buffer.writeUInt16LE(1, 22);
  buffer.writeUInt32LE(sampleRate, 24);
  buffer.writeUInt32LE(sampleRate * 2, 28);
  buffer.writeUInt16LE(2, 32);
  buffer.writeUInt16LE(16, 34);
  buffer.write('data', 36);
  buffer.writeUInt32LE(dataSize, 40);

  const beatInterval = 60 / bpm;
  for (let index = 0; index < sampleCount; index += 1) {
    const time = index / sampleRate;
    const beatPhase = time % beatInterval;
    const envelope = beatPhase < 0.06 ? 1 : 0.08;
    const tone = Math.sin(2 * Math.PI * 220 * time);
    buffer.writeInt16LE(Math.max(-32767, Math.min(32767, Math.round(envelope * tone * 32767))), 44 + index * 2);
  }

  fs.writeFileSync(filePath, buffer);
}
