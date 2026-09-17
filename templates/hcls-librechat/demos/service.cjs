/* Shared application service for the authenticated UI and per-user MCP. */
const fs = require('node:fs/promises');
const { createReadStream } = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawn } = require('node:child_process');
const ROOT = process.env.SCIENTIFIC_DEMOS_DIR || '/data/hcls-demos';
const PLATFORM = (process.env.SCIENTIFIC_MODELS_API_BASE_URL || 'https://89.169.99.188/v1').replace(/\/v1\/?$/, '');
const REPORT_MODEL = 'Qwen/Qwen3-235B-A22B-Instruct-2507';
const REPORT_PROVIDER = 'https://api.tokenfactory.nebius.com/v1';
const FILES = ['report.md', 'transcript.txt', 'follow-up.md', 'review.md', 'document.json', 'review.json', 'run.json'];
const hash = (text) => crypto.createHash('sha256').update(text).digest('hex');
const failure = (message, status = 400) => Object.assign(new Error(message), { status });
async function fileHash(filename) {
  const value = crypto.createHash('sha256');
  for await (const chunk of createReadStream(filename)) value.update(chunk);
  return value.digest('hex');
}

async function save(filename, value) {
  const temporary = `${filename}.${crypto.randomUUID()}.tmp`;
  await fs.writeFile(temporary, JSON.stringify(value, null, 2), { mode: 0o600 });
  await fs.rename(temporary, filename);
}
async function read(filename) { return JSON.parse(await fs.readFile(filename, 'utf8')); }
function directory(owner, id) {
  if (!owner || !/^[a-f0-9]{32}$/.test(id)) throw failure('Invalid job identity');
  return path.join(ROOT, hash(owner), id);
}
function privateKey(key) {
  if (!key || /\s/.test(key)) throw failure('Configure your Scientific AI API key in demo settings.', 401);
  return key;
}
async function platform(key, method, resource, body, idempotencyKey) {
  privateKey(key);
  const allowed = resource === '/v1/models' || /^\/v1\/workshop\/(catalog|runs(?:\/[a-f0-9-]{36}(?:\/(?:interventions|report|events))?)?)$/.test(resource);
  if (!allowed || !['GET', 'POST'].includes(method)) throw failure('Unsupported workshop operation');
  let response;
  try {
    response = await fetch(PLATFORM + resource, { method, redirect: 'error', signal: AbortSignal.timeout(45000),
      headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json',
        ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  } catch { throw failure('Platform connection interrupted. Check existing runs before retrying with the same request ID.', 503); }
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof result.detail === 'string' ? result.detail : result.error?.message;
    throw failure(detail || `Platform returned HTTP ${response.status}`, response.status);
  }
  return result;
}
async function status(owner, id) {
  const dir = directory(owner, id);
  let receipt;
  try { receipt = await read(path.join(dir, 'status.json')); }
  catch { throw failure('Clinical job not found', 404); }
  if (['running', 'queued'].includes(receipt.status)) {
    let alive = false;
    try { alive = (await fs.readFile(`/proc/${receipt.pid}/stat`, 'utf8')).split(' ')[21] === receipt.process_start; } catch { /* process exited */ }
    if (!alive) {
      const latest = await read(path.join(dir, 'status.json'));
      receipt = ['running', 'queued'].includes(latest.status) ? { ...latest, status: 'interrupted', error: 'Worker stopped. Resume this job; do not upload again.' } : latest;
    }
  }
  const available = [];
  for (const name of FILES) {
    try { await fs.access(path.join(dir, 'output', name)); available.push(name); } catch { /* not produced */ }
  }
  return { id, status: receipt.status, created_at: receipt.created_at, finished_at: receipt.finished_at,
    error: receipt.error, files: available, model: REPORT_MODEL,
    url: `/demos?tab=clinical&job=${id}`, clinical_validation: false };
}
async function list(owner) {
  const folder = path.join(ROOT, hash(owner));
  const entries = await fs.readdir(folder).catch(() => []);
  const jobs = await Promise.all(entries.filter((id) => /^[a-f0-9]{32}$/.test(id)).map((id) => status(owner, id)));
  return jobs.sort((a, b) => b.created_at.localeCompare(a.created_at));
}
async function start(owner, key, id) {
  const dir = directory(owner, id);
  const request = await read(path.join(dir, 'request.json'));
  if (request.key_hash !== hash(privateKey(key))) throw failure('Resume with the original submitting platform key.', 409);
  let lock;
  try { lock = await fs.open(path.join(dir, 'launch.lock'), 'wx', 0o600); }
  catch { throw failure('A launch is already in progress. Refresh job status.', 409); }
  try {
    const current = await status(owner, id);
    if (['completed', 'running', 'queued'].includes(current.status)) return current;
    await fs.unlink(path.join(dir, 'launched')).catch(() => {});
    const worker = spawn(process.execPath, [path.join(__dirname, 'worker.cjs'), dir], {
      detached: true, stdio: 'ignore', env: { PATH: process.env.PATH, LANG: 'C.UTF-8',
        FS2_API_KEY: key, CLINICAL_REPORT_API_KEY: process.env.NEBIUS_API_KEY || process.env.CLINICAL_REPORT_API_KEY || '',
        SCIENTIFIC_CLINICAL_PYTHON: process.env.SCIENTIFIC_CLINICAL_PYTHON || '/opt/clinical-client/bin/python',
        SCIENTIFIC_CLINICAL_SCRIPT: process.env.SCIENTIFIC_CLINICAL_SCRIPT || '/app/skill/clinical-documentation/scripts/clinical_report.py' },
    });
    await new Promise((resolve, reject) => { worker.once('spawn', resolve); worker.once('error', reject); });
    const processStart = (await fs.readFile(`/proc/${worker.pid}/stat`, 'utf8')).split(' ')[21];
    await save(path.join(dir, 'status.json'), { id, status: 'running', created_at: request.created_at,
      pid: worker.pid, process_start: processStart });
    // The child waits for this receipt, avoiding a fast-exit/parent-overwrite race.
    await fs.writeFile(path.join(dir, 'launched'), '', { mode: 0o600 });
    worker.unref();
    return status(owner, id);
  } finally { await lock.close(); await fs.unlink(path.join(dir, 'launch.lock')); }
}
async function clinical(owner, key, input) {
  privateKey(key);
  if (!['en', 'de'].includes(input.language)) throw failure('Choose English or German.');
  if (!['audio', 'transcript'].includes(input.kind)) throw failure('Choose audio or transcript.');
  if (!/^[A-Za-z0-9_.:-]{1,160}$/.test(input.idempotency_key || '')) throw failure('Supply an idempotency key.');
  if (!process.env.NEBIUS_API_KEY && !process.env.CLINICAL_REPORT_API_KEY) throw failure('The operator must configure the report provider credential.', 503);
  const ext = path.extname(input.filename || '').toLowerCase();
  if (!(input.kind === 'audio' ? ['.wav', '.flac', '.mp3', '.ogg', '.m4a', '.mp4', '.webm'] : ['.txt', '.json']).includes(ext)) throw failure('Unsupported input format.');
  const size = input.local_path ? (await fs.stat(input.local_path)).size : input.bytes?.length;
  if (!size || size > 512 * 1024 * 1024 || (!input.local_path && !Buffer.isBuffer(input.bytes))) throw failure('Upload a nonempty file, at most 512 MiB.');
  const id = hash(input.idempotency_key).slice(0, 32);
  const dir = directory(owner, id);
  const signature = hash(JSON.stringify([input.local_path ? await fileHash(input.local_path) : hash(input.bytes), input.kind, input.language]));
  await fs.mkdir(path.dirname(dir), { recursive: true, mode: 0o700 });
  try { await fs.mkdir(dir, { mode: 0o700 }); }
  catch (error) {
    if (error.code !== 'EEXIST') throw error;
    const existing = await read(path.join(dir, 'request.json')).catch(() => null);
    if (!existing) throw failure('Upload still being admitted; refresh and retry the same request ID.', 409);
    if (existing.signature !== signature || existing.key_hash !== hash(key)) throw failure('Request ID belongs to different input or credentials.', 409);
    return status(owner, id);
  }
  const source = `input${ext}`;
  if (input.local_path) await fs.copyFile(input.local_path, path.join(dir, source));
  else await fs.writeFile(path.join(dir, source), input.bytes, { mode: 0o600 });
  await fs.chmod(path.join(dir, source), 0o600);
  await save(path.join(dir, 'request.json'), { source, kind: input.kind, language: input.language,
    signature, key_hash: hash(key), created_at: new Date().toISOString(), platform: PLATFORM,
    report_model: REPORT_MODEL, report_provider: REPORT_PROVIDER });
  await save(path.join(dir, 'status.json'), { id, status: 'prepared', created_at: new Date().toISOString() });
  return start(owner, key, id);
}
async function output(owner, id, filename) {
  if (!FILES.includes(filename)) throw failure('Unknown report file', 404);
  try { return await fs.readFile(path.join(directory(owner, id), 'output', filename)); }
  catch (error) { if (error.code === 'ENOENT') throw failure('This report file has not been produced. Check job status.', 409); throw error; }
}
module.exports = { platform, clinical, status, list, start, output, save, read, failure, FILES, REPORT_MODEL };
