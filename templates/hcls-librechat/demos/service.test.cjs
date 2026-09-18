const { test, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const crypto = require('node:crypto');
let root;
const setup = (async () => {
  root = await fs.mkdtemp(path.join(os.tmpdir(), 'clinical-demos-test-'));
  process.env.SCIENTIFIC_DEMOS_DIR = root;
  process.env.NEBIUS_API_KEY = 'fixture-provider-not-real';
  process.env.SCIENTIFIC_CLINICAL_PYTHON = process.execPath;
  process.env.SCIENTIFIC_CLINICAL_SCRIPT = path.join(__dirname, 'worker-fixture.cjs');
  process.env.SCIENTIFIC_WORKSPACE = path.join(root, 'workspace');
  process.env.TEAM_ID = 'fixture-team';
  process.env.TEAM_BUCKET_NAME = 'fixture-bucket';
  await fs.mkdir(process.env.SCIENTIFIC_WORKSPACE);
  return require('./service.cjs');
})();
const input = (id) => ({ filename: 'consultation.txt', bytes: Buffer.from('Synthetic consultation only.'),
  kind: 'transcript', language: 'de', idempotency_key: id });
async function complete(service, id) {
  for (let n = 0; n < 240; n++) {
    const value = await service.status('user-a', id);
    if (!['running', 'queued'].includes(value.status)) return value;
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  throw new Error('Fixture worker did not complete');
}
test('valid clinical submission survives request return and replays exactly once', async () => {
  const service = await setup;
  const job = await service.clinical('user-a', 'test-platform-key', input('fixture-1'));
  const done = await complete(service, job.id);
  assert.equal(done.status, 'completed');
  assert.ok(done.files.includes('report.md'));
  const again = await service.clinical('user-a', 'test-platform-key', input('fixture-1'));
  assert.equal(again.id, job.id);
  assert.equal(again.status, 'completed');
  assert.equal((await service.output('user-a', job.id, 'report.md')).toString(), 'Fixture draft, not medical evidence.');
  assert.equal((await service.list('user-a')).length, 1);
  await assert.rejects(service.status('user-b', job.id), /not found/);
  await assert.rejects(service.output('user-a', job.id, 'request.json'), /Unknown report/);
  await assert.rejects(service.output('user-a', '../other', 'report.md'), /Invalid job/);
  await assert.rejects(service.start('user-a', 'different-key', job.id), /original submitting/);
  await assert.rejects(service.clinical('user-a', 'test-platform-key', { ...input('fixture-1'), language: 'en' }), /different input/);
});
test('invalid inputs and missing credentials fail before admitting any work', async () => {
  const service = await setup;
  for (const patch of [{ language: 'fr' }, { bytes: Buffer.alloc(0) }, { filename: 'data.exe' }, { idempotency_key: '../bad' }, { kind: 'other' }]) {
    await assert.rejects(service.clinical('user-c', 'test-key', { ...input('bad'), ...patch }));
  }
  await assert.rejects(service.clinical('user-c', '', input('bad')), /Configure/);
  assert.deepEqual(await service.list('user-c'), []);
  await assert.rejects(service.platform('key', 'GET', '/unrelated'), /Unsupported/);
  await assert.rejects(service.platform('key', 'DELETE', '/v1/workshop/runs'), /Unsupported/);
});
test('receipt files do not contain either platform or provider key', async () => {
  const service = await setup;
  const job = await service.clinical('user-a', 'test-platform-key', input('fixture-2'));
  await complete(service, job.id);
  const folder = path.join(root, crypto.createHash('sha256').update('user-a').digest('hex'), job.id);
  for (const name of ['request.json', 'status.json', 'worker.log']) {
    const text = await fs.readFile(path.join(folder, name), 'utf8');
    assert.ok(!text.includes('test-platform-key'));
    assert.ok(!text.includes('fixture-provider-not-real'));
  }
});
test('same-key jobs serialize and a timeout resumes cached work once', async () => {
  const service = await setup;
  const a = await service.clinical('user-a', 'queue-key', input('queued-a'));
  const b = await service.clinical('user-a', 'queue-key', input('queued-b'));
  await Promise.all([complete(service, a.id), complete(service, b.id)]);
  const receipt = async (id) => JSON.parse(await fs.readFile(path.join(root,
    crypto.createHash('sha256').update('user-a').digest('hex'), id, 'output/fixture.json')));
  const [first, second] = (await Promise.all([receipt(a.id), receipt(b.id)])).sort((a, b) => a.start - b.start);
  assert.ok(second.start >= first.finish);
  const retried = await service.clinical('user-a', 'queue-key', { ...input('timeout-a'), bytes: Buffer.from('fixture:timeout') });
  assert.equal((await complete(service, retried.id)).status, 'completed');
  assert.equal((await receipt(retried.id)).attempt, 2);
});
test('stdio MCP exposes typed tools and rejects absent identity without inference', async () => {
  await setup;
  const child = spawn(process.execPath, [path.join(__dirname, 'mcp.cjs')], { env: { ...process.env, LIBRECHAT_USER_ID: '' } });
  let stdout = '';
  child.stdout.on('data', (data) => stdout += data);
  child.stdin.end([ { id: 1, method: 'initialize' }, { id: 2, method: 'tools/list' },
    { id: 3, method: 'tools/call', params: { name: 'clinical_list_jobs' } } ].map((item) => JSON.stringify({ jsonrpc: '2.0', ...item })).join('\n') + '\n');
  assert.equal(await new Promise((resolve) => child.on('exit', resolve)), 0);
  const messages = stdout.trim().split('\n').map(JSON.parse);
  assert.equal(messages[1].result.tools.length, 20);
  assert.ok(messages[1].result.tools.every((tool) => tool.inputSchema.additionalProperties === false));
  assert.ok(messages[1].result.tools.some((tool) => tool.name === 'workbench_track_operation'));
  assert.ok(messages[1].result.tools.some((tool) => tool.name === 'clinical_report_from_workspace'));
  assert.ok(messages[1].result.tools.some((tool) => tool.name === 'workbench_compare_docking'));
  assert.ok(messages[1].result.tools.some((tool) => tool.name === 'workbench_compare_structures'));
  assert.equal(messages[2].result.isError, true);
});
test('mounted workspace stays inside its root and round-trips files', async () => {
  const service = await setup;
  const source = path.join(root, 'source.txt');
  await fs.writeFile(source, 'workspace fixture');
  const receipt = await service.workspacePut('fixture-key', 'papers/result.txt', source);
  assert.equal(receipt.path, 'papers/result.txt');
  assert.match(receipt.sha256, /^[a-f0-9]{64}$/);
  await assert.rejects(service.workspacePut('fixture-key', 'papers/result.txt', source), /already exists/);
  const listing = await service.workspaceList('fixture-key', 'papers');
  assert.equal(listing.info.team_bucket_name, 'fixture-bucket');
  assert.deepEqual(listing.data.map((item) => item.name), ['result.txt']);
  const downloaded = await service.workspaceGet('fixture-key', 'papers/result.txt');
  assert.equal(await fs.readFile(downloaded.absolute, 'utf8'), 'workspace fixture');
  await assert.rejects(service.workspaceGet('fixture-key', '../request.json'), /escape/);
});
test('artifact-backed operation results are verified and compacted for the agent', async () => {
  const service = await setup;
  const operationId = '11111111-1111-4111-8111-111111111111';
  const artifactId = '22222222-2222-4222-8222-222222222222';
  const payload = Buffer.from(JSON.stringify({ confidence: 72.5, plddt: [70, 80, 90],
    predicted_aligned_error: [[0.25, 1.5], [2.5, 0.25]], structure: 'ATOM '.repeat(1000) }));
  const artifact = { artifact_id: artifactId, compression: 'none', media_type: 'application/octet-stream',
    size_bytes: payload.length, sha256: crypto.createHash('sha256').update(payload).digest('hex') };
  const originalFetch = global.fetch;
  const calls = [];
  global.fetch = async (url) => {
    calls.push(String(url));
    if (String(url).endsWith(`/v1/operations/${operationId}`)) return new Response(JSON.stringify({
      id: operationId, status: 'succeeded', model_id: 'openfold2', operation: 'infer_openfold2',
    }), { status: 200, headers: { 'content-type': 'application/json' } });
    if (String(url).endsWith(`/v1/operations/${operationId}/result`)) return new Response(JSON.stringify({
      schema: 'fs2-serve.nebius.ai/operation-artifact-result/v1', content_type: 'application/json', artifact,
    }), { status: 200, headers: { 'content-type': 'application/json' } });
    if (String(url).endsWith(`/v1/artifacts/${artifactId}/content`)) return new Response(payload, { status: 200 });
    return new Response('{}', { status: 404 });
  };
  try {
    const resolved = await service.operationResult('fixture-key', operationId);
    assert.equal(resolved.result.schema, 'fs2-serve.nebius.ai/resolved-operation-result/v1');
    assert.equal(resolved.result.summary.confidence, 72.5);
    assert.deepEqual(resolved.result.summary.plddt, { type: 'numeric-array', count: 3,
      finite_count: 3, min: 70, max: 90, mean: 80 });
    assert.deepEqual(resolved.result.summary.predicted_aligned_error.shape, [2, 2]);
    assert.equal(resolved.result.summary.structure.type, 'long-string');
    assert.match(resolved.result.evidence_guidance.observations[0], /verified/);
    assert.ok(resolved.result.evidence_guidance.interpretation_boundaries.some((item) => item.includes('absent')));
    assert.ok(resolved.result.evidence_guidance.interpretation_boundaries.some((item) => item.includes('result JSON artifact size')));
    assert.equal(calls.length, 3);
    assert.equal(resolved.workspace_file.saved, true);
    assert.deepEqual(await fs.readFile(resolved.workspace_file.path), payload);
    assert.equal((await service.operationResult('fixture-key', operationId)).workspace_file.sha256, artifact.sha256);
  } finally { global.fetch = originalFetch; }
});
test('compact discovery filters Apps and does not emit scientific input schemas', async () => {
  const service = await setup;
  const originalFetch = global.fetch;
  global.fetch = async (url) => new Response(JSON.stringify({ data: String(url).endsWith('/v1/models')
    ? [{ id: 'openfold2', protocols: ['native'], input_schema: { huge: 'x'.repeat(50000) } }]
    : [{ model_id: 'protenix-v2', display_name: 'Protenix', operations: ['predict'],
      parameters_schema: { huge: 'x'.repeat(50000) }, mcp_tool_description: 'Protein complex prediction' }] }));
  try {
    const all = await service.listApps('fixture-key');
    assert.equal(all.count, 2);
    assert.ok(JSON.stringify(all).length < 1000);
    assert.deepEqual((await service.listApps('fixture-key', 'complex')).data.map((app) => app.model_id), ['protenix-v2']);
    assert.equal((await service.listApps('fixture-key', 'missing')).count, 0);
  } finally { global.fetch = originalFetch; }
});
test('inline output is compacted, saved losslessly and never overwrites different evidence', async () => {
  const service = await setup;
  const id = crypto.randomUUID();
  const result = { structures: [{ pdb: 'ATOM '.repeat(5000), confidence: 0.75 }] };
  const originalFetch = global.fetch;
  global.fetch = async (url) => new Response(JSON.stringify(String(url).endsWith('/result')
    ? result : { id, status: 'succeeded' }));
  try {
    const output = await service.operationResult('fixture-key', id);
    assert.equal(output.result.structures[0].pdb.type, 'long-string');
    assert.deepEqual(JSON.parse(await fs.readFile(output.workspace_file.path, 'utf8')), result);
    result.structures[0].confidence = 0.9;
    await assert.rejects(service.operationResult('fixture-key', id), /not overwritten/);
    assert.equal(JSON.parse(await fs.readFile(output.workspace_file.path, 'utf8')).structures[0].confidence, 0.75);
  } finally { global.fetch = originalFetch; }
});
test('parallel operation tracking cannot overwrite another run or mix changed keys', async () => {
  const service = await setup;
  const ids = Array.from({ length: 30 }, () => crypto.randomUUID());
  const originalFetch = global.fetch;
  global.fetch = async (url) => {
    if (String(url).includes('/v1/operations?')) return new Response('{}', { status: 404 });
    await new Promise((resolve) => setTimeout(resolve, 5));
    const id = String(url).split('/').pop();
    return new Response(JSON.stringify({ id, status: 'succeeded', model_id: 'test-app',
      accepted_at: '2026-09-18T18:00:00Z', completed_at: '2026-09-18T18:01:00Z' }));
  };
  try {
    await Promise.all(ids.map((id) => service.track('parallel-scientist', 'one-key', id)));
    const records = await service.runs('parallel-scientist', 'one-key');
    assert.deepEqual(new Set(records.data.map((row) => row.id)), new Set(ids));
    assert.equal(records.history_available, false);
    assert.deepEqual((await service.runs('parallel-scientist', 'another-key')).data, []);
  } finally { global.fetch = originalFetch; }
});
test('caller history discovers untracked operations and follows the platform page cursor', async () => {
  const service = await setup;
  const id = crypto.randomUUID();
  const originalFetch = global.fetch;
  const requests = [];
  global.fetch = async (url, options) => {
    requests.push({ url: String(url), authorization: options.headers.Authorization });
    return new Response(JSON.stringify({ data: [{ id, model_id: 'mosaic', status: 'queued',
      protocol: 'scientific-batch-v1', accepted_at: '2026-09-18T18:00:00Z' }], next_cursor: 'next_page' }));
  };
  try {
    const page = await service.runs('new-scientist', 'caller-key', { limit: 25, cursor: 'previous_page' });
    assert.equal(page.data[0].id, id);
    assert.equal(page.data[0].accepted_at, '2026-09-18T18:00:00Z');
    assert.equal(page.history_available, true);
    assert.equal(page.next_cursor, 'next_page');
    assert.equal(requests.length, 1);
    assert.ok(requests[0].url.endsWith('/v1/operations?limit=25&cursor=previous_page'));
    assert.equal(requests[0].authorization, 'Bearer caller-key');
    await assert.rejects(service.runs('new-scientist', 'caller-key', { cursor: '../bad' }), /Invalid/);
  } finally { global.fetch = originalFetch; }
});
test('bounded operation wait preserves terminal and intermediate status without submission', async () => {
  const service = await setup;
  const id = crypto.randomUUID();
  const originalFetch = global.fetch;
  const calls = [];
  let state = 'queued';
  global.fetch = async (url, options) => {
    calls.push(options.method);
    return new Response(JSON.stringify({ id, status: state, model_id: 'test' }));
  };
  try {
    const pending = await service.waitOperation('waiting-user', 'fixture-key', id, 0);
    assert.equal(pending.terminal, false);
    assert.equal(pending.observations[0].status, 'queued');
    state = 'preempted';
    const done = await service.waitOperation('waiting-user', 'fixture-key', id, 15);
    assert.equal(done.terminal, true);
    assert.equal(done.status, 'preempted');
    assert.deepEqual(calls, ['GET', 'GET']);
    await assert.rejects(service.waitOperation('waiting-user', 'fixture-key', id, 31), /between 0 and 30/);
  } finally { global.fetch = originalFetch; }
});
test('admission errors retain retry and accepted-work facts for the panel and agent', async () => {
  const service = await setup;
  const originalFetch = global.fetch;
  global.fetch = async () => new Response(JSON.stringify({ error: { code: 'admission_limit_reached',
    message: 'Your current run is still active.', retryable: true, durable_admission: false } }),
  { status: 429, headers: { 'retry-after': '12' } });
  try {
    await assert.rejects(service.platform('caller-key', 'POST', '/v1/workshop/runs', {}), (error) => {
      assert.deepEqual(service.publicError(error), { error: 'Your current run is still active.',
        code: 'admission_limit_reached', retryable: true, durable_admission: false, retry_after_seconds: 12 });
      return true;
    });
  } finally { global.fetch = originalFetch; }
});
test('consultation export preserves every turn and immutable versions without model submissions', async () => {
  const service = await setup;
  const id = crypto.randomUUID();
  const originalFetch = global.fetch;
  const run = { id, status: 'running', state: { transcript: Array.from({ length: 21 }, (_, i) => ({
    role: i % 2 ? 'patient' : 'clinician', content: `Exact turn ${i}: ` + 'long synthetic text '.repeat(500),
  })), judgment: null } };
  const calls = [];
  global.fetch = async (url, options) => {
    calls.push({ method: options.method, url });
    return new Response(JSON.stringify(run));
  };
  try {
    const first = await service.workshopRun('caller-key', id);
    const bytes = await fs.readFile(first.workspace_file.path);
    assert.equal(first.workspace_file.sha256, crypto.createHash('sha256').update(bytes).digest('hex'));
    assert.deepEqual(JSON.parse(bytes), run);
    assert.equal((await service.workshopRun('caller-key', id)).workspace_file.path, first.workspace_file.path);
    run.status = 'completed';
    run.state.judgment = { overall_score: 4.25, judgment: { evidence: 'final real field' } };
    const final = await service.workshopRun('caller-key', id);
    assert.notEqual(final.workspace_file.path, first.workspace_file.path);
    assert.equal(JSON.parse(await fs.readFile(first.workspace_file.path)).status, 'running');
    assert.deepEqual(JSON.parse(await fs.readFile(final.workspace_file.path)), run);
    assert.ok(calls.every((call) => call.method === 'GET' && call.url.endsWith(`/v1/workshop/runs/${id}`)));
    process.env.LIBRECHAT_USER_ID = 'export-fixture-user';
    process.env.SCIENTIFIC_MODELS_API_KEY = 'caller-key';
    const mcp = require('./mcp.cjs');
    const toolResult = await mcp.dispatch('workshop_get_run', { run_id: id });
    assert.equal(toolResult.transcript.messages, 21);
    assert.equal(toolResult.workspace_file.sha256, final.workspace_file.sha256);
    assert.ok(JSON.stringify(toolResult).length < 5000);
    assert.equal(JSON.stringify(toolResult).includes('long synthetic text'), false);
  } finally { global.fetch = originalFetch; }
});
test('clinical output retains exact files and versions without exposing private job paths', async () => {
  const service = await setup;
  const owner = 'export-fixture-user';
  const id = crypto.randomUUID().replaceAll('-', '');
  const source = path.join(root, crypto.createHash('sha256').update(owner).digest('hex'), id, 'output');
  await fs.mkdir(source, { recursive: true });
  const original = Buffer.from('Synthetic report with exact evidence.\n');
  await fs.writeFile(path.join(source, 'report.md'), original);
  const retained = await service.clinicalOutput(owner, 'caller-key', id, 'report.md');
  assert.deepEqual(await fs.readFile(retained.workspace_file.path), original);
  assert.equal(retained.workspace_file.sha256, crypto.createHash('sha256').update(original).digest('hex'));
  assert.ok(retained.workspace_file.path.startsWith(process.env.SCIENTIFIC_WORKSPACE));
  assert.equal((await service.clinicalOutput(owner, 'caller-key', id, 'report.md')).workspace_file.path, retained.workspace_file.path);
  const updated = Buffer.from('Explicitly revised synthetic report.\n');
  await fs.writeFile(path.join(source, 'report.md'), updated);
  const revised = await service.clinicalOutput(owner, 'caller-key', id, 'report.md');
  assert.notEqual(revised.workspace_file.path, retained.workspace_file.path);
  assert.deepEqual(await fs.readFile(retained.workspace_file.path), original);
  await assert.rejects(service.clinicalOutput('another-user', 'caller-key', id, 'report.md'), /not been produced/);
  await assert.rejects(service.clinicalOutput(owner, 'caller-key', id, 'request.json'), /Unknown report/);
  process.env.LIBRECHAT_USER_ID = owner;
  process.env.SCIENTIFIC_MODELS_API_KEY = 'caller-key';
  const mcp = require('./mcp.cjs');
  const value = await mcp.dispatch('clinical_read_output', { job_id: id, filename: 'report.md' });
  assert.equal(value.content, updated.toString());
  assert.equal(value.workspace_file.sha256, revised.workspace_file.sha256);
  const large = Buffer.from('Synthetic transcript.\n'.repeat(6000));
  await fs.writeFile(path.join(source, 'transcript.txt'), large);
  const bounded = await mcp.dispatch('clinical_read_output', { job_id: id, filename: 'transcript.txt' });
  assert.equal(bounded.content, undefined);
  assert.equal(bounded.requires_download, true);
  assert.deepEqual(await fs.readFile(bounded.workspace_file.path), large);
  assert.ok(JSON.stringify(bounded).length < 2000);
});
test('workspace clinical input captures full bytes and exposes immutable source lineage', async () => {
  const service = await setup;
  const relative = 'full-source/asr-result.json';
  const file = path.join(process.env.SCIENTIFIC_WORKSPACE, relative);
  await fs.mkdir(path.dirname(file), { recursive: true });
  const bytes = Buffer.from(JSON.stringify({ text: 'Complete synthetic source with a final sentinel. '.repeat(5000),
    duration_seconds: 457.92, source: 'test-fixture' }));
  await fs.writeFile(file, bytes);
  const job = await service.clinicalFromWorkspace('user-a', 'test-platform-key', relative, 'en', 'full-workspace-fixture');
  await complete(service, job.id);
  const done = await service.status('user-a', job.id);
  assert.deepEqual(done.input_provenance, { kind: 'transcript',
    sha256: crypto.createHash('sha256').update(bytes).digest('hex'),
    size_bytes: bytes.length, workspace_file: relative });
  const captured = path.join(root, crypto.createHash('sha256').update('user-a').digest('hex'), job.id, 'input.json');
  assert.deepEqual(await fs.readFile(captured), bytes);
  assert.equal((await service.clinicalFromWorkspace('user-a', 'test-platform-key', relative, 'en', 'full-workspace-fixture')).id, job.id);
  await fs.writeFile(file, Buffer.from('{"text":"different input"}'));
  await assert.rejects(service.clinicalFromWorkspace('user-a', 'test-platform-key', relative, 'en', 'full-workspace-fixture'), /different input/);
  await assert.rejects(service.clinicalFromWorkspace('user-a', 'test-platform-key', '../outside.txt', 'en', 'bad-path-fixture'), /path/);
});
after(async () => { await setup; await fs.rm(root, { recursive: true }); });
