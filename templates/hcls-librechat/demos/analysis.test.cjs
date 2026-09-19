const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
process.env.SCIENTIFIC_ANALYSIS_HELPERS = path.resolve(__dirname, '..');
const { compare, dockingBatch, aging, assembleReport } = require('./analysis.cjs');
const hash = (bytes) => crypto.createHash('sha256').update(bytes).digest('hex');

async function fixture(run) {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'analysis-adapter-test-'));
  try {
    await fs.writeFile(path.join(dir, 'reference.sdf'), 'reference bytes');
    await fs.writeFile(path.join(dir, 'result.json'), '{}');
    await fs.writeFile(path.join(dir, 'mapping.json'), '{}');
    const retained = {};
    const storage = {
      workspaceGet: async (key, relative) => {
        assert.equal(key, 'fixture-key');
        if (!['reference.sdf', 'result.json', 'mapping.json'].includes(relative)) throw new Error('Unowned input');
        const absolute = path.join(dir, relative);
        return { absolute, normalized: relative, size_bytes: (await fs.stat(absolute)).size };
      },
      retainWorkspaceBytes: async (key, name, bytes) => {
        retained[name] = bytes;
        return { saved: true, relative_path: name, path: '/workspace/' + name,
          size_bytes: bytes.length, sha256: hash(bytes) };
      },
      execute: async (_, argv) => {
        const output = argv.includes('--output') ? argv[argv.indexOf('--output') + 1]
          : path.join(argv[argv.indexOf('--output-dir') + 1], 'metrics.json');
        await fs.writeFile(output, JSON.stringify({ schema: 'test-only', method: 'existing-helper',
          poses: [{ rank: 1, status: 'comparable', pose_rmsd_angstrom: 1.25 }],
          all_poses_comparable: true, top_rank_pose_rmsd_angstrom: 1.25 }));
      },
    };
    await run({ dir, storage, retained });
  } finally { await fs.rm(dir, { recursive: true, force: true }); }
}
const args = { reference_file: 'reference.sdf', result_file: 'result.json', same_coordinate_frame: true };
test('report assembly uses existing files, preserves UTF-8 and exact CSV cells without inference', () => fixture(async ({ dir, storage, retained }) => {
  await fs.writeFile(path.join(dir, 'reference.sdf'), '# Verified method — Å\r\nUnchanged.\r\n');
  await fs.writeFile(path.join(dir, 'result.json'), 'run,rank,overlap\na,1,false\nb,1,true\n');
  storage.execute = async (_, argv, options) => {
    assert.equal(options.timeout, 50000);
    return require('node:util').promisify(require('node:child_process').execFile)('python3', argv, options);
  };
  const result = await assembleReport('fixture-key', { title: 'Complete study', output_directory: 'study/report-v2',
    sections: [{ title: 'Method', format: 'markdown', file: 'reference.sdf' },
      { title: 'Exact rows', format: 'csv', file: 'result.json' }] }, storage);
  const bytes = retained['study/report-v2/report.md'];
  assert.match(bytes.toString(), /\| a \| 1 \| false \|/);
  assert.ok(bytes.includes(await fs.readFile(path.join(dir, 'reference.sdf'))));
  assert.equal(result.files['report.md'].sha256, hash(bytes));
  assert.equal(result.files['report.md'].size_bytes, bytes.length);
  assert.equal(result.sections[1].row_count, 2);
  assert.equal(result.sections[1].column_count, 3);
  const provenance = JSON.parse(retained['study/report-v2/provenance.json']);
  assert.equal(provenance.workspace_sources[0].sha256, hash(await fs.readFile(path.join(dir, 'reference.sdf'))));
  assert.equal(result.inference_submitted, false);
  assert.equal(result.scientific_claims_validated, false);
  assert.equal(result.document_assembled, true);
  await fs.writeFile(path.join(dir, 'result.json'), 'run,rank,overlap\na,false\n');
  await assert.rejects(assembleReport('fixture-key', { title: 'Broken', output_directory: 'study/broken',
    sections: [{ title: 'Rows', format: 'csv', file: 'result.json' }] }, storage), /row width/);
  assert.equal(retained['study/broken/report.md'], undefined);
  await assert.rejects(assembleReport('fixture-key', { title: 'Escape', output_directory: '../outside', sections: [] }, storage), /workspace-relative/);
}));
test('report source mutation is rejected before publication', () => fixture(async ({ dir, storage, retained }) => {
  storage.execute = async (_, argv, options) => {
    await require('node:util').promisify(require('node:child_process').execFile)('python3', argv, options);
    await fs.writeFile(path.join(dir, 'reference.sdf'), 'mutated');
  };
  await assert.rejects(assembleReport('fixture-key', { title: 'Study', output_directory: 'study/new',
    sections: [{ title: 'Method', format: 'markdown', file: 'reference.sdf' }] }, storage), /changed during assembly/);
  assert.deepEqual(retained, {});
}));
test('multi-run docking uses existing helper once and retains true UTF-8 bytes and explicit denominators', () => fixture(async ({ storage, retained }) => {
  let executed = 0;
  storage.execute = async (_, argv, options) => {
    executed += 1;
    assert.equal(options.timeout, 50000);
    const runs = JSON.parse(await fs.readFile(argv[argv.indexOf('--runs') + 1], 'utf8'));
    assert.deepEqual(runs.map((run) => [run.run_id, run.group_id]), [['first', 'target'], ['second', 'target']]);
    assert.ok(runs.every((run) => run.reference_file.endsWith('/reference.sdf')));
    const folder = path.dirname(argv[argv.indexOf('--output') + 1]);
    await fs.writeFile(path.join(folder, 'metrics.json'), JSON.stringify({ schema: 'multi-run-test',
      method: 'existing-helper', summary: { run_count: 2, all_poses: { pose_count: 8 }, top_ranked_poses: { pose_count: 2 } },
      groups: [], runs: runs.map((run) => ({ ...run, metrics: { rank_facts: {}, requested_pose_count: 4, comparable_pose_count: 4 } })) }));
    await fs.writeFile(path.join(folder, 'report.md'), '# Report — RMSD Å\n');
    await fs.writeFile(path.join(folder, 'rows.csv'), 'run,rank\nfirst,1\n');
  };
  const result = await dockingBatch('fixture-key', { same_coordinate_frame: true, output_directory: 'study/docking',
    runs: ['first', 'second'].map((run_id) => ({ run_id, group_id: 'target', reference_file: 'reference.sdf', result_file: 'result.json' })) }, storage);
  assert.equal(executed, 1);
  assert.equal(result.metrics.summary.top_ranked_poses.pose_count, 2);
  const bytes = retained[result.files['report.md'].relative_path];
  assert.equal(result.files['report.md'].size_bytes, bytes.length);
  assert.notEqual(bytes.length, bytes.toString().length);
  assert.equal(result.files['report.md'].sha256, hash(bytes));
  assert.equal(result.provenance.inputs['0_result_file'].sha256, hash('{}'));
  assert.equal(result.files['report.md'].relative_path, 'study/docking/report.md');
  const full = JSON.parse(retained[result.files['metrics.json'].relative_path]);
  assert.deepEqual(result.metrics.runs[0].metrics.rank_facts, full.runs[0].metrics.rank_facts);
  assert.equal(result.metrics.runs[0].rank_facts, undefined);
  assert.equal(result.inference_submitted, false);
  await assert.rejects(dockingBatch('fixture-key', { same_coordinate_frame: true,
    runs: [{ run_id: 'same' }, { run_id: 'same' }] }, storage), /distinct/);
  assert.equal(executed, 1);
  await assert.rejects(dockingBatch('fixture-key', { output_directory: '../outside' }, storage), /workspace-relative/);
  assert.equal(executed, 1);
}));
test('typed docking adapter preserves actual helper metrics and exact byte/hash lineage', () => fixture(async ({ storage, retained }) => {
  const result = await compare('docking', 'fixture-key', args, storage);
  assert.equal(result.analysis_completed, true);
  assert.equal(result.inference_submitted, false);
  assert.equal(result.metrics.poses[0].pose_rmsd_angstrom, 1.25);
  assert.equal(result.provenance.inputs.reference_file.sha256, hash('reference bytes'));
  assert.equal(result.provenance.inputs.result_file.sha256, hash('{}'));
  assert.equal(result.files['metrics.json'].sha256, result.provenance.result_sha256);
  assert.equal(retained[result.files['metrics.json'].relative_path].length, result.files['metrics.json'].size_bytes);
}));
test('explicit non-comparable helper exit retains the result instead of inventing a score', () => fixture(async ({ storage }) => {
  storage.execute = async (_, argv) => {
    await fs.writeFile(argv[argv.indexOf('--output') + 1], JSON.stringify({
      poses: [{ rank: 1, status: 'not_comparable', reason: 'stereochemistry differs' }], all_poses_comparable: false }));
    throw Object.assign(new Error('not comparable'), { code: 2 });
  };
  const result = await compare('docking', 'fixture-key', args, storage);
  assert.equal(result.metrics.all_poses_comparable, false);
  assert.equal(result.metrics.poses[0].pose_rmsd_angstrom, undefined);
}));
test('docking report, rank facts and explicit threshold query survive the typed adapter', () => fixture(async ({ storage, retained }) => {
  storage.execute = async (_, argv) => {
    assert.deepEqual(argv.slice(argv.indexOf('--threshold-query')), ['--threshold-query', '0.7', '1.2']);
    const folder = path.dirname(argv[argv.indexOf('--output') + 1]);
    const metrics = { poses: [], rank_facts: { best_rmsd: { ranks: [3] }, lowest_confidence: { ranks: [4] } },
      threshold_counts: [{ matching_pose_count: 1, eligible_comparable_pose_count: 3 }] };
    await fs.writeFile(path.join(folder, 'metrics.json'), JSON.stringify(metrics));
    await fs.writeFile(path.join(folder, 'report.md'), '# Deterministic rank report\n');
    await fs.writeFile(path.join(folder, 'rows.csv'), 'rank,rmsd\n3,1.2109\n');
  };
  const result = await compare('docking', 'fixture-key', { ...args,
    threshold_queries: [{ confidence_above: 0.7, rmsd_below_angstrom: 1.2 }] }, storage);
  assert.deepEqual(result.metrics.rank_facts.best_rmsd.ranks, [3]);
  assert.deepEqual(result.metrics.rank_facts.lowest_confidence.ranks, [4]);
  assert.equal(result.metrics.threshold_counts[0].matching_pose_count, 1);
  assert.ok(retained[result.files['report.md'].relative_path].toString().includes('Deterministic'));
  assert.ok(retained[result.files['rows.csv'].relative_path].toString().includes('1.2109'));
}));
test('helper failures retain diagnostics and never claim completed analysis', () => fixture(async ({ storage, retained }) => {
  storage.execute = async () => { throw Object.assign(new Error('failed'), { code: 1, stderr: 'Invalid source coordinates' }); };
  await assert.rejects(compare('docking', 'fixture-key', args, storage), /no scientific metrics accepted/);
  assert.equal(Object.values(retained)[0].toString(), 'Invalid source coordinates');
}));
test('input mutation during analysis invalidates metrics', () => fixture(async ({ dir, storage }) => {
  const original = storage.execute;
  storage.execute = async (...values) => { await original(...values); await fs.writeFile(path.join(dir, 'reference.sdf'), 'changed'); };
  await assert.rejects(compare('docking', 'fixture-key', args, storage), /Input changed/);
}));
test('structure mapping is passed unchanged to the existing helper', () => fixture(async ({ storage }) => {
  const original = storage.execute;
  storage.execute = async (...values) => {
    const argv = values[1];
    assert.deepEqual(argv.slice(argv.indexOf('--chain-map') + 1, argv.indexOf('--residue-map')), ['A:A', 'B:C']);
    assert.ok(argv.at(-1).endsWith('/mapping.json'));
    await original(...values);
  };
  const result = await compare('structure', 'fixture-key', { reference_file: 'reference.sdf', result_file: 'result.json',
    chain_map: ['A:A', 'B:C'], residue_mapping_file: 'mapping.json' }, storage);
  assert.equal(result.provenance.inputs.residue_mapping_file.sha256, hash('{}'));
}));
test('ambiguous sources, missing coordinate-frame confirmation or chain mapping fail before execution', () => fixture(async ({ storage }) => {
  await assert.rejects(compare('docking', 'fixture-key', { ...args, prediction_file: 'other.sdf' }, storage), /exactly one/);
  await assert.rejects(compare('docking', 'fixture-key', { ...args, same_coordinate_frame: false }, storage), /coordinate frame/);
  await assert.rejects(compare('structure', 'fixture-key', args, storage), /explicit/);
}));
test('typed aging analysis retains actual row files, hashes and exact cohort overlap counts', () => fixture(async ({ storage, retained }) => {
  storage.execute = async (_, argv) => {
    assert.equal(argv[argv.indexOf('--model') + 1], 'phenoage');
    assert.equal(argv[argv.indexOf('--coefficient-version') + 1], 'levine-2018-supplement-rounded-v1');
    const cohorts = JSON.parse(await fs.readFile(argv[argv.indexOf('--cohorts') + 1], 'utf8'));
    assert.equal(cohorts.length, 1);
    assert.ok(cohorts[0].input_file.endsWith('reference.sdf'));
    const folder = argv[argv.indexOf('--output-dir') + 1];
    await fs.writeFile(path.join(folder, 'metrics.json'), JSON.stringify({ schema: 'scientific-aging-analysis/v1',
      model_id: 'phenoage', model_version: 'levine-2018-supplement-rounded-v1', method: 'independent reference',
      evaluator_sha256: 'reference-hash', row_count: 1, rows: [{ sample_id: 'one', independent_age_years: 41.9 }],
      cohorts: [{ sample_count: 1 }], overlaps: [], all_numerical_checks_pass: true }));
    await fs.writeFile(path.join(folder, 'rows.csv'), 'sample_id,independent_age_years\none,41.9\n');
    await fs.writeFile(path.join(folder, 'report.md'), '# Actual numerical report\n');
  };
  const result = await aging('fixture-key', { model_id: 'phenoage', coefficient_version: 'levine-2018-supplement-rounded-v1',
    cohorts: [{ label: 'one', input_file: 'reference.sdf', result_file: 'result.json' }] }, storage);
  assert.equal(result.metrics.row_count, 1);
  assert.equal(result.metrics.row_count, JSON.parse(retained[result.files['metrics.json'].relative_path]).row_count);
  assert.match(result.evidence_guidance, /already a complete deterministic methods/);
  assert.equal(result.inference_submitted, false);
  assert.equal(result.provenance.inputs.cohort_0_input.sha256, hash('reference bytes'));
  assert.equal(result.files['metrics.json'].sha256, result.provenance.result_sha256);
  assert.ok(retained[result.files['rows.csv'].relative_path].toString().includes('one,41.9'));
}));
