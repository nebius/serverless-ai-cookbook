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
  assert.equal(messages[1].result.tools.length, 16);
  assert.ok(messages[1].result.tools.every((tool) => tool.inputSchema.additionalProperties === false));
  assert.ok(messages[1].result.tools.some((tool) => tool.name === 'workbench_track_operation'));
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
after(async () => { await setup; await fs.rm(root, { recursive: true }); });
