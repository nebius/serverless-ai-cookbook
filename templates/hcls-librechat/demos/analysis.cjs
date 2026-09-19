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

function outputPrefix(args, fallback) {
  if (args.output_directory === undefined) return fallback;
  const value = args.output_directory;
  if (typeof value !== 'string' || !value.trim() || value.length > 1000 || path.isAbsolute(value)
      || value.includes('\0') || value.split('/').some((part) => part === '..')) {
    throw fail('output_directory must be a nonempty workspace-relative directory. Existing different files are never overwritten.');
  }
  return value.replace(/\/+$/, '');
}

async function compare(kind, key, args, storage) {
  outputPrefix(args, '');
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
    const prefix = outputPrefix(args, `.scientific-analysis/${kind}/${helperHash}/${hash(metricsBytes)}`);
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

async function dockingBatch(key, args, storage) {
  outputPrefix(args, '');
  if (args.same_coordinate_frame !== true || !Array.isArray(args.runs) || !args.runs.length || args.runs.length > 16) {
    throw fail('Supply one to sixteen saved runs and explicitly confirm their shared receptor coordinate frames.');
  }
  const ids = args.runs.map((run) => run.run_id);
  if (ids.some((id) => typeof id !== 'string' || !id.trim() || id.length > 128) || new Set(ids).size !== ids.length) {
    throw fail('Every run needs a distinct nonempty run_id of at most128 characters.');
  }
  const inputs = {};
  const runs = [];
  for (const [index, run] of args.runs.entries()) {
    if (Boolean(run.result_file) === Boolean(run.prediction_file)) throw fail('Each run needs exactly one result_file or prediction_file.');
    const saved = { run_id: run.run_id, group_id: run.group_id };
    for (const field of ['reference_file', run.result_file ? 'result_file' : 'prediction_file']) {
      if (typeof run[field] !== 'string' || !run[field]) throw fail('Supply actual workspace-relative files.');
      const file = await storage.workspaceGet(key, run[field]);
      if (file.size_bytes > 64 * 1024 * 1024) throw fail('Analysis input exceeds the bounded 64 MiB helper limit.');
      const bytes = await fs.readFile(file.absolute);
      inputs[`${index}_${field}`] = { ...file, sha256: hash(bytes), size_bytes: bytes.length };
      saved[field] = file.absolute;
    }
    runs.push(saved);
  }
  const queries = args.threshold_queries || [];
  if (!Array.isArray(queries) || queries.length > 20 || queries.some((query) =>
    !Number.isFinite(query.confidence_above) || !Number.isFinite(query.rmsd_below_angstrom) || query.rmsd_below_angstrom <= 0)) {
    throw fail('Threshold queries need finite confidence_above and positive rmsd_below_angstrom.');
  }
  const helper = path.join(HELPERS, 'molecule-analysis.py');
  const helperHash = hash(await fs.readFile(helper));
  const temporary = await fs.mkdtemp(path.join(os.tmpdir(), 'scientific-docking-batch-'));
  try {
    const manifest = path.join(temporary, 'runs.json');
    await fs.writeFile(manifest, JSON.stringify(runs));
    const argv = [helper, '--runs', manifest, '--same-coordinate-frame', '--output', path.join(temporary, 'metrics.json')];
    for (const query of queries) argv.push('--threshold-query', String(query.confidence_above), String(query.rmsd_below_angstrom));
    // Keep analysis and response publication inside the existing60s MCP call.
    try { await (storage.execute || execute)(PYTHON, argv, { timeout: 50000, maxBuffer: 2 * 1024 * 1024 }); }
    catch (error) {
      if (error.code !== 2) {
        const diagnostic = String(error.stderr || error.message).slice(-4000);
        const retained = await storage.retainWorkspaceBytes(key, `.scientific-analysis/failures/${hash(diagnostic)}/diagnostic.txt`, Buffer.from(diagnostic));
        throw fail(`Multi-run docking analysis failed; no metrics accepted. Read ${retained.relative_path}.`);
      }
    }
    for (const file of Object.values(inputs)) {
      if (hash(await fs.readFile(file.absolute)) !== file.sha256) throw fail('Input changed during analysis; no metrics accepted.');
    }
    const bytes = await fs.readFile(path.join(temporary, 'metrics.json'));
    const metrics = JSON.parse(bytes);
    const prefix = outputPrefix(args, `.scientific-analysis/docking-batch/${helperHash}/${hash(bytes)}`);
    const files = {};
    for (const name of ['metrics.json', 'rows.csv', 'report.md']) {
      const content = await fs.readFile(path.join(temporary, name));
      files[name] = { ...await storage.retainWorkspaceBytes(key, `${prefix}/${name}`, content),
        size_bytes: content.length, sha256: hash(content) };
    }
    const provenance = { helper: 'molecule-analysis.py', helper_sha256: helperHash, method: metrics.method,
      inputs: Object.fromEntries(Object.entries(inputs).map(([field, file]) => [field,
        { workspace_path: file.normalized, size_bytes: file.size_bytes, sha256: file.sha256 }])),
      result_sha256: hash(bytes), inference_submitted: false };
    files['provenance.json'] = await storage.retainWorkspaceBytes(key, `${prefix}/provenance.json`, Buffer.from(JSON.stringify(provenance, null, 2)));
    return { analysis_completed: true, inference_submitted: false, files, provenance,
      metrics: { schema: metrics.schema, method: metrics.method, summary: metrics.summary, groups: metrics.groups,
        all_poses_comparable: metrics.all_poses_comparable,
        runs: metrics.runs.map((run) => ({ run_id: run.run_id, group_id: run.group_id,
          metrics: { rank_facts: run.metrics.rank_facts, requested_pose_count: run.metrics.requested_pose_count,
            comparable_pose_count: run.metrics.comparable_pose_count } })), limitations: metrics.limitations },
      evidence_guidance: 'Reuse report.md and rows.csv as the complete cross-run docking deliverable. Every group has explicit run, all-pose and top-ranked-pose denominators; never substitute one for another. Threshold counts are unrounded descriptive queries, not clinical/scientific pass criteria. Highest-confidence/best-RMSD overlap includes ties. File size_bytes is the exact UTF-8 byte count, not a character count. Optional interpretation must agree with these saved aggregates and preserve non-comparable poses.' };
  } finally { await fs.rm(temporary, { recursive: true, force: true }); }
}

async function aging(key, args, storage) {
  outputPrefix(args, '');
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
    const prefix = outputPrefix(args, `.scientific-analysis/aging/${helperHash}/${hash(bytes)}`);
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

async function assembleReport(key, args, storage) {
  if (!args.output_directory) throw fail('Choose a new workspace-relative report output_directory.');
  const prefix = outputPrefix(args, '');
  if (!Array.isArray(args.sections) || !args.sections.length || args.sections.length > 16) throw fail('Choose one to sixteen existing report sections.');
  const sources = [];
  for (const section of args.sections) {
    if (!['markdown', 'csv'].includes(section.format)) throw fail('Section format must be markdown or csv.');
    const file = await storage.workspaceGet(key, section.file);
    if (file.size_bytes > 64 * 1024 * 1024) throw fail('Report section exceeds64 MiB.');
    const bytes = await fs.readFile(file.absolute);
    sources.push({ ...file, sha256: hash(bytes), size_bytes: bytes.length, title: section.title, format: section.format });
  }
  const helper = path.join(HELPERS, 'report-assembly.py');
  const temporary = await fs.mkdtemp(path.join(os.tmpdir(), 'scientific-report-'));
  try {
    const manifest = path.join(temporary, 'manifest.json');
    await fs.writeFile(manifest, JSON.stringify({ title: args.title,
      sections: sources.map((source) => ({ title: source.title, format: source.format, file: source.absolute })) }));
    try { await (storage.execute || execute)(PYTHON, [helper, '--manifest', manifest, '--output-dir', temporary],
      { timeout: 50000, maxBuffer: 65536 }); }
    catch (error) { throw fail(`Report assembly failed; no scientific validation claimed: ${String(error.stderr || error.message).slice(-2000)}`); }
    for (const file of sources) {
      if (hash(await fs.readFile(file.absolute)) !== file.sha256) throw fail('Report source changed during assembly; no document accepted.');
    }
    const bytes = await fs.readFile(path.join(temporary, 'report.md'));
    const provenance = JSON.parse(await fs.readFile(path.join(temporary, 'provenance.json')));
    if (provenance.report_sha256 !== hash(bytes) || provenance.report_size_bytes !== bytes.length) throw fail('Report byte verification failed.');
    provenance.helper_sha256 = hash(await fs.readFile(helper));
    provenance.workspace_sources = sources.map((source) => ({ file: source.normalized, sha256: source.sha256, size_bytes: source.size_bytes }));
    const files = { 'report.md': await storage.retainWorkspaceBytes(key, `${prefix}/report.md`, bytes),
      'provenance.json': await storage.retainWorkspaceBytes(key, `${prefix}/provenance.json`, Buffer.from(JSON.stringify(provenance, null, 2))) };
    return { document_assembled: true, inference_submitted: false, scientific_claims_validated: false,
      files, sections: provenance.sections.map(({ title, format, row_count, column_count, source_sha256 }) =>
        ({ title, format, row_count, column_count, source_sha256 })),
      evidence_guidance: 'Markdown sections are preserved verbatim and CSV values rendered in original order with exact checked column widths. Use this actual report rather than rewriting its numerical tables. File lineage and document construction are verified; scientific correctness and optional narrative claims still need review.' };
  } finally { await fs.rm(temporary, { recursive: true, force: true }); }
}

module.exports = { compare, dockingBatch, aging, assembleReport };
