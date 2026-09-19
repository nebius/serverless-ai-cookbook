/* Run inside the exact image with --network none and a disposable /workspace.
 * node installed_stdio_gate.cjs RECEIPT [CANDIDATE_RENDERER]
 * The optional source renderer is explicitly a pre-build source gate, never an
 * installed-image claim. Runtime helpers/SDK/interpreter are never replaced.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { createRequire } = require('node:module');
const { spawn, spawnSync } = require('node:child_process');
const installedRequire = createRequire('/app/package.json');
const { Client } = installedRequire('@modelcontextprotocol/sdk/client/index.js');
const { StdioClientTransport, getDefaultEnvironment } = installedRequire('@modelcontextprotocol/sdk/client/stdio.js');
const { processMCPEnv } = installedRequire('@librechat/api');

const receiptPath = process.argv[2];
assert(receiptPath, 'Supply a private receipt path.');
const renderer = process.argv[3] || '/opt/hcls-librechat/render-config.mjs';
const python = '/opt/scientific-client/bin/python';
const ownerKeys = ['SCIENTIFIC_STUDY_OWNER_MODE', 'SCIENTIFIC_STUDY_OWNER', 'SEED_DEFAULT_USER_EMAIL'];
const providerKeys = ['NEBIUS_API_KEY', 'CLINICAL_REPORT_API_KEY', 'CLINICAL_REPORT_API_KEY_FILE'];
for (const key of Object.keys(process.env)) {
  if (/^(SCIENTIFIC_|SEED_|CLINICAL_|NEBIUS_)/.test(key)) delete process.env[key];
}
Object.assign(process.env, {
  SCIENTIFIC_DISCOVER_CHAT_MODELS: 'false', SCIENTIFIC_WORKSPACE: '/workspace',
  SCIENTIFIC_MODELS_API_KEY: 'synthetic-offline-platform-key',
  SCIENTIFIC_MODELS_MCP_URL: 'https://offline.invalid/mcp',
  SCIENTIFIC_MODELS_API_BASE_URL: 'https://offline.invalid',
});
const root = fs.mkdtempSync('/workspace/stdio-gate-');
const observations = [];
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
function parentPython(code) {
  const result = spawnSync(python, ['-c', code], {cwd: '/opt/bionemo', env: process.env, encoding: 'utf8'});
  assert.equal(result.status, 0, 'Parent study/API observer failed.');
  return JSON.parse(result.stdout);
}
function configure(values) {
  for (const key of [...ownerKeys, ...providerKeys]) delete process.env[key];
  Object.assign(process.env, values);
  const configPath = path.join(root, 'rendered.json');
  const result = spawnSync('node', [renderer, configPath], {env: process.env, encoding: 'utf8'});
  assert.equal(result.status, 0, 'Config render failed.');
  const raw = fs.readFileSync(configPath, 'utf8');
  for (const key of [...ownerKeys, ...providerKeys, 'SCIENTIFIC_MODELS_API_KEY']) {
    if (process.env[key]) assert(!raw.includes(JSON.stringify(process.env[key])), 'Config contains a literal binding value.');
  }
  const config = JSON.parse(raw).mcpServers['environment-execution'];
  assert.equal(config.command, python);
  assert.deepEqual(config.args, ['/opt/bionemo/execution-mcp.py']);
  // Actual installed LibreChat substitution, not a test reimplementation.
  return processMCPEnv({options: config, user: {id: 'transient-request-user'}});
}
async function connect(options) {
  const transport = new StdioClientTransport({...options, stderr: 'pipe'});
  transport.stderr.on('data', () => {}); // Never publish environment/provider output.
  const client = new Client({name: 'installed-stdio-qualification', version: '1'}, {capabilities: {}});
  await client.connect(transport);
  const tools = await client.listTools();
  assert(tools.tools.some(tool => tool.name === 'run_scientific_workflow'));
  return client;
}
function unpack(response) {
  assert.equal(response.isError, false, 'Offline MCP tool error: ' + response.content?.[0]?.text?.slice(0, 700));
  return JSON.parse(response.content[0].text);
}
const plan = {schema: 'scientific-workflow/v2', title: 'Offline rendered-stdio study',
  steps: [{id: 'prepare', kind: 'preparation', method: 'write-json',
    arguments: {filename: 'measurement.json', value: {count: 6, unit: 'items'}}},
    {id: 'report', kind: 'analysis', method: 'report', arguments: {title: 'Offline measurements',
      sections: [{title: 'Measured values', format: 'markdown', file: {step: 'prepare', file: 'measurement.json'}}]}}],
  deliverables: [{name: 'measurement.json', role: 'data', source: {step: 'prepare', file: 'measurement.json'}},
    {name: 'report.md', role: 'report', source: {step: 'report', file: 'report.md'}},
    {name: 'provenance.json', role: 'provenance', source: {step: 'report', file: 'provenance.json'}}]};
async function runCase(label, values, expectedError) {
  const options = configure(values);
  assert(!('SCIENTIFIC_STUDY_OWNER_MODE' in getDefaultEnvironment()));
  const client = await connect(options);
  const args = {study: plan, output_directory: path.join(root, label)};
  try {
    const raw = await client.callTool({name: 'run_scientific_workflow', arguments: args});
    if (expectedError) {
      assert.equal(raw.isError, true);
      assert.match(raw.content[0].text, expectedError);
      observations.push({case: label, rejected: true});
      return;
    }
    const accepted = unpack(raw);
    assert.equal(accepted.state, 'queued');
    const repeated = unpack(await client.callTool({name: 'run_scientific_workflow', arguments: args}));
    assert.equal(repeated.id, accepted.id);
    const before = parentPython('import json, scientific_study as s; print(json.dumps({"owner":s.owner_identity(),"items":s.list_studies()}))');
    assert(before.items.some(item => item.id === accepted.id));
    assert.equal(fs.existsSync(path.join('/workspace/.scientific-studies', before.owner, accepted.id, 'receipt.json')), true);
    await client.close(); // No client remains while the independent worker runs.
    const worker = spawn(python, ['/opt/bionemo/scientific-study-worker.py', '--', '/bin/sleep', '40'],
      {cwd: '/opt/bionemo', env: process.env, stdio: ['ignore', 'ignore', 'ignore']});
    let final;
    try {
      const deadline = Date.now() + 20000;
      while (Date.now() < deadline) {
        final = parentPython(`import json, scientific_study as s; print(json.dumps(s.get(${JSON.stringify(accepted.id)})))`);
        if (final.state === 'completed') break;
        assert(!['failed', 'needs_attention'].includes(final.state), 'Independent worker failed.');
        await pause(150);
      }
      assert.equal(final.state, 'completed');
      const engine = parentPython('import json, scientific_study as s; print(json.dumps(s.engine_status()))');
      assert.equal(engine.alive, true);
      const health = JSON.parse(fs.readFileSync('/data/hcls-execution/study-worker.json'));
      assert.equal(health.owner_namespace, before.owner);
    } finally {
      worker.kill('SIGTERM');
      await new Promise(resolve => worker.once('exit', resolve));
    }
    const reconnected = await connect(options);
    try {
      const reread = unpack(await reconnected.callTool({name: 'read_execution', arguments: {job_id: accepted.id, wait_seconds: 0}}));
      assert.equal(reread.state, 'completed');
      assert.equal(unpack(await reconnected.callTool({name: 'run_scientific_workflow', arguments: args})).id, accepted.id);
      for (const artifact of [...reread.artifacts, reread.manifest]) {
        const bytes = fs.readFileSync(artifact.path);
        assert(bytes.length > 0);
        assert.equal(digest(bytes), artifact.sha256);
      }
      observations.push({case: label, state: reread.state, owner_namespace: before.owner,
        study_id: accepted.id, artifact_count: reread.artifacts.length, idempotent: true,
        disconnected_worker_completion: true, reconnected_read_verified: true});
    } finally { await reconnected.close(); }
  } finally { await client.close(); }
}
async function clinicalCase(label, providerName) {
  const values = {SCIENTIFIC_STUDY_OWNER_MODE: 'first-instance', SEED_DEFAULT_USER_EMAIL: `${label}@example.test`};
  if (providerName) values[providerName] = providerName.endsWith('_FILE') ? path.join(root, 'provider-key') : 'synthetic-offline-provider-key';
  const options = configure(values);
  const client = await connect(options);
  const transcript = path.join(root, 'transcript.txt');
  fs.writeFileSync(transcript, 'This is an offline configuration test, not a patient report.');
  fs.writeFileSync(path.join(root, 'provider-key'), 'synthetic-offline-provider-key');
  const clinical = {schema: 'scientific-workflow/v2', title: 'Clinical preflight only',
    steps: [{id: 'draft', kind: 'clinical', source: transcript, source_type: 'transcript', language: 'en',
      report_model: 'Qwen/Qwen3-235B-A22B-Instruct-2507'}],
    deliverables: [{name: 'report.md', role: 'report', source: {step: 'draft', file: 'report.md'}}]};
  try {
    const raw = await client.callTool({name: 'run_scientific_workflow', arguments: {study: clinical, output_directory: path.join(root, label)}});
    if (providerName) {
      const accepted = unpack(raw);
      assert.equal(accepted.state, 'queued');
      const parent = parentPython(`import json, scientific_study as s; print(json.dumps(s.get(${JSON.stringify(accepted.id)})))`);
      assert.equal(parent.state, 'queued');
      assert.deepEqual(parent.completed_steps, []);
      // No supervisor starts for these namespaces: zero provider calls.
      observations.push({case: label, state: 'queued', provider_binding: providerName, worker_started: false});
    } else {
      assert.equal(raw.isError, true);
      assert.match(raw.content[0].text, /clinical provider credential/);
      observations.push({case: label, rejected: true});
    }
  } finally { await client.close(); }
}
async function omittedBindingRegression() {
  const options = configure({SCIENTIFIC_STUDY_OWNER_MODE: 'first-instance', SEED_DEFAULT_USER_EMAIL: 'first@example.test'});
  // Reproduce the former rendered env omission while the parent remains
  // fully configured. SDK defaults must not accidentally make this pass.
  for (const key of ownerKeys) delete options.env[key];
  const client = await connect(options);
  try {
    const raw = await client.callTool({name: 'run_scientific_workflow', arguments: {
      study: plan, output_directory: path.join(root, 'old-omitted-binding')}});
    assert.equal(raw.isError, true);
    assert.match(raw.content[0].text, /stop-first deployment preflight/);
    observations.push({case: 'old-omitted-binding', parent_configured: true, rejected: true});
  } finally { await client.close(); }
}
async function main() {
  await omittedBindingRegression();
  await runCase('email-first', {SCIENTIFIC_STUDY_OWNER_MODE: 'first-instance', SEED_DEFAULT_USER_EMAIL: 'first@example.test'});
  await runCase('explicit-stopped', {SCIENTIFIC_STUDY_OWNER_MODE: 'stopped-predecessor', SCIENTIFIC_STUDY_OWNER: 'stable-explicit-owner', SEED_DEFAULT_USER_EMAIL: 'ignored@example.test'});
  await runCase('missing-mode', {SEED_DEFAULT_USER_EMAIL: 'first@example.test'}, /stop-first deployment preflight/);
  await runCase('invalid-mode', {SCIENTIFIC_STUDY_OWNER_MODE: 'invalid-mode', SEED_DEFAULT_USER_EMAIL: 'first@example.test'}, /stop-first deployment preflight/);
  await runCase('missing-owner', {SCIENTIFIC_STUDY_OWNER_MODE: 'first-instance'}, /dedicated-user identity/);
  await clinicalCase('clinical-missing', null);
  for (const name of providerKeys) await clinicalCase(`clinical-${name.toLowerCase()}`, name);
  for (const filename of fs.readdirSync('/workspace/.scientific-studies', {recursive: true})) {
    const absolute = path.join('/workspace/.scientific-studies', filename);
    if (fs.statSync(absolute).isFile()) {
      const bytes = fs.readFileSync(absolute, 'utf8');
      assert(!bytes.includes('synthetic-offline-platform-key'));
      assert(!bytes.includes('synthetic-offline-provider-key'));
    }
  }
  const receipt = {schema: 'rendered-stdio-acceptance/v1', passed: true,
    installed_renderer: process.argv[3] === undefined, renderer_sha256: digest(fs.readFileSync(renderer)),
    process_mcp_env: 'installed @librechat/api', transport: 'installed SDK StdioClientTransport',
    inherited_default_keys: Object.keys(getDefaultEnvironment()), interpreter: python,
    network_required: false, model_calls: 0, observations};
  fs.mkdirSync(path.dirname(receiptPath), {recursive: true});
  fs.writeFileSync(receiptPath, JSON.stringify(receipt, null, 2) + '\n');
  console.log(JSON.stringify({passed: true, case_count: observations.length, installed_renderer: receipt.installed_renderer}));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
