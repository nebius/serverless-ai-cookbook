/* Shared application service for the authenticated UI and per-user MCP. */
const fs = require('node:fs/promises');
const { createReadStream, constants } = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawn } = require('node:child_process');
const ROOT = process.env.SCIENTIFIC_DEMOS_DIR || '/data/hcls-demos';
const PLATFORM = (process.env.SCIENTIFIC_MODELS_API_BASE_URL || 'https://89.169.99.188/v1').replace(/\/v1\/?$/, '');
const REPORT_MODEL = 'Qwen/Qwen3-235B-A22B-Instruct-2507';
const REPORT_PROVIDER = 'https://api.tokenfactory.nebius.com/v1';
const FILES = ['report.md', 'transcript.txt', 'follow-up.md', 'review.md', 'document.json', 'review.json', 'run.json'];
const WORKSPACE = process.env.SCIENTIFIC_WORKSPACE || '/workspace';
const RUN_ID = /^[a-f0-9-]{36}$/i;
const TERMINAL_STATES = new Set(['succeeded', 'completed', 'failed', 'cancelled', 'preempted', 'expired']);
const hash = (text) => crypto.createHash('sha256').update(text).digest('hex');
const failure = (message, status = 400) => Object.assign(new Error(message), { status });
function publicError(error) {
  return { error: error.status === 500 || !error.status
    ? 'Workbench request failed. Refresh existing runs before submitting again.' : error.message,
  ...(error.code ? { code: error.code } : {}),
  ...(typeof error.retryable === 'boolean' ? { retryable: error.retryable } : {}),
  ...(typeof error.durable_admission === 'boolean' ? { durable_admission: error.durable_admission } : {}),
  ...(error.operation_id ? { operation_id: error.operation_id } : {}),
  ...(error.retry_after_seconds !== undefined ? { retry_after_seconds: error.retry_after_seconds } : {}) };
}
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
async function platform(key, method, resource, body, idempotencyKey, timeoutMs = 45000) {
  privateKey(key);
  const allowed = resource === '/v1/models' || resource === '/v1/scientific-models' || resource === '/v1/storage'
    || resource === '/v1/storage/credentials'
    || /^\/v1\/operations\?limit=\d{1,3}(?:&cursor=[A-Za-z0-9_-]{1,256})?$/.test(resource)
    || /^\/v1\/operations\/[a-f0-9-]{36}(?::cancel|\/(?:events|result))?$/.test(resource)
    || /^\/v1\/workshop\/(catalog|runs(?:\/[a-f0-9-]{36}(?:\/(?:interventions|report|events))?)?)$/.test(resource);
  if (!allowed || !['GET', 'POST'].includes(method)) throw failure('Unsupported platform operation');
  let response;
  try {
    response = await fetch(PLATFORM + resource, { method, redirect: 'error', signal: AbortSignal.timeout(timeoutMs),
      headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json',
        ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  } catch { throw failure('Platform connection interrupted. Check existing runs before retrying with the same request ID.', 503); }
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = result.error && typeof result.error === 'object' ? result.error
      : result.detail && typeof result.detail === 'object' ? result.detail : result;
    const message = typeof result.detail === 'string' ? result.detail
      : detail.message || detail.detail || `Platform returned HTTP ${response.status}`;
    const error = failure(typeof message === 'string' ? message : `Platform returned HTTP ${response.status}`, response.status);
    error.code = detail.code || detail.error_code;
    error.retryable = typeof detail.retryable === 'boolean' ? detail.retryable : undefined;
    error.durable_admission = typeof detail.durable_admission === 'boolean' ? detail.durable_admission : undefined;
    error.operation_id = RUN_ID.test(detail.operation_id || '') ? detail.operation_id : undefined;
    const retryAfter = Number(response.headers.get('retry-after') ?? detail.retry_after_seconds);
    if (Number.isFinite(retryAfter) && retryAfter >= 0) error.retry_after_seconds = retryAfter;
    throw error;
  }
  return result;
}

async function platformBytes(key, resource) {
  privateKey(key);
  if (!/^\/v1\/artifacts\/[a-f0-9-]{36}\/content$/.test(resource)) throw failure('Unsupported platform artifact operation');
  let response;
  try {
    response = await fetch(PLATFORM + resource, { method: 'GET', redirect: 'error', signal: AbortSignal.timeout(45000),
      headers: { Authorization: `Bearer ${key}` } });
  } catch { throw failure('Artifact download interrupted. Retry the same result lookup; do not resubmit compute.', 503); }
  if (!response.ok) throw failure(`Platform artifact returned HTTP ${response.status}`, response.status);
  return Buffer.from(await response.arrayBuffer());
}

async function listApps(key, query = '') {
  if (typeof query !== 'string' || query.length > 200) throw failure('Supply a short App name or capability.');
  const catalogs = await Promise.all([platform(key, 'GET', '/v1/models'), platform(key, 'GET', '/v1/scientific-models')]);
  const apps = new Map();
  for (const catalog of catalogs) for (const item of catalog.data || []) {
    const id = item.id || item.model_id;
    if (!id) continue;
    const previous = apps.get(id) || {};
    apps.set(id, { ...previous, model_id: id, display_name: item.display_name || previous.display_name || id,
      ...(item.protocols ? { protocols: item.protocols } : {}),
      ...(item.operations ? { operations: item.operations } : {}),
      ...(item.capabilities ? { capabilities: item.capabilities } : {}),
      ...(item.mcp_tool_name ? { tool_name: item.mcp_tool_name } : {}),
      ...(item.mcp_tool_description ? { description: item.mcp_tool_description.slice(0, 500) } : {}),
    });
  }
  const data = [...apps.values()].filter((item) => !query || JSON.stringify(item).toLowerCase().includes(query.toLowerCase()));
  return { data, count: data.length, discovery_only: true,
    next_step: 'Read get_model_schema for the chosen App only. This list proves authorization, not runtime readiness or scientific validity.' };
}

async function retainResult(key, operationId, bytes) {
  return retainWorkspaceBytes(key, `.scientific-runs/${operationId}/result.json`, bytes);
}

async function retainWorkspaceBytes(key, relativePath, bytes) {
  if (!(await workspaceInfo(key)).mounted) return { saved: false, reason: 'No mounted workspace; use the authenticated panel download.' };
  const target = workspacePath(relativePath);
  await fs.mkdir(path.dirname(target.absolute), { recursive: true, mode: 0o700 });
  const expected = hash(bytes);
  try { await fs.writeFile(target.absolute, bytes, { mode: 0o600, flag: 'wx' }); }
  catch (error) { if (error.code !== 'EEXIST') throw error; }
  const actual = await fileHash(target.absolute);
  if (actual !== expected) throw failure('Saved result differs from the verified platform output; existing file was not overwritten.', 409);
  return { saved: true, path: target.absolute, relative_path: target.normalized, size_bytes: bytes.length, sha256: actual };
}

async function workshopRun(key, runId) {
  if (!RUN_ID.test(runId || '')) throw failure('Invalid consultation identity');
  const run = await platform(key, 'GET', `/v1/workshop/runs/${runId}`);
  if (run.id !== runId) throw failure('Consultation identity mismatch', 409);
  const bytes = Buffer.from(JSON.stringify(run));
  // An in-progress consultation changes. Keep content-addressed versions rather
  // than overwriting prior turns, judgments or interventions on Object Storage.
  const workspace_file = await retainWorkspaceBytes(key,
    `.scientific-workshops/${runId}/${hash(bytes)}.json`, bytes);
  return { run, workspace_file };
}

function numberSummary(values, kind, shape) {
  const finite = values.filter(Number.isFinite);
  let min; let max; let sum = 0;
  for (const value of finite) {
    min = min === undefined || value < min ? value : min;
    max = max === undefined || value > max ? value : max;
    sum += value;
  }
  return { type: kind, count: values.length, ...(shape ? { shape } : {}),
    finite_count: finite.length,
    ...(finite.length ? { min, max, mean: sum / finite.length } : {}) };
}

function summarizeResult(value, depth = 0) {
  if (value === null || ['boolean', 'number'].includes(typeof value)) return value;
  if (typeof value === 'string') {
    if (value.length <= 2048) return value;
    return { type: 'long-string', characters: value.length, sha256: hash(value), preview: value.slice(0, 320) };
  }
  if (depth >= 8) return { type: Array.isArray(value) ? 'array' : 'object', omitted_below_depth: depth };
  if (Array.isArray(value)) {
    if (value.every((item) => typeof item === 'number')) return numberSummary(value, 'numeric-array');
    if (value.length && value.every((row) => Array.isArray(row) && row.every((item) => typeof item === 'number'))) {
      return numberSummary(value.flat(), 'numeric-matrix', [value.length, ...new Set(value.map((row) => row.length))]);
    }
    if (value.length > 20) return { type: 'array', count: value.length,
      first_items: value.slice(0, 5).map((item) => summarizeResult(item, depth + 1)) };
    return value.map((item) => summarizeResult(item, depth + 1));
  }
  if (typeof value === 'object') return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [key, summarizeResult(item, depth + 1)]),
  );
  return String(value);
}

function evidenceGuidance(value, summary, artifact) {
  const observations = [
    `The complete JSON result artifact was verified at ${artifact.size_bytes} bytes with SHA-256 ${artifact.sha256}.`,
  ];
  const structures = Array.isArray(value?.structures_in_ranked_order) ? value.structures_in_ranked_order : [];
  if (structures.length) {
    observations.push(`${structures.length} structure record(s) are present in this result; this does not define the App's maximum output count.`);
    const first = structures[0];
    if (typeof first.relaxed === 'boolean') observations.push(`The first structure's explicit relaxed field is ${first.relaxed}.`);
    if (typeof first.runtime_origin === 'string') observations.push(`The first structure's runtime_origin is ${first.runtime_origin}; the label alone does not describe supported inputs.`);
    if (summary?.structures_in_ranked_order?.[0]?.predicted_aligned_error?.type === 'numeric-matrix') {
      observations.push('The full predicted_aligned_error matrix remains in the verified JSON artifact; chat receives only its numeric summary.');
    }
    if (summary?.structures_in_ranked_order?.[0]?.structure?.type === 'long-string') {
      observations.push('The structure text remains in the verified JSON artifact; chat receives a hash, length and preview rather than the complete coordinate string.');
    }
  }
  return {
    observations,
    interpretation_boundaries: [
      'Do not infer unsupported inputs, modalities, chain counts, ligands, batching or output cardinality from fields absent in one result.',
      'source_artifact.size_bytes is the complete result JSON artifact size, not the size of a nested PDB, SDF, image or other scientific object.',
      'Do not claim a separate downloadable nested artifact unless an explicit artifact reference is present.',
      'Confidence and scoring fields are model outputs, not experimental or clinical validation.',
      'For App-wide capabilities or constraints, consult the live model schema or an identified primary source.',
    ],
  };
}

async function operationResult(key, operationId) {
  if (!RUN_ID.test(operationId || '')) throw failure('Supply a valid operation ID.');
  // The production API returns the result body directly. Older gateways and the
  // local fixture wrap it in { operation, result }, so accept both shapes while
  // independently binding the response to the requested operation identity.
  const [operationEnvelope, resultEnvelope] = await Promise.all([
    platform(key, 'GET', `/v1/operations/${operationId}`),
    platform(key, 'GET', `/v1/operations/${operationId}/result`),
  ]);
  const nestedOperation = operationEnvelope.operation;
  const operation = nestedOperation && typeof nestedOperation === 'object' ? nestedOperation : operationEnvelope;
  const resultOperation = resultEnvelope.operation;
  if (operation?.id !== operationId
      || (resultOperation && typeof resultOperation === 'object' && resultOperation.id !== operationId)) {
    throw failure('Platform returned a mismatched operation result.', 502);
  }
  const result = resultOperation && typeof resultOperation === 'object' ? resultEnvelope.result : resultEnvelope;
  if (result?.schema !== 'fs2-serve.nebius.ai/operation-artifact-result/v1') {
    const workspace_file = await retainResult(key, operationId, Buffer.from(JSON.stringify(result)));
    return { operation, result: summarizeResult(result), workspace_file };
  }
  const artifact = result.artifact || {};
  if (result.content_type !== 'application/json' || artifact.compression !== 'none'
      || !RUN_ID.test(artifact.artifact_id || '') || !Number.isInteger(artifact.size_bytes)
      || artifact.size_bytes < 0 || artifact.size_bytes > 8 * 1024 * 1024
      || !/^[a-f0-9]{64}$/.test(artifact.sha256 || '')) {
    return { operation, result: { ...result, resolution: 'Download in Runs; this artifact is not bounded JSON.' } };
  }
  const bytes = await platformBytes(key, `/v1/artifacts/${artifact.artifact_id}/content`);
  if (bytes.length !== artifact.size_bytes || hash(bytes) !== artifact.sha256) throw failure('Result artifact failed size or SHA-256 verification.', 502);
  let parsed;
  try { parsed = JSON.parse(bytes.toString('utf8')); }
  catch { throw failure('Result artifact was declared as JSON but could not be decoded.', 502); }
  const summary = summarizeResult(parsed);
  const workspace_file = await retainResult(key, operationId, bytes);
  return { operation, workspace_file, result: {
    schema: 'fs2-serve.nebius.ai/resolved-operation-result/v1', content_type: result.content_type,
    source_artifact: artifact, summary, evidence_guidance: evidenceGuidance(parsed, summary, artifact),
    resolution: 'Downloaded with caller credentials; size and SHA-256 verified; large arrays and strings summarized.',
  } };
}

function runFile(owner) {
  if (!owner) throw failure('LibreChat user identity is missing.', 401);
  return path.join(ROOT, 'workbench', hash(owner), 'runs.json');
}
function runDirectory(owner, key) {
  return path.join(path.dirname(runFile(owner)), 'runs', hash(privateKey(key)));
}
async function optionalRead(filename, fallback) {
  try { return await read(filename); }
  catch (error) { if (error.code === 'ENOENT') return fallback; throw error; }
}
async function tracked(owner, key) {
  const legacy = await optionalRead(runFile(owner), { data: [] });
  const folder = runDirectory(owner, key);
  let filenames;
  try { filenames = await fs.readdir(folder); }
  catch (error) { if (error.code !== 'ENOENT') throw error; filenames = []; }
  const current = await Promise.all(filenames.filter((name) => RUN_ID.test(name.replace(/\.json$/, ''))
    && name.endsWith('.json')).map((name) => read(path.join(folder, name))));
  // One atomic file per operation avoids lost updates when UI and MCP processes
  // save different operations concurrently. Legacy rows are reauthorized below.
  const data = new Map((legacy.data || []).map((item) => [item.id, { ...item, legacy: true }]));
  for (const item of current) data.set(item.id, item);
  return { data: [...data.values()] };
}
async function saveRun(owner, key, entry) {
  const folder = runDirectory(owner, key);
  await fs.mkdir(folder, { recursive: true, mode: 0o700 });
  await save(path.join(folder, entry.id + '.json'), entry);
}
function runEntry(operation, previous = {}, metadata = {}) {
  return {
    id: operation.id, model_id: operation.model_id || previous.model_id || metadata.model_id,
    protocol: operation.protocol || previous.protocol, status: operation.status,
    source: previous.source || metadata.source || 'workbench',
    label: typeof metadata.label === 'string' ? metadata.label.slice(0, 160) : previous.label,
    first_seen_at: previous.first_seen_at || new Date().toISOString(),
    accepted_at: operation.accepted_at || operation.created_at || previous.accepted_at,
    started_at: operation.started_at, completed_at: operation.completed_at,
    updated_at: new Date().toISOString(), operation,
  };
}
async function track(owner, key, operationId, metadata = {}, timeoutMs = 45000) {
  if (!RUN_ID.test(operationId || '')) throw failure('Supply a valid operation ID.');
  const current = await platform(key, 'GET', `/v1/operations/${operationId}`, undefined, undefined, timeoutMs);
  const operation = current.operation && typeof current.operation === 'object' ? current.operation : current;
  if (operation.id !== operationId) throw failure('Platform returned a mismatched operation.', 502);
  const existing = await optionalRead(path.join(runDirectory(owner, key), operationId + '.json'), {});
  const entry = runEntry(operation, existing, metadata);
  await saveRun(owner, key, entry);
  return { ...entry, ...(current.batch ? { batch: current.batch } : {}) };
}
async function waitOperation(owner, key, operationId, waitSeconds = 15) {
  if (!Number.isInteger(waitSeconds) || waitSeconds < 0 || waitSeconds > 30) throw failure('wait_seconds must be between 0 and 30.');
  const deadline = Date.now() + waitSeconds * 1000;
  const observations = [];
  let latest;
  do {
    latest = await track(owner, key, operationId, { source: 'agent' }, waitSeconds ? Math.max(1, deadline - Date.now()) : 45000);
    if (observations.at(-1)?.status !== latest.status) observations.push({ status: latest.status, observed_at: latest.updated_at });
    if (TERMINAL_STATES.has(latest.status) || Date.now() >= deadline) break;
    await new Promise((resolve) => setTimeout(resolve, Math.min(3000, deadline - Date.now())));
  } while (Date.now() <= deadline);
  return { ...latest, observations, terminal: TERMINAL_STATES.has(latest.status),
    next_step: TERMINAL_STATES.has(latest.status) ? 'Inspect the terminal state before retrieving output.'
      : 'Still accepted, not complete. Reconnect through Runs or use another bounded wait; do not resubmit or tight-loop polls.' };
}
async function runs(owner, key, { cursor, limit = 50 } = {}) {
  if (!Number.isInteger(limit) || limit < 1 || limit > 200
      || (cursor !== undefined && !/^[A-Za-z0-9_-]{1,256}$/.test(cursor))) {
    throw failure('Invalid operation history page.');
  }
  const existing = await tracked(owner, key);
  let history;
  try {
    history = await platform(key, 'GET', `/v1/operations?limit=${limit}${cursor ? `&cursor=${cursor}` : ''}`);
  } catch (error) {
    if (error.status !== 404) throw error;
    // Older deployments do not have discovery. Keep saved runs usable during a
    // rolling upgrade and state this limitation instead of pretending completeness.
    return { ...(await trackedRuns(owner, key, existing)), history_available: false,
      history_notice: 'Automatic history is unavailable on this platform version. Only explicitly saved runs are shown.',
      next_cursor: null };
  }
  if (!Array.isArray(history.data)) throw failure('Platform operation history has an invalid response.', 502);
  const byId = new Map(existing.data.map((item) => [item.id, item]));
  return { data: history.data.map((operation) => runEntry(operation, byId.get(operation.id), { source: 'platform' })),
    next_cursor: history.next_cursor || null, history_available: true };
}
async function trackedRuns(owner, key, existing) {
  const pending = [...existing.data].sort((a, b) => (b.accepted_at || b.first_seen_at || '')
    .localeCompare(a.accepted_at || a.first_seen_at || ''));
  const refreshed = [];
  // Bound platform fanout while preserving every saved operation. A terminal
  // operation is immutable; refresh its permission periodically, not every 5s.
  await Promise.all(Array.from({ length: Math.min(4, pending.length) }, async () => {
    while (pending.length) {
      const item = pending.shift();
      if (!item.legacy && item.operation && TERMINAL_STATES.has(item.status)
          && Date.now() - Date.parse(item.updated_at) < 60000) {
        refreshed.push(item); continue;
      }
      try {
        const value = await platform(key, 'GET', `/v1/operations/${item.id}`);
        const operation = value.operation && typeof value.operation === 'object' ? value.operation : value;
        if (operation.id !== item.id) throw failure('Platform returned a mismatched operation.', 502);
        const entry = runEntry(operation, item);
        await saveRun(owner, key, entry);
        refreshed.push(entry);
      } catch (error) {
        // A changed key must not expose previously attached another-tenant rows.
        if ([401, 403, 404].includes(error.status)) continue;
        if (!item.legacy) refreshed.push({ ...item, refresh_error: error.message, refresh_status: error.status || 500 });
      }
    }
  }));
  refreshed.sort((a, b) => (b.accepted_at || b.first_seen_at || '').localeCompare(a.accepted_at || a.first_seen_at || ''));
  return { data: refreshed };
}

function workspacePath(relative = '') {
  if (typeof relative !== 'string' || relative.length > 1024 || relative.includes('\0')) throw failure('Invalid workspace path.');
  const normalized = relative.replace(/^\/+/, '');
  if (normalized.split('/').some((part) => part === '..')) throw failure('Workspace paths cannot escape the bucket.');
  const absolute = path.resolve(WORKSPACE, normalized);
  if (absolute !== path.resolve(WORKSPACE) && !absolute.startsWith(path.resolve(WORKSPACE) + path.sep)) throw failure('Invalid workspace path.');
  return { normalized, absolute };
}
async function workspaceInfo(key) {
  let mounted = false;
  try { mounted = (await fs.stat(WORKSPACE)).isDirectory(); } catch { /* no endpoint mount */ }
  if (mounted) return { state: 'ready', mode: 'deployment', mounted: true, mount_path: WORKSPACE,
    team_id: process.env.TEAM_ID, team_bucket_name: process.env.TEAM_BUCKET_NAME };
  const storage = await platform(key, 'GET', '/v1/storage').catch((error) => ({ state: 'unavailable', error: error.message }));
  return { ...storage, mounted: false };
}
async function workspaceList(key, relative = '') {
  const info = await workspaceInfo(key);
  if (!info.mounted) throw failure('This deployment has no mounted workspace. Use the platform bucket credentials from your account until the shared-workbench S3 bridge is enabled.', 503);
  const target = workspacePath(relative);
  let entries;
  try { entries = await fs.readdir(target.absolute, { withFileTypes: true }); }
  catch (error) { if (error.code === 'ENOENT') throw failure('Workspace folder not found.', 404); throw error; }
  const data = await Promise.all(entries.slice(0, 500).map(async (entry) => {
    const stat = await fs.stat(path.join(target.absolute, entry.name));
    return { name: entry.name, path: [target.normalized, entry.name].filter(Boolean).join('/'),
      kind: entry.isDirectory() ? 'directory' : 'file', size_bytes: entry.isFile() ? stat.size : undefined,
      updated_at: stat.mtime.toISOString() };
  }));
  return { info, prefix: target.normalized, data: data.sort((a, b) => a.kind.localeCompare(b.kind) || a.name.localeCompare(b.name)) };
}
async function workspacePut(key, relative, localPath) {
  const info = await workspaceInfo(key);
  if (!info.mounted) throw failure('This deployment has no mounted workspace.', 503);
  const target = workspacePath(relative);
  if (!target.normalized) throw failure('Choose a file name.');
  await fs.mkdir(path.dirname(target.absolute), { recursive: true, mode: 0o700 });
  const source = await fs.stat(localPath);
  try { await fs.copyFile(localPath, target.absolute, constants.COPYFILE_EXCL); }
  catch (error) { if (error.code === 'EEXIST') throw failure('A workspace object already exists at this path. Choose a new name.', 409); throw error; }
  const stat = await fs.stat(target.absolute);
  const [expected, actual] = await Promise.all([fileHash(localPath), fileHash(target.absolute)]);
  if (stat.size !== source.size || actual !== expected) {
    await fs.unlink(target.absolute).catch(() => {});
    throw failure('Workspace upload verification failed; the incomplete object was removed.', 503);
  }
  return { path: target.normalized, size_bytes: stat.size, sha256: actual, updated_at: stat.mtime.toISOString() };
}
async function workspaceGet(key, relative) {
  const info = await workspaceInfo(key);
  if (!info.mounted) throw failure('This deployment has no mounted workspace.', 503);
  const target = workspacePath(relative);
  const stat = await fs.stat(target.absolute).catch((error) => { if (error.code === 'ENOENT') throw failure('Workspace file not found.', 404); throw error; });
  if (!stat.isFile()) throw failure('Workspace path is not a file.');
  return { ...target, size_bytes: stat.size };
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
  const request = await read(path.join(dir, 'request.json')).catch(() => ({}));
  return { id, status: receipt.status, created_at: receipt.created_at, finished_at: receipt.finished_at,
    error: receipt.error, files: available, model: REPORT_MODEL,
    input_provenance: { kind: request.kind, sha256: request.input_sha256,
      size_bytes: request.input_size_bytes, workspace_file: request.source_workspace },
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
  const inputDigest = input.local_path ? await fileHash(input.local_path) : hash(input.bytes);
  const signature = hash(JSON.stringify([inputDigest, input.kind, input.language]));
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
  if (await fileHash(path.join(dir, source)) !== inputDigest) throw failure('Transcript changed during input capture; no report was started.', 409);
  await fs.chmod(path.join(dir, source), 0o600);
  await save(path.join(dir, 'request.json'), { source, kind: input.kind, language: input.language,
    signature, key_hash: hash(key), created_at: new Date().toISOString(), platform: PLATFORM,
    input_sha256: inputDigest, input_size_bytes: size, source_workspace: input.source_workspace,
    report_model: REPORT_MODEL, report_provider: REPORT_PROVIDER });
  await save(path.join(dir, 'status.json'), { id, status: 'prepared', created_at: new Date().toISOString() });
  return start(owner, key, id);
}
async function clinicalFromWorkspace(owner, key, relativePath, language, idempotencyKey) {
  const file = await workspaceGet(key, relativePath);
  if (!['.txt', '.json'].includes(path.extname(file.normalized).toLowerCase())) {
    throw failure('Choose an existing transcript .txt or ASR .json workspace file.');
  }
  return clinical(owner, key, { kind: 'transcript', language, idempotency_key: idempotencyKey,
    filename: path.basename(file.normalized), local_path: file.absolute,
    source_workspace: file.normalized });
}
async function output(owner, id, filename) {
  if (!FILES.includes(filename)) throw failure('Unknown report file', 404);
  try { return await fs.readFile(path.join(directory(owner, id), 'output', filename)); }
  catch (error) { if (error.code === 'ENOENT') throw failure('This report file has not been produced. Check job status.', 409); throw error; }
}
async function clinicalOutput(owner, key, id, filename) {
  const bytes = await output(owner, id, filename);
  const workspace_file = await retainWorkspaceBytes(key,
    `.scientific-clinical/${id}/${hash(bytes)}/${filename}`, bytes);
  return { bytes, workspace_file };
}
async function analyzeWorkspace(kind, key, args) {
  return require('./analysis.cjs').compare(kind, key, args, { workspaceGet, retainWorkspaceBytes });
}
module.exports = { platform, listApps, operationResult, workshopRun, summarizeResult, clinical, clinicalFromWorkspace, status, list, start, output, clinicalOutput, analyzeWorkspace, track, waitOperation, runs, workspaceInfo, workspaceList,
  workspacePut, workspaceGet, save, read, failure, publicError, FILES, REPORT_MODEL };
