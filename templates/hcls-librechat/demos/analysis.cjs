/* Typed workspace adapters for the already-qualified analysis helpers. */
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { execFile } = require('node:child_process');
const { promisify } = require('node:util');
const execute = promisify(execFile);
const hash = (bytes) => crypto.createHash('sha256').update(bytes).digest('hex');
const fail = (message) => Object.assign(new Error(message), { status: 400 });
const PYTHON = process.env.SCIENTIFIC_ANALYSIS_PYTHON || '/opt/scientific-client/bin/python';
const HELPERS = process.env.SCIENTIFIC_ANALYSIS_HELPERS || '/opt/bionemo';

async function compare(kind, key, args, storage) {
  if (!['docking', 'structure'].includes(kind)) throw fail('Unknown analysis method.');
  if (kind === 'docking' && args.same_coordinate_frame !== true) {
    throw fail('Confirm the reference and predictions share the unchanged receptor coordinate frame.');
  }
  if (Boolean(args.result_file) === Boolean(args.prediction_file)) {
    throw fail('Supply exactly one saved result_file or prediction_file.');
  }
  if (kind === 'structure' && (!Array.isArray(args.chain_map) || !args.chain_map.length
      || args.chain_map.length > 20 || args.chain_map.some((pair) => typeof pair !== 'string'
      || !/^[A-Za-z0-9_]+:[A-Za-z0-9_]+$/.test(pair)))) {
    throw fail('Supply explicit reference:prediction chain mappings; do not guess the biological assembly.');
  }
  const fields = ['reference_file', args.result_file ? 'result_file' : 'prediction_file'];
  if (args.residue_mapping_file) fields.push('residue_mapping_file');
  const inputs = {};
  for (const field of fields) {
    if (typeof args[field] !== 'string' || !args[field]) throw fail('Supply workspace-relative input file paths.');
    const file = await storage.workspaceGet(key, args[field]);
    if (file.size_bytes > 64 * 1024 * 1024) throw fail('Analysis input exceeds the bounded 64 MiB helper limit.');
    const bytes = await fs.readFile(file.absolute);
    inputs[field] = { ...file, sha256: hash(bytes), size_bytes: bytes.length };
  }
  const helper = path.join(HELPERS, kind === 'docking' ? 'molecule-analysis.py' : 'structure-analysis.py');
  const helperHash = hash(await fs.readFile(helper));
  const temporary = await fs.mkdtemp(path.join(os.tmpdir(), 'scientific-analysis-'));
  try {
    const argv = [helper, '--reference', inputs.reference_file.absolute,
      args.result_file ? '--result' : '--prediction', inputs[fields[1]].absolute];
    if (kind === 'docking') {
      argv.push('--same-coordinate-frame', '--output', path.join(temporary, 'metrics.json'));
      const queries = args.threshold_queries || [];
      if (!Array.isArray(queries) || queries.length > 20 || queries.some((query) =>
        !Number.isFinite(query.confidence_above) || !Number.isFinite(query.rmsd_below_angstrom) || query.rmsd_below_angstrom <= 0)) {
        throw fail('Threshold queries must name finite confidence_above and positive rmsd_below_angstrom values.');
      }
      for (const query of queries) argv.push('--threshold-query', String(query.confidence_above), String(query.rmsd_below_angstrom));
    }
    else {
      if (args.structure_index !== undefined && (!Number.isInteger(args.structure_index) || args.structure_index < 0)) {
        throw fail('structure_index must identify an existing nonnegative result index.');
      }
      argv.push('--output-dir', temporary, '--structure-index', String(args.structure_index || 0), '--chain-map', ...args.chain_map);
      if (inputs.residue_mapping_file) argv.push('--residue-map', inputs.residue_mapping_file.absolute);
    }
    let diagnostic = '';
    try { await (storage.execute || execute)(PYTHON, argv, { timeout: 120000, maxBuffer: 2 * 1024 * 1024 }); }
    catch (error) {
      // The docking helper deliberately exits2 for chemically non-comparable
      // poses after writing a valid report. All other failures remain failures.
      if (kind !== 'docking' || error.code !== 2) {
        diagnostic = String(error.stderr || error.message).slice(-4000);
        const workspace_file = await storage.retainWorkspaceBytes(key,
          `.scientific-analysis/failures/${hash(diagnostic)}/diagnostic.txt`, Buffer.from(diagnostic));
        throw fail(`Analysis helper failed; no scientific metrics accepted. Read ${workspace_file.relative_path || 'the retained diagnostic'}.`);
      }
    }
    for (const file of Object.values(inputs)) {
      if (hash(await fs.readFile(file.absolute)) !== file.sha256) throw fail('Input changed during analysis; no metrics accepted.');
    }
    const metricsBytes = await fs.readFile(path.join(temporary, 'metrics.json'));
    const metrics = JSON.parse(metricsBytes);
    const prefix = `.scientific-analysis/${kind}/${helperHash}/${hash(metricsBytes)}`;
    const files = {};
    for (const name of await fs.readdir(temporary)) {
      if (!/^(metrics\.json|residue-mapping\.json|prediction\.(pdb|cif)|methods\.md|report\.md|rows\.csv)$/.test(name)) continue;
      files[name] = await storage.retainWorkspaceBytes(key, `${prefix}/${name}`, await fs.readFile(path.join(temporary, name)));
    }
    const provenance = { helper: path.basename(helper), helper_sha256: helperHash,
      inputs: Object.fromEntries(Object.entries(inputs).map(([field, file]) => [field,
        { workspace_path: file.normalized, size_bytes: file.size_bytes, sha256: file.sha256 }])),
      method: kind === 'docking' ? metrics.method : 'Explicit chain/residue mapping; fitted C-alpha RMSD and mapped-residue contacts, not DockQ.',
      result_sha256: hash(metricsBytes), inference_submitted: false };
    files['provenance.json'] = await storage.retainWorkspaceBytes(key, `${prefix}/provenance.json`, Buffer.from(JSON.stringify(provenance, null, 2)));
    const summary = kind === 'docking' ? {
      schema: metrics.schema, method: metrics.method,
      requested_pose_count: metrics.requested_pose_count, comparable_pose_count: metrics.comparable_pose_count,
      all_poses_comparable: metrics.all_poses_comparable,
      top_rank_pose_rmsd_angstrom: metrics.top_rank_pose_rmsd_angstrom,
      best_comparable_pose_rmsd_angstrom: metrics.best_comparable_pose_rmsd_angstrom,
      rank_facts: metrics.rank_facts, threshold_counts: metrics.threshold_counts,
      poses: metrics.poses.map(({ rank, status, reason, pose_rmsd_angstrom, model_confidence_not_reference_accuracy }) =>
        ({ rank, status, reason, pose_rmsd_angstrom, model_confidence_not_reference_accuracy })),
      limitations: metrics.limitations, rdkit_version: metrics.rdkit_version, numpy_version: metrics.numpy_version,
    } : metrics;
    return { analysis_completed: true, inference_submitted: false, metrics: summary, provenance,
      files, evidence_guidance: 'Use these saved deterministic metric values in the final table. Docking report.md and rows.csv are already rendered from exact rank_facts: best/worst RMSD and highest/lowest confidence are distinct. Do not infer correlation from extrema or round before threshold comparisons; request threshold_queries for explicit descriptive counts, not default success criteria. Do not substitute a newly written calculator. Model confidence, reference agreement, service wall time and GPU occupancy are different quantities.' };
  } finally { await fs.rm(temporary, { recursive: true, force: true }); }
}

async function aging(key, args, storage) {
  if (!['phenoage', 'altumage'].includes(args.model_id)
      || !Array.isArray(args.cohorts) || !args.cohorts.length || args.cohorts.length > 8) {
    throw fail('Choose an aging model and one to eight explicitly labelled input/result file pairs.');
  }
  const inputs = {};
  const get = async (field, relative) => {
    if (typeof relative !== 'string' || !relative) throw fail('Supply existing workspace-relative file paths.');
    const file = await storage.workspaceGet(key, relative);
    if (file.size_bytes > 64 * 1024 * 1024) throw fail('Analysis input exceeds the bounded 64 MiB helper limit.');
    const bytes = await fs.readFile(file.absolute);
    inputs[field] = { ...file, sha256: hash(bytes), size_bytes: bytes.length };
    return file.absolute;
  };
  const cohorts = [];
  for (const [index, cohort] of args.cohorts.entries()) {
    cohorts.push({ label: cohort.label,
      input_file: await get(`cohort_${index}_input`, cohort.input_file),
      result_file: await get(`cohort_${index}_result`, cohort.result_file) });
  }
  const ages = args.reference_ages_file ? await get('reference_ages', args.reference_ages_file) : undefined;
  const helper = path.join(HELPERS, 'aging-analysis.py');
  const helperHash = hash(await fs.readFile(helper));
  const temporary = await fs.mkdtemp(path.join(os.tmpdir(), 'scientific-aging-analysis-'));
  try {
    const cohortPath = path.join(temporary, 'cohorts.json');
    await fs.writeFile(cohortPath, JSON.stringify(cohorts));
    const argv = [helper, '--model', args.model_id, '--cohorts', cohortPath, '--output-dir', temporary];
    if (args.coefficient_version) argv.push('--coefficient-version', args.coefficient_version);
    if (ages) argv.push('--reference-ages', ages);
    try { await (storage.execute || execute)(PYTHON, argv, { timeout: 120000, maxBuffer: 2 * 1024 * 1024 }); }
    catch (error) {
      const diagnostic = String(error.stderr || error.message).slice(-4000);
      const retained = await storage.retainWorkspaceBytes(key,
        `.scientific-analysis/failures/${hash(diagnostic)}/diagnostic.txt`, Buffer.from(diagnostic));
      throw fail(`Independent aging analysis failed; no metrics accepted. Read ${retained.relative_path || 'the retained diagnostic'}.`);
    }
    for (const file of Object.values(inputs)) {
      if (hash(await fs.readFile(file.absolute)) !== file.sha256) throw fail('Input changed during analysis; no metrics accepted.');
    }
    const bytes = await fs.readFile(path.join(temporary, 'metrics.json'));
    const metrics = JSON.parse(bytes);
    const prefix = `.scientific-analysis/aging/${helperHash}/${hash(bytes)}`;
    const files = {};
    for (const name of ['metrics.json', 'rows.csv', 'report.md']) {
      files[name] = await storage.retainWorkspaceBytes(key, `${prefix}/${name}`, await fs.readFile(path.join(temporary, name)));
    }
    const provenance = { helper: 'aging-analysis.py', helper_sha256: helperHash,
      evaluator_sha256: metrics.evaluator_sha256, method: metrics.method,
      inputs: Object.fromEntries(Object.entries(inputs).map(([field, file]) => [field,
        { workspace_path: file.normalized, size_bytes: file.size_bytes, sha256: file.sha256 }])),
      result_sha256: hash(bytes), inference_submitted: false };
    files['provenance.json'] = await storage.retainWorkspaceBytes(key, `${prefix}/provenance.json`, Buffer.from(JSON.stringify(provenance, null, 2)));
    return { analysis_completed: true, inference_submitted: false, files, provenance,
      metrics: { schema: metrics.schema, model_id: metrics.model_id, model_version: metrics.model_version,
        all_numerical_checks_pass: metrics.all_numerical_checks_pass, cohorts: metrics.cohorts,
        row_count: metrics.row_count,
        overlaps: metrics.overlaps.map((pair) => ({ ...pair, pairs: pair.pairs.slice(0, 20),
          full_pair_count: pair.pairs.length, complete_rows_in: files['metrics.json'].relative_path })),
        limitations: metrics.limitations },
      evidence_guidance: 'The retained report.md is already a complete deterministic methods/limitations report; reuse it and rows.csv instead of requiring a new combined script. Summary row_count is also present in metrics.json; cohorts use sample_count, overlaps use common_sample_count. Exact sample overlap is not total cohort size. Numerical agreement, age-label error, biological validity and clinical utility are distinct. Do not invent another network, change coefficient versions to force agreement, or infer the cause of a historical script error from a generic limitation.' };
  } finally { await fs.rm(temporary, { recursive: true, force: true }); }
}

module.exports = { compare, aging };
