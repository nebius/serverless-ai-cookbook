const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const installed = process.env.SCIENTIFIC_ADMISSION_INSTALLED === '1';
const helperPath = installed ? '/opt/hcls-librechat/scientific-study-admission.cjs' : path.join(__dirname, 'scientific-study-admission.cjs');
const acknowledge = require(helperPath);
const name = 'run_scientific_workflow_mcp_environment-execution';
const id = '11111111-1111-5111-8111-111111111111';
const receipt = () => ({ id, job_id: id, state: 'queued', status: 'running', durable_study: true,
  study_admission: 'accepted', new_study_admitted: true });
function messages(value = receipt()) {
  return [{ getType: () => 'ai', tool_calls: [{ name, id: 'call-one', args: {} }] },
    { getType: () => 'tool', name, tool_call_id: 'call-one', content: JSON.stringify(value), status: 'success' }];
}

for (const state of ['queued', 'running', 'publishing']) test(`confirmed ${state} is lifecycle only`, () => {
  const input = messages({ ...receipt(), state, title: '16 overlapping samples', step_count: 16 });
  const before = JSON.stringify(input);
  const result = acknowledge(input);
  assert.match(result, new RegExp(id));
  assert.match(result, /\/demos\?tab=runs/);
  assert.match(result, /not completion or scientific results/);
  assert.doesNotMatch(result, /16|overlapping/);
  assert.equal(JSON.stringify(input), before);
});
for (const [label, change] of [
  ['legacy', { durable_study: false }], ['unknown admission', { study_admission: 'unknown' }],
  ['admission lock pending', { status: 'admission_pending' }],
  ['failed', { state: 'failed', status: 'failed' }], ['terminal replay', { state: 'completed', status: 'completed' }],
  ['needs attention', { state: 'needs_attention' }], ['unresolved', { admission_unknown: true }],
  ['blocked queue', { queue_blocked: true }], ['cancellation', { cancellation_unknown: true }],
  ['failure receipt', { failure: { message: 'original failure' } }], ['MCP error', { isError: true }],
  ['identity mismatch', { job_id: '22222222-2222-5222-8222-222222222222' }],
  ['bad identity', { id: 'not-a-study' }],
]) test(`${label} remains on normal path`, () => assert.equal(acknowledge(messages({ ...receipt(), ...change })), null));
test('existing ongoing admission replay has the same lifecycle acknowledgement', () => {
  assert.equal(acknowledge(messages()), acknowledge(messages({ ...receipt(), reused_existing_study: true, new_study_admitted: false })));
});
test('single text content block and LangChain legacy type accessor are supported', () => {
  const input = messages();
  input[1].content = [{ type: 'text', text: input[1].content }];
  for (const m of input) { m._getType = m.getType; delete m.getType; }
  assert.ok(acknowledge(input));
});
test('multi-call, unresolved sibling result, unrelated tool and malformed content do not terminate', () => {
  for (const change of [
    (m) => m[0].tool_calls.push({ name: 'other', id: 'call-two' }),
    (m) => m.splice(1, 0, { getType: () => 'tool', content: 'other result' }),
    (m) => { m[1].name = 'other'; }, (m) => { m[1].tool_call_id = 'other'; },
    (m) => { m[1].status = 'error'; }, (m) => { m[1].content = 'not JSON'; },
    (m) => { m[1].content = [{ type: 'text', text: m[1].content }, { type: 'image' }]; },
  ]) { const input = messages(); change(input); assert.equal(acknowledge(input), null); }
});
test('new user or already-emitted assistant message cannot replay the acknowledgement', () => {
  for (const type of ['human', 'ai']) assert.equal(acknowledge([...messages(), { getType: () => type, content: 'new turn' }]), null);
});
test('pinned patch refuses missing, duplicate or already-patched seam', () => {
  const anchor = '\t\t\tconst { messages } = state;\n\t\t\tconst discoveredNames = require_tools.extractToolDiscoveries(messages);';
  assert.throws(() => acknowledge.patchGraph(''), /Unsupported pinned/);
  assert.throws(() => acknowledge.patchGraph(anchor + anchor), /Unsupported pinned/);
  assert.throws(() => acknowledge.patchGraph(acknowledge.patchGraph(anchor)), /Unsupported pinned/);
});

// Set this for the exact installed image gate; no mounted runtime replacements.
// Local candidate proof compiles the pinned upstream module in memory only.
const graphPath = process.env.SCIENTIFIC_ADMISSION_GRAPH;
if (installed && !graphPath) throw new Error('Installed admission proof requires the actual Graph module.');
if (graphPath) {
  const source = fs.readFileSync(graphPath, 'utf8');
  const requireInstalled = Module.createRequire(graphPath);
  const { AIMessage, ToolMessage } = requireInstalled('@langchain/core/messages');
  const { toolsCondition } = requireInstalled('../tools/ToolNode.cjs');
  const completion = require(installed ? '/opt/hcls-librechat/scientific-completion.cjs' : './scientific-completion.cjs');
  let graph;
  if (installed) {
    assert.match(source, /const studyAdmissionText = require\('\/opt\/hcls-librechat\/scientific-study-admission.cjs'\)/);
    graph = requireInstalled(graphPath);
  } else {
    const compiled = new Module(graphPath, module);
    compiled.filename = graphPath;
    compiled.paths = Module._nodeModulePaths(path.dirname(graphPath));
    compiled.require = (request) => request === '/opt/hcls-librechat/scientific-study-admission.cjs' ? acknowledge : requireInstalled(request);
    compiled._compile(acknowledge.patchGraph(source), graphPath);
    graph = compiled.exports;
  }
  function harness() {
    const events = [];
    const instance = { breakerAbort: new AbortController(), breakerEpoch: 0,
      resolveTrippedBreakerReason: () => null, agentContexts: new Map([['default', { provider: 'openai' }]]),
      preemptHaltReason: null, getPreparedToolsForBinding() { throw new Error('NORMAL_PROVIDER_PATH'); },
      getStepKey: () => 'ack-step', messageIdsByStepKey: new Map(), prelimMessageIdsByStepKey: new Map(),
      runProducedAiMessageIds: new Set(),
      async dispatchRunStep(key, event, metadata) { events.push({ kind: 'creation', key, event, metadata }); },
      getStepIdByKey: () => 'step-ack',
      async dispatchMessageDelta(step, delta, metadata) { events.push({ kind: 'delta', step, delta, metadata }); } };
    return { instance, events, invoke: graph.StandardGraph.prototype.createCallModel.call(instance) };
  }
  function realMessages(value = receipt()) {
    return [new AIMessage({ id: 'original-assistant', content: '', tool_calls: [{ name, id: 'call-one', args: {}, type: 'tool_call' }] }),
      new ToolMessage({ id: 'original-tool-result', name, tool_call_id: 'call-one', content: JSON.stringify(value), status: 'success' })];
  }
  test('pinned Graph emits normal final text with one identity, preserves history and ends without provider', async () => {
    const h = harness(); const input = realMessages(); const before = JSON.stringify(input);
    const result = await h.invoke({ messages: input }, { metadata: { langgraph_step: 3 } });
    assert.equal(result.messages.length, 1);
    const reply = result.messages[0];
    assert.equal(reply.getType(), 'ai');
    assert.equal(reply.id, h.events[0].event.message_creation.message_id);
    assert.equal(reply.id, h.instance.messageIdsByStepKey.get('ack-step'));
    assert.deepEqual(h.events[1].delta.content, [{ type: 'text', text: reply.content }]);
    assert.equal(h.events[0].event.type, 'message_creation');
    assert.equal(h.events[0].event.message_creation.content_type, 'text');
    assert.equal(h.instance.runProducedAiMessageIds.has(reply.id), true);
    assert.equal(reply.usage_metadata, undefined);
    assert.equal(reply.response_metadata.scientific_admission_acknowledgement, true);
    assert.equal(toolsCondition({ messages: [...input, reply] }, 'tools', new Set()), '__end__');
    assert.equal(completion({ content: [{ type: 'text', text: reply.content }] }), false);
    assert.equal(JSON.stringify(input), before);
    await assert.rejects(h.invoke({ messages: [...input, reply] }, { metadata: {} }), /NORMAL_PROVIDER_PATH/);
    assert.equal(h.events.length, 2, 'No duplicate acknowledgment on graph re-entry.');
  });
  test('pinned Graph error and terminal receipts preserve normal provider route', async () => {
    for (const value of [{ ...receipt(), state: 'completed', status: 'completed' },
      { ...receipt(), study_admission: 'unknown' }, { ...receipt(), failure: { message: 'original' } }]) {
      const h = harness(); await assert.rejects(h.invoke({ messages: realMessages(value) }, { metadata: {} }), /NORMAL_PROVIDER_PATH/);
      assert.equal(h.events.length, 0);
    }
  });
  test('pinned Graph retains normal routing while any upstream tool completion is unresolved', async () => {
    const h = harness(); h.instance.pendingToolCallsByStep = new Map([['other-step', new Set(['pending-call'])]]);
    await assert.rejects(h.invoke({ messages: realMessages() }, { metadata: {} }), /NORMAL_PROVIDER_PATH/);
    assert.equal(h.events.length, 0);
  });
  test('real compiled graph streams one final acknowledgement and ends with matching state identity', async () => {
    const g = new graph.StandardGraph({ runId: 'admission-test', agents: [{
      agentId: 'default', provider: 'openai', clientOptions: {}, tools: [],
    }] });
    g.getPreparedToolsForBinding = () => { throw new Error('PROVIDER_MUST_NOT_INITIALIZE'); };
    const input = realMessages(); const before = JSON.stringify(input);
    const events = [];
    for await (const event of g.createWorkflow().streamEvents({ messages: input }, { version: 'v2' })) events.push(event);
    const creations = events.filter((e) => e.event === 'on_custom_event' && e.name === 'on_run_step');
    const deltas = events.filter((e) => e.event === 'on_custom_event' && e.name === 'on_message_delta');
    assert.equal(creations.length, 1); assert.equal(deltas.length, 1);
    const reply = g.messages.at(-1);
    assert.equal(reply.getType(), 'ai');
    assert.equal(reply.id, creations[0].data.stepDetails.message_creation.message_id);
    assert.deepEqual(deltas[0].data.delta.content, [{ type: 'text', text: reply.content }]);
    assert.equal(g.runProducedAiMessageIds.has(reply.id), true);
    assert.equal(completion({ content: [{ type: 'text', text: reply.content }] }), false);
    assert.equal(g.messages.length, input.length + 1);
    assert.equal(JSON.stringify(input), before);
    assert.equal(events.at(-1).event, 'on_chain_end');
  });
  test('pinned Graph never persists an acknowledgement when normal emission is unavailable', async () => {
    const h = harness(); h.instance.messageIdsByStepKey.set('ack-step', 'existing-message');
    await assert.rejects(h.invoke({ messages: realMessages() }, { metadata: {} }), /Unable to emit/);
    assert.equal(h.events.length, 0); assert.equal(h.instance.runProducedAiMessageIds.size, 0);
  });
  if (process.env.SCIENTIFIC_ADMISSION_RETAINED_MESSAGES) test('exact retained customer admission returns lifecycle facts only', async () => {
    const raw = fs.readFileSync(process.env.SCIENTIFIC_ADMISSION_RETAINED_MESSAGES);
    const calls = JSON.parse(raw).flatMap((m) => m.content ?? []).filter((part) => part.type === 'tool_call')
      .map((part) => part.tool_call).filter((call) => call?.name === name);
    assert.equal(calls.length, 1);
    const original = calls[0]; const value = JSON.parse(original.output);
    const input = [new AIMessage({ id: 'retained-assistant', content: '', tool_calls: [{ name, id: original.id, args: {}, type: 'tool_call' }] }),
      new ToolMessage({ id: 'retained-tool-result', name, tool_call_id: original.id, content: original.output, status: 'success' })];
    const h = harness(); const result = await h.invoke({ messages: input }, { metadata: {} });
    assert.match(result.messages[0].content, new RegExp(value.id));
    assert.match(result.messages[0].content, new RegExp(`Observed state: \\*\\*${value.state}\\*\\*`));
    assert.doesNotMatch(result.messages[0].content, /overlap|sample|PhenoAge|AltumAge|16 overlappende/i);
    assert.equal(input[1].content, original.output);
    assert.deepEqual(fs.readFileSync(process.env.SCIENTIFIC_ADMISSION_RETAINED_MESSAGES), raw);
  });
}
