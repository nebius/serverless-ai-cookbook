// Source mode uses the pinned installed factory region with only our candidate
// factory insertion. Installed mode reads the already-patched image verbatim.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const installed = process.env.SCIENTIFIC_VALIDATION_INSTALLED === '1';
const factoryPath = '/app/api/server/services/MCP.js';
const r = createRequire(factoryPath);
const helper = require(installed ? '/opt/hcls-librechat/scientific-workflow-validation.cjs'
  : path.join(__dirname, 'scientific-workflow-validation.cjs'));
const { tool, ToolInputParsingException } = r('@langchain/core/tools');
const { Client } = r('@modelcontextprotocol/sdk/client/index.js');
const { StdioClientTransport } = r('@modelcontextprotocol/sdk/client/stdio.js');
const originalFactory = fs.readFileSync(factoryPath, 'utf8');
const factorySource = installed ? originalFactory : helper.patchFactory(originalFactory);
assert.equal(factorySource.split(helper.CALL).length, 2);
const region = `${helper.ANCHOR}\n${helper.CALL}`;
assert.ok(factorySource.includes(region));
// Loading all of MCP.js starts unrelated application services. Execute its
// exact constructor/attachment region with the real pinned LangChain factory.
const construct = new Function('tool', '_call', 'schema', 'normalizedToolKey', 'description',
  'AgentConstants', 'require', 'serverName', 'serverToolName', `${region}\nreturn toolInstance;`);
function make(name, schema, handler, server = 'environment-execution') {
  return construct(tool, handler, schema, `${name}_mcp_${server}`, 'Workflow contract fixture',
    { CONTENT_AND_ARTIFACT: 'content_and_artifact' }, moduleName => {
      assert.equal(moduleName, '/opt/hcls-librechat/scientific-workflow-validation.cjs');
      return helper;
    }, server, name);
}
const client = new Client({ name: 'workflow-validation-boundary', version: '1' });
let schemas, lastSDKReply, calls = 0;
test.before(async () => {
  const root = process.env.SCIENTIFIC_VALIDATION_PYTHON_ROOT || '/opt/bionemo';
  await client.connect(new StdioClientTransport({ command: '/opt/scientific-client/bin/python',
    args: [path.join(root, 'execution-mcp.py')], env: { ...process.env, PYTHONPATH: root,
      SCIENTIFIC_WORKSPACE: '/workspace', SCIENTIFIC_MODELS_MCP_URL: 'https://platform.test/mcp',
      SCIENTIFIC_MODELS_API_KEY: 'cpu-fixture-only', SCIENTIFIC_STUDY_OWNER_MODE: 'first-instance',
      SEED_DEFAULT_USER_EMAIL: 'validation-boundary@example.test', PYTHONDONTWRITEBYTECODE: '1' } }));
  schemas = Object.fromEntries((await client.listTools()).tools.map(t => [t.name, t.inputSchema]));
});
test.after(async () => { await client.close(); });
function sdkTool(name, schema = schemas[name]) {
  return make(name, schema, async args => {
    calls++;
    lastSDKReply = await client.callTool({ name, arguments: args });
    return [JSON.stringify(lastSDKReply), null];
  });
}
function mpnn(overrides = {}) {
  return { id: 'design', kind: 'preparation', method: 'proteinmpnn-input', arguments: {
    backbone: '/workspace/backbone.pdb', structure_index: 0, chain: 'A', num_sequences: 2,
    seed: 1, sampling_temp: 0.1, omit_aas: [], ...overrides } };
}
async function rejected(instance, args, pattern) {
  const before = calls;
  const saved = JSON.stringify(args);
  await assert.rejects(() => instance.invoke(args), error => {
    assert.ok(error instanceof ToolInputParsingException);
    assert.match(error.message, pattern);
    assert.ok(error.message.length <= 1024);
    assert.doesNotMatch(error.message, /PRIVATE_SENTINEL|oneOf|keywordLocation/);
    return true;
  });
  assert.equal(calls, before, 'Rejected input must never reach the MCP handler');
  assert.equal(JSON.stringify(args), saved, 'Arguments must not be rewritten');
}

test('known historical required report title returns the exact field path before SDK dispatch', async () => {
  const historical = JSON.parse(fs.readFileSync(path.join(__dirname, 'test-fixtures/workflow-composer-v60-schema.json')));
  const instance = sdkTool('compose_scientific_workflow', historical);
  await rejected(instance, { draft_directory: '/workspace/missing-title', steps: [{ id: 'report',
    kind: 'analysis', method: 'report', arguments: { sections: [{ title: 'Measurements',
      file: '/workspace/data.csv', format: 'csv' }] } }] }, /\$\.steps\[0\]\.arguments\.title: required/);
});

test('all three retained missing-title calls get bounded diagnostics with zero SDK dispatch', async t => {
  if (!process.env.SCIENTIFIC_VALIDATION_RETAINED_MESSAGES) return t.skip('Retained trace not mounted');
  const saved = JSON.parse(fs.readFileSync(process.env.SCIENTIFIC_VALIDATION_RETAINED_MESSAGES));
  const failed = (saved.body ?? saved).flatMap(m => m.content ?? []).map(c => c.tool_call)
    .filter(c => c?.name === 'compose_scientific_workflow_mcp_environment-execution' && c.output.startsWith('Error:'));
  assert.equal(failed.length, 3);
  const historical = JSON.parse(fs.readFileSync(path.join(__dirname, 'test-fixtures/workflow-composer-v60-schema.json')));
  for (const call of failed) await rejected(sdkTool('compose_scientific_workflow', historical), JSON.parse(call.args),
    /\$\.steps\[(0|4)\]\.arguments\.title: required/);
});

test('composer num_sequences lower bound retains strict installed validation', async () => {
  await rejected(sdkTool('compose_scientific_workflow'), { draft_directory: '/workspace/invalid',
    steps: [mpnn({ num_sequences: 0 })] }, /\$\.steps\[0\]\.arguments\.num_sequences: must be >= 1/);
});

test('run inline study num_sequences type is reported without admitting a study', async () => {
  await rejected(sdkTool('run_scientific_workflow'), { output_directory: '/workspace/no-admission', study: {
    schema: 'scientific-workflow/v2', title: 'Typed fixture', steps: [mpnn({ num_sequences: 'PRIVATE_SENTINEL' })],
    deliverables: [{ name: 'report.md', role: 'report', source: { step: 'design', file: 'report.md' } }] } },
  /\$\.study\.steps\[0\]\.arguments\.num_sequences: must have type integer/);
  assert.equal(fs.existsSync('/workspace/no-admission'), false);
});

test('unknown method reports the discriminator rather than unrelated branch failures', async () => {
  await rejected(sdkTool('compose_scientific_workflow'), { draft_directory: '/workspace/invalid',
    steps: [{ ...mpnn(), method: 'PRIVATE_SENTINEL' }] }, /\$\.steps\[0\]\.method: must match a published workflow kind\/method/);
});

test('multiple scientific errors stay concise without echoing values or unknown field names', async () => {
  const instance = sdkTool('compose_scientific_workflow');
  const args = { draft_directory: '/workspace/PRIVATE_SENTINEL', steps: [mpnn({
    num_sequences: 0, seed: 0, sampling_temp: 2, PRIVATE_SENTINEL: 'PRIVATE_SENTINEL' })] };
  await rejected(instance, args, /num_sequences: must be >= 1/);
  await assert.rejects(() => instance.invoke(args), error => {
    assert.match(error.message, /seed: must be >= 1/);
    assert.match(error.message, /sampling_temp: must be <= 1/);
    assert.doesNotMatch(error.message, /PRIVATE_SENTINEL/);
    return true;
  });
});

test('unrelated tools and other servers retain the original call and generic error', async () => {
  for (const [name, server] of [['execute_command', 'environment-execution'], ['compose_scientific_workflow', 'other']]) {
    const instance = make(name, { type: 'object', required: ['required_field'] }, async () => { calls++; }, server);
    assert.equal(Object.hasOwn(instance, 'call'), false);
    await assert.rejects(() => instance.invoke({}), error => {
      assert.ok(error instanceof ToolInputParsingException);
      assert.equal(error.message, 'Received tool input did not match expected schema');
      return true;
    });
  }
});

test('formatter preserves the exact original parsing exception object and call arguments', async () => {
  const error = new ToolInputParsingException('original', '{}');
  const input = {};
  const config = { tags: ['unchanged'] };
  let seen;
  const fake = { name: 'compose_scientific_workflow_mcp_environment-execution',
    schema: { type: 'object', required: ['draft_directory'] },
    async call(...args) { seen = args; throw error; } };
  helper.attach(fake, 'environment-execution', 'compose_scientific_workflow');
  await assert.rejects(() => fake.call(input, config), caught => caught === error);
  assert.deepEqual(seen, [input, config]);
  assert.equal(seen[0], input); assert.equal(seen[1], config);
  assert.match(error.message, /\$\.draft_directory: required/);
});

test('handler exceptions and valid-input parsing exceptions pass through unchanged', async () => {
  for (const error of [new Error('handler failure'), new ToolInputParsingException('handler parsing failure', '{}')]) {
    const instance = make('compose_scientific_workflow', { type: 'object' }, async () => { throw error; });
    const message = error.message;
    await assert.rejects(() => instance.invoke({}), caught => caught === error && caught.message === message);
  }
});

test('valid composer then run calls keep real SDK results and idempotent study identity', async () => {
  const composed = JSON.parse(await sdkTool('compose_scientific_workflow').invoke({
    draft_directory: '/workspace/valid-draft', title: 'CPU fixture', steps: [{ id: 'data',
      kind: 'preparation', method: 'write-json', arguments: { filename: 'data.json', value: { exact: [4.55, 4.325] } } },
      { id: 'report', kind: 'analysis', method: 'report', arguments: { title: 'CPU report',
        sections: [{ title: 'Exact stored values', file: { step: 'data', file: 'data.json' }, format: 'markdown' }] } }],
    deliverables: [{ name: 'data.json', role: 'data', source: { step: 'data', file: 'data.json' } },
      { name: 'report.md', role: 'report', source: { step: 'report', file: 'report.md' } }], finalize: true }));
  assert.equal(composed.isError, false, JSON.stringify(composed));
  const draft = JSON.parse(composed.content[0].text);
  assert.equal(draft.finalized, true);
  const args = { plan_file: draft.plan_file, output_directory: '/workspace/valid-study' };
  const throughFactory = JSON.parse(await sdkTool('run_scientific_workflow').invoke(args));
  assert.deepEqual(throughFactory, lastSDKReply);
  const direct = await client.callTool({ name: 'run_scientific_workflow', arguments: args });
  const replay = JSON.parse(await sdkTool('run_scientific_workflow').invoke(args));
  assert.deepEqual(replay, direct);
  assert.equal(throughFactory.isError, false);
  assert.equal(JSON.parse(throughFactory.content[0].text).study_admission, 'accepted');
  assert.equal(JSON.parse(throughFactory.content[0].text).id, JSON.parse(replay.content[0].text).id);
});

test('pinned factory patch refuses missing duplicate and already-patched anchors', () => {
  for (const value of ['', helper.ANCHOR.repeat(2), `${helper.ANCHOR}\n${helper.CALL}`]) {
    assert.throws(() => helper.patchFactory(value), /Unsupported pinned MCP tool factory/);
  }
});

test('LangChain tool-call envelopes preserve strict rejection and do not dispatch SDK calls', async () => {
  await rejected(sdkTool('compose_scientific_workflow'), { type: 'tool_call', id: 'fixture-call',
    name: 'compose_scientific_workflow_mcp_environment-execution', args: {
      draft_directory: '/workspace/invalid-envelope', steps: [mpnn({ num_sequences: 9 })] } },
  /\$\.steps\[0\]\.arguments\.num_sequences: must be <= 8/);
});

test('many invalid fields remain bounded and preserve all original input bytes', async () => {
  await rejected(sdkTool('compose_scientific_workflow'), { draft_directory: '/workspace/multiple',
    steps: Array.from({ length: 12 }, (_, i) => ({ ...mpnn({ num_sequences: 0, seed: 0, sampling_temp: 2 }), id: `step${i}` })) },
  /num_sequences: must be >= 1/);
});

test('nested file alternatives report missing declared fields without irrelevant type constraints', async () => {
  const args = { draft_directory: '/workspace/file-reference', steps: [mpnn({ backbone: { step: 'earlier' } })] };
  await rejected(sdkTool('compose_scientific_workflow'), args, /\$\.steps\[0\]\.arguments\.backbone\.file: required/);
  await assert.rejects(() => sdkTool('compose_scientific_workflow').invoke(args), error => {
    assert.doesNotMatch(error.message, /undefined|must have type string/);
    return true;
  });
});
