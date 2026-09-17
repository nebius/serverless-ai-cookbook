const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require(process.env.TYPESCRIPT_MODULE || 'typescript');
const source = ts.transpileModule(fs.readFileSync(`${__dirname}/comparison.ts`, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const exported = {};
vm.runInNewContext(source, { exports: exported });
const { compareBatch, comparisonCsv } = exported;
const row = (model, profile, score) => ({ id: model + profile, batch_id: 'batch', status: 'completed', created_at: 'now',
  state: { config: { profile_id: profile, clinician_model: model, clinician_models: ['a', 'b'], profile_ids: ['p1', 'p2'] },
    benchmark_eligible: true, judgment: { model: 'judge', overall_score: score } } });
test('only fully paired profiles contribute; partial failures are not zero scores', () => {
  const rows = [row('a', 'p1', 4), row('b', 'p1', 2), row('a', 'p2', 6), { ...row('b', 'p2', 6), status: 'failed' }];
  const result = compareBatch(rows, 'batch');
  assert.equal(result.matched_profiles.join(','), 'p1');
  assert.equal(result.summaries[0].mean, 4);
  assert.equal(result.summaries[1].mean, 2);
  assert.equal(result.summaries[1].failed, 1);
  assert.equal(result.summaries[1].planned, 2);
  assert.ok(comparisonCsv(result).includes('"b","2","1","1","0","0","1","2"'));
});
test('intervention, changing judges and incomplete batches do not produce misleading means', () => {
  const a = row('a', 'p1', 4), b = row('b', 'p1', 6);
  b.state.intervened = true;
  assert.equal(compareBatch([a, b], 'batch').summaries[0].mean, null);
  b.state.intervened = false; b.state.judgment.model = 'other-judge';
  assert.equal(compareBatch([a, b], 'batch').matched_profiles.length, 0);
  assert.equal(compareBatch([a], 'batch').summaries[1].missing, 2);
  assert.equal(compareBatch([a], 'different-batch').summaries.length, 0);
});
