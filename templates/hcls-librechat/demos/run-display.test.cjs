const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require(process.env.TYPESCRIPT_MODULE || 'typescript');
const source = ts.transpileModule(fs.readFileSync(`${__dirname}/run-display.ts`, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const exported = {};
vm.runInNewContext(source, { exports: exported });
test('pending uploads never masquerade as GPU execution or capacity waiting', () => {
  const display = exported.runDisplay({ protocol: 'scientific-artifact-upload-v1', status: 'queued' });
  assert.equal(display.status, 'Upload pending');
  assert.equal(display.showComputeTiming, false);
  assert.equal(display.showResult, false);
  assert.match(display.description, /not inference/);
  assert.equal(display.terminal, false);
});
test('finalized uploads and failed uploads keep distinct terminal labels', () => {
  assert.equal(exported.runDisplay({ protocol: 'scientific-artifact-upload-v1', status: 'succeeded' }).status, 'Upload finalized');
  assert.equal(exported.runDisplay({ operation: { protocol: 'scientific-artifact-upload-v1' }, status: 'failed' }).status, 'Upload failed');
});
test('ordinary inference preserves status, preemption and result availability', () => {
  assert.equal(exported.runDisplay({ protocol: 'scientific-batch-v1', status: 'succeeded' }).showResult, true);
  assert.equal(exported.runDisplay({ status: 'preempted' }).terminal, true);
  assert.equal(exported.runDisplay({ status: 'queued' }).description, 'Accepted; execution has not started');
});
test('batch orchestration does not masquerade as admitted GPU execution', () => {
  for (const shape of [{ protocol: 'scientific-batch-v1' }, { operation: { protocol: 'scientific-batch-v1' } }]) {
    const active = exported.runDisplay({ ...shape, status: 'running' });
    assert.equal(active.status, 'Workflow active');
    assert.equal(active.showComputeTiming, false);
    assert.match(active.description, /queued, loading or computing/);
    assert.match(active.description, /Details/);
    for (const status of ['succeeded', 'failed', 'cancelled', 'preempted', 'expired']) {
      const terminal = exported.runDisplay({ ...shape, status });
      assert.equal(terminal.status, status);
      assert.equal(terminal.terminal, true);
      assert.equal(terminal.showComputeTiming, false);
      assert.equal(terminal.description, '');
    }
  }
});
test('legacy cold_start_seconds label includes queue instead of claiming activation time', () => {
  const display = exported.runDisplay({ protocol: 'openai-chat', status: 'succeeded' });
  assert.equal(display.showComputeTiming, true);
  assert.equal(display.readyTimingLabel, 'Accepted → ready (includes queue)');
  assert.match(fs.readFileSync(`${__dirname}/Demos.tsx`, 'utf8'), /display\.readyTimingLabel/);
});

test('a completed polling window does not imply study or model timeout', () => {
  const display = exported.studyDisplay('observation_expired');
  assert.equal(display.status, 'Waiting for an update');
  assert.match(display.description, /not the study/);
  assert.match(display.description, /while the study supervisor is available/);
  assert.doesNotMatch(display.status, /failed|expired|completed|succeeded/);
});
test('admission waiting and read reconnection do not imply new or repeated inference', () => {
  assert.equal(exported.studyDisplay('waiting_admission').status, 'Waiting to start');
  assert.match(exported.studyDisplay('waiting_admission').description, /has not been accepted/);
  assert.equal(exported.studyDisplay('observation_interrupted').status, 'Reconnecting to the existing operation');
  assert.match(exported.studyDisplay('observation_interrupted').description, /do not submit another copy/);
});
test('terminal and unknown study states remain explicit', () => {
  for (const state of ['completed', 'failed', 'cancelled', 'needs_attention', 'future_unknown_state']) {
    assert.equal(exported.studyDisplay(state).status, state);
    assert.equal(exported.studyDisplay(state).description, '');
  }
});
test('Runs uses the label while retaining the actual recorded state and cancellation policy', () => {
  const ui = fs.readFileSync(`${__dirname}/Demos.tsx`, 'utf8');
  assert.match(ui, /studyDisplay\(study\.state\)/);
  assert.match(ui, /Recorded state: \$\{study\.state\}/);
  assert.match(ui, /\['completed', 'failed', 'cancelled', 'needs_attention'\]\.includes\(study\.state\)/);
});
