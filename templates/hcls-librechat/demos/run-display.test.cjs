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
