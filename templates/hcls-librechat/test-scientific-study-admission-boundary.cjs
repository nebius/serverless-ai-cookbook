// Exercise the actual ToolNode and enclosing Run completion callback. The old
// pair-only gate did not include the host's graph-only PostToolBatch notice.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const installed = process.env.SCIENTIFIC_ADMISSION_INSTALLED === '1';
const graphPath = process.env.SCIENTIFIC_ADMISSION_GRAPH;
if (!graphPath) throw new Error('Boundary proof requires the pinned Graph path.');
const r = Module.createRequire(graphPath);
const helperPath = installed ? '/opt/hcls-librechat/scientific-study-admission.cjs' : path.join(__dirname, 'scientific-study-admission.cjs');
const acknowledge = require(helperPath);
const graphSource = fs.readFileSync(graphPath, 'utf8');
if (installed) {
  assert.match(graphSource, /const studyAdmissionText = require\('\/opt\/hcls-librechat\/scientific-study-admission.cjs'\)/);
} else {
  // Candidate-only proof: compile the pinned Graph in memory, resolving only
  // the candidate admission helper. Installed mode never compiles or patches.
  const compiled = new Module(graphPath, module);
  compiled.filename = graphPath;
  compiled.paths = Module._nodeModulePaths(path.dirname(graphPath));
  compiled.require = (name) => name === '/opt/hcls-librechat/scientific-study-admission.cjs' ? acknowledge : r(name);
  const source = graphSource.includes('const studyAdmissionText =') ? graphSource : acknowledge.patchGraph(graphSource);
  compiled._compile(source, graphPath);
  require.cache[graphPath] = compiled;
}
const { Run } = r('../run.cjs');
const { HookRegistry } = r('@librechat/agents');
const { HumanMessage } = r('@langchain/core/messages');
const name = 'run_scientific_workflow_mcp_environment-execution';
const id = '11111111-1111-5111-8111-111111111111';
let saved = { id: 'call-admission', name, output: JSON.stringify({ id, job_id: id,
  durable_study: true, study_admission: 'accepted', state: 'queued', status: 'running' }) };
if (process.env.SCIENTIFIC_ADMISSION_RETAINED_V59_MESSAGES) {
  const raw = JSON.parse(fs.readFileSync(process.env.SCIENTIFIC_ADMISSION_RETAINED_V59_MESSAGES));
  const calls = (raw.body ?? raw).flatMap((m) => m.content ?? []).filter((p) => p.tool_call?.name === name);
  assert.equal(calls.length, 1); saved = calls[0].tool_call;
}
const apiPath = process.env.SCIENTIFIC_ADMISSION_API || '/app/packages/api/dist/index.cjs';
const rawApi = fs.readFileSync(apiPath, 'utf8');
const apiSource = installed ? rawApi : acknowledge.patchBudgetHook(rawApi);
const region = apiSource.match(/\/\/#region src\/agents\/stepBudget\.ts\n([\s\S]*?)\/\/#endregion/);
assert.ok(region, 'Exact pinned host budget-hook region must be present.');
// Evaluate the installed host function alone: loading the whole API bundle
// initializes unrelated application services. This is not a duplicate hook.
const { createStepBudgetHook, remainingToolRounds } = new Function('_librechat_data_schemas',
  `${region[1]}; return { createStepBudgetHook, remainingToolRounds };`)({ logger: { debug() {} } });

async function boundary({ nearBudget = true, notice = 'host', sibling = false,
  receipt = saved.output, completionCallback = true } = {}) {
  const hooks = new HookRegistry();
  const budgetHook = createStepBudgetHook({ recursionLimit: 30 });
  const hookInput = { entries: [{ toolName: 'fixture', status: 'success' }] };
  if (nearBudget) for (let i = 0; i < 10; i++) assert.deepEqual(await budgetHook(hookInput), {});
  hooks.register('PostToolBatch', { internal: true, hooks: [async (input) => {
    const result = await budgetHook(input);
    if (notice === 'host') return result;
    const text = result.injectedMessages?.[0]?.content ?? result.additionalContext ?? 'fixture notice';
    if (notice === 'steer') return { injectedMessages: [{ role: 'user', source: 'steer', content: text }] };
    if (notice === 'lookalike') return { additionalContext: text };
    throw new Error('Unknown test notice.');
  }] });
  const definitions = [{ name, parameters: { type: 'object', properties: {} } }];
  if (sibling) definitions.push({ name: 'other_tool', parameters: { type: 'object', properties: {} } });
  const run = await Run.create({ runId: 'admission-boundary-fixture', hooks,
    eagerEventToolExecution: { enabled: true }, graphConfig: { type: 'standard', agents: [{
      agentId: 'default', provider: 'openai', clientOptions: {}, tools: [], toolDefinitions: definitions,
    }] } });
  const g = run.Graph;
  const calls = [{ name, id: saved.id, args: {} }];
  if (sibling) calls.push({ name: 'other_tool', id: 'call-sibling', args: {} });
  g.overrideTestModel(['FIXTURE_TOOL_CALL', 'PROVIDER_PATH_SENTINEL'], 0, calls);
  let generations = 0;
  const fakeStream = g.overrideModel._streamResponseChunks.bind(g.overrideModel);
  g.overrideModel._streamResponseChunks = function (...args) { generations++; return fakeStream(...args); };
  const events = [];
  let executions = 0;
  const callbacks = completionCallback ? [{ handleCustomEvent: run.createCustomEventCallback() }] : [];
  for await (const event of run.graphRunnable.streamEvents({ messages: [new HumanMessage('CPU fixture; no provider or scientific execution')] },
    { version: 'v2', recursionLimit: 30, callbacks })) {
    events.push(event);
    if (event.event === 'on_custom_event' && event.name === 'on_tool_execute') {
      executions += event.data.toolCalls.length;
      event.data.resolve(event.data.toolCalls.map((call) => ({ toolCallId: call.id, status: 'success',
        content: call.name === name ? receipt : 'other completed result' })));
    }
  }
  return { g, events, generations, executions, reply: g.messages.at(-1) };
}

test('real event-driven ToolNode plus Run callback acknowledges near-budget admission without another model generation', async () => {
  const result = await boundary();
  assert.equal(result.generations, 1);
  assert.equal(result.executions, 1);
  assert.match(result.reply.content, /Study accepted:/);
  assert.match(result.reply.content, new RegExp(JSON.parse(saved.output).id));
  assert.equal(result.reply.response_metadata.scientific_admission_acknowledgement, true);
  const notice = result.g.messages.at(-2);
  assert.equal(notice.getType(), 'human');
  assert.equal(notice.additional_kwargs.role, 'system');
  assert.equal(notice.additional_kwargs.source, 'scientific-step-budget');
  assert.equal(notice.additional_kwargs.provenance.parts[0].attribution, 'synthetic');
  assert.match(notice.content, /about 3 more tool-calling rounds/);
  assert.equal([...result.g.pendingToolCallsByStep.values()].some((set) => set.size), false);
  const deltas = result.events.filter((e) => e.name === 'on_message_delta')
    .flatMap((e) => e.data.delta.content ?? []).filter((part) => part.text === result.reply.content);
  assert.equal(deltas.length, 1, 'Exactly one normal final text emission.');
  assert.equal(result.events.at(-1).event, 'on_chain_end');
});
test('real ToolNode admission before budget notice still acknowledges once', async () => {
  const result = await boundary({ nearBudget: false });
  assert.equal(result.generations, 1); assert.match(result.reply.content, /Study accepted:/);
});
for (const notice of ['steer', 'lookalike']) test(`real ToolNode ${notice} message is not skipped`, async () => {
  const result = await boundary({ notice });
  assert.equal(result.generations, 2); assert.equal(result.reply.content, 'PROVIDER_PATH_SENTINEL');
});
test('real ToolNode completed multi-tool batch retains the normal route', async () => {
  const result = await boundary({ sibling: true });
  assert.equal(result.executions, 2); assert.equal(result.generations, 2);
  assert.equal(result.reply.content, 'PROVIDER_PATH_SENTINEL');
});
test('real ToolNode unknown admission retains the normal route despite a tagged notice', async () => {
  const result = await boundary({ receipt: JSON.stringify({ ...JSON.parse(saved.output), study_admission: 'unknown' }) });
  assert.equal(result.generations, 2); assert.equal(result.reply.content, 'PROVIDER_PATH_SENTINEL');
});
test('missing Run completion callback retains unresolved pending veto', async () => {
  const result = await boundary({ completionCallback: false });
  assert.equal(result.generations, 2); assert.equal(result.reply.content, 'PROVIDER_PATH_SENTINEL');
  assert.equal([...result.g.pendingToolCallsByStep.values()].some((set) => set.size > 0), true);
});
test('pinned budget-hook stamp preserves notice text, role, round count and threshold', async () => {
  assert.equal(remainingToolRounds(30, 10), 4); assert.equal(remainingToolRounds(30, 11), 3);
  const originalRegion = rawApi.match(/\/\/#region src\/agents\/stepBudget\.ts\n([\s\S]*?)\/\/#endregion/)[1];
  const original = new Function('_librechat_data_schemas', `${originalRegion}; return createStepBudgetHook;`)({ logger: { debug() {} } })({ recursionLimit: 30 });
  const candidate = createStepBudgetHook({ recursionLimit: 30 });
  for (let i = 0; i < 15; i++) {
    const input = { entries: [{ toolName: 'fixture' }] };
    const before = await original(input), after = await candidate(input);
    assert.equal(after.injectedMessages?.[0]?.content ?? after.additionalContext,
      before.injectedMessages?.[0]?.content ?? before.additionalContext);
    if (i < 10) assert.deepEqual(after, {});
  }
});
