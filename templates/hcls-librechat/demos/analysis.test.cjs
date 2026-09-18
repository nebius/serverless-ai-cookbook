const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
process.env.SCIENTIFIC_ANALYSIS_HELPERS = path.resolve(__dirname, '..');
const { compare } = require('./analysis.cjs');
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
