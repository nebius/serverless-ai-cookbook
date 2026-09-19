// Candidate SDK/composer gate using the actual pinned installed LangChain tool.
// Mounting candidate Python is source evidence, NOT a final-image qualification.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const { spawnSync } = require('node:child_process');
const r = createRequire('/app/api/server/services/ToolService.js');
const { DynamicStructuredTool } = r('@librechat/agents/langchain/tools');
const { Client } = r('@modelcontextprotocol/sdk/client/index.js');
const { StdioClientTransport } = r('@modelcontextprotocol/sdk/client/stdio.js');
const root = process.env.SCIENTIFIC_REPORT_CANDIDATE || '/opt/bionemo';
const python = '/opt/scientific-client/bin/python';
const environment = { ...process.env, PYTHONPATH: root, PYTHONDONTWRITEBYTECODE: '1',
  SCIENTIFIC_WORKSPACE: '/workspace', SCIENTIFIC_MODELS_MCP_URL: 'https://platform.test/mcp',
  SCIENTIFIC_MODELS_API_KEY: 'cpu-fixture-only', SCIENTIFIC_STUDY_OWNER_MODE: 'first-instance',
  SEED_DEFAULT_USER_EMAIL: 'title-boundary@example.test' };
const client = new Client({ name: 'report-title-boundary', version: '1' });
let tool, schema, executed = 0;
test.before(async () => {
  await client.connect(new StdioClientTransport({ command: python,
    args: [path.join(root, 'execution-mcp.py')], env: environment }));
  schema = (await client.listTools()).tools.find(t => t.name === 'compose_scientific_workflow').inputSchema;
  tool = new DynamicStructuredTool({ name: 'compose_scientific_workflow_mcp_environment-execution',
    description: 'Exact listed composer contract', schema, func: async args => {
      executed++;
      return JSON.stringify(await client.callTool({ name: 'compose_scientific_workflow', arguments: args }));
    } });
});
test.after(async () => { await client.close(); });
async function compose(args) {
  const result = JSON.parse(await tool.invoke(args));
  return { result, value: JSON.parse(result.content[0].text) };
}

test('all three exact retained rejections cross installed tool validation without relaxing plan dependencies', async t => {
  if (!process.env.SCIENTIFIC_REPORT_RETAINED_MESSAGES) return t.skip('Retained private trace not mounted');
  const saved = JSON.parse(fs.readFileSync(process.env.SCIENTIFIC_REPORT_RETAINED_MESSAGES));
  const calls = (saved.body ?? saved).flatMap(m => m.content ?? []).map(c => c.tool_call)
    .filter(c => c?.name === tool.name);
  assert.equal(calls.filter(c => c.output.startsWith('Error:')).length, 3);
  let formerRejections = 0;
  for (const call of calls) {
    const args = JSON.parse(call.args);
    const reply = await compose(args);
    if (call.output.startsWith('Error:')) {
      formerRejections++;
      assert.equal(reply.value.inference_submitted, false);
      if (args.finalize) {
        // Its late diagnostic draft really has missing dummy input/dependencies.
        // The presentation default must not repair or admit that damaged plan.
        assert.equal(reply.result.isError, true);
        assert.equal(reply.value.finalized, false);
        assert.match(reply.value.validation_error, /existing valid JSON file|earlier|prior|preced|unknown|reference/i);
      } else {
        assert.equal(reply.result.isError, false);
        assert.equal(reply.value.step_count, 8);
      }
    } else assert.equal(reply.result.isError, false);
  }
  assert.equal(formerRejections, 3);
});

test('explicit wrong-type blank and newline headings remain pre-transport errors', async () => {
  const before = executed;
  for (const title of [null, false, 7, {}, [], '', ' ', 'line\nbreak', 'trailing\r']) {
    await assert.rejects(() => tool.invoke({ draft_directory: '/workspace/invalid-title', title: 'Study',
      steps: [{ id: 'report', kind: 'analysis', method: 'report', arguments: { title,
        sections: [{ title: 'Data', file: '/workspace/data.csv', format: 'csv' }] } }] }),
      /Received tool input did not match expected schema/);
  }
  assert.equal(executed, before);
});

test('actual composer and durable report finish without a document title and preserve explicit numeric bytes', async () => {
  const args = { draft_directory: '/workspace/title-completion/draft', title: 'Stored numeric data',
    steps: [{ id: 'data', kind: 'preparation', method: 'write-json', arguments: {
      filename: 'measurement.json', value: { values: [4.55, 4.325] } } },
    { id: 'report', kind: 'analysis', method: 'report', arguments: { sections: [
      { title: 'Exact stored values', file: { step: 'data', file: 'measurement.json' }, format: 'markdown' }] } }],
    deliverables: [{ name: 'report.md', role: 'report', source: { step: 'report', file: 'report.md' } }],
    finalize: true };
  const composed = await compose(args);
  assert.equal(composed.result.isError, false); assert.equal(composed.value.finalized, true);
  const accepted = await client.callTool({ name: 'run_scientific_workflow', arguments: {
    plan_file: composed.value.plan_file, output_directory: '/workspace/title-completion/final' } });
  assert.equal(accepted.isError, false);
  const record = JSON.parse(accepted.content[0].text);
  const result = spawnSync(python, ['-c', 'import asyncio,json,sys; import scientific_study as s; r=None\nfor _ in range(3): r=asyncio.run(s.advance(sys.argv[1]))\nprint(json.dumps(r))', record.id],
    { env: environment, encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  const done = JSON.parse(result.stdout); assert.equal(done.state, 'completed');
  const body = fs.readFileSync(done.artifacts[0].path, 'utf8');
  assert.match(body, /^# Scientific study report\n/);
  assert.ok(body.includes('4.55') && body.includes('4.325'));
  const original = fs.readFileSync(done.steps.data.files['measurement.json'].path);
  const retained = fs.readFileSync(done.steps.report.files['sources/000.md'].path);
  assert.deepEqual(retained, original);
});
