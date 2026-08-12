import { InputError } from "./errors.mjs";

export const LIMITS = Object.freeze({
  requestBytes: 2_500_000,
  responseBytes: 20_000_000,
  pdbBytes: 2_000_000,
  sequenceLength: 4_096,
  alignmentBytes: 4_000_000,
  maxArtifactsPerRun: 100,
});

const PROTEIN = /^[ABCDEFGHIKLMNPQRSTVWXYZOU*\-]+$/iu;
const DNA = /^[ACGTN]+$/iu;
const CHAIN = /^[A-Za-z0-9]{1,4}$/u;
const HOTSPOT = /^[A-Za-z0-9][1-9][0-9]{0,5}$/u;
const CONTIG = /^[A-Za-z0-9\-\/ .]+$/u;
const AMINO_ACID = /^[ACDEFGHIKLMNPQRSTVWY]$/u;

function assertObject(value, label = "request") {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new InputError(`${label} must be an object`);
  }
  return value;
}

function onlyKeys(value, allowed, label = "request") {
  const unknown = Object.keys(value).filter((key) => !allowed.includes(key));
  if (unknown.length) throw new InputError(`${label} contains unsupported fields: ${unknown.join(", ")}`);
}

function required(value, keys, label = "request") {
  const missing = keys.filter((key) => value[key] === undefined || value[key] === null || value[key] === "");
  if (missing.length) throw new InputError(`${label} is missing required fields: ${missing.join(", ")}`);
}

function string(value, label, { min = 0, max = 10_000, pattern } = {}) {
  if (typeof value !== "string" || value.length < min || value.length > max) {
    throw new InputError(`${label} must be a string between ${min} and ${max} characters`);
  }
  if (pattern && !pattern.test(value)) throw new InputError(`${label} contains unsupported characters`);
  return value;
}

function number(value, label, { min = -Infinity, max = Infinity, integer = false } = {}) {
  if (typeof value !== "number" || !Number.isFinite(value) || value < min || value > max || (integer && !Number.isInteger(value))) {
    throw new InputError(`${label} must be ${integer ? "an integer" : "a number"} between ${min} and ${max}`);
  }
  return value;
}

function bool(value, label) {
  if (typeof value !== "boolean") throw new InputError(`${label} must be a boolean`);
  return value;
}

function array(value, label, { min = 0, max = 100 } = {}) {
  if (!Array.isArray(value) || value.length < min || value.length > max) {
    throw new InputError(`${label} must contain between ${min} and ${max} items`);
  }
  return value;
}

function enumeration(value, label, choices) {
  if (!choices.includes(value)) throw new InputError(`${label} must be one of: ${choices.join(", ")}`);
  return value;
}

function optional(value, key, validator) {
  if (value[key] !== undefined && value[key] !== null) validator(value[key], key);
}

function inlinePdb(value, label = "input_pdb") {
  string(value, label, { min: 20, max: LIMITS.pdbBytes });
  if (!/(?:^|\n)(?:ATOM  |HETATM|CRYST1)/u.test(value)) {
    throw new InputError(`${label} must contain inline PDB records, not a file path`);
  }
}

function proteinSequence(value, label = "sequence") {
  string(value, label, { min: 2, max: LIMITS.sequenceLength, pattern: PROTEIN });
}

function safeGenerationMask(value, label = "safe_notation") {
  if (typeof value !== "string" || value.length < 1 || value.length > 32) {
    throw new InputError(`${label} must be a GenMol de novo SAFE mask such as [*{5-10}], not a label or SMILES`);
  }
  const match = value.match(/^\[\*\{([1-9][0-9]{0,2})-([1-9][0-9]{0,2})\}\]$/u);
  if (!match) throw new InputError(`${label} must be a GenMol de novo SAFE mask such as [*{5-10}], not a label or SMILES`);
  const minimum = Number(match[1]);
  const maximum = Number(match[2]);
  if (minimum > maximum || maximum > 100) throw new InputError(`${label} fragment bounds must increase and stay between 1 and 100`);
}

function assertRequestSize(value) {
  const bytes = Buffer.byteLength(JSON.stringify(value), "utf8");
  if (bytes > LIMITS.requestBytes) throw new InputError(`request exceeds ${LIMITS.requestBytes} bytes`);
}

function final(value) {
  assertRequestSize(value);
  return structuredClone(value);
}

export function validateBoltz2(input) {
  const value = assertObject(input);
  onlyKeys(value, ["polymers", "ligands", "constraints", "recycling_steps", "sampling_steps", "diffusion_samples", "step_scale", "output_format"]);
  required(value, ["polymers"]);
  array(value.polymers, "polymers", { min: 1, max: 12 }).forEach((polymer, index) => {
    assertObject(polymer, `polymers[${index}]`);
    onlyKeys(polymer, ["id", "molecule_type", "sequence", "msa"], `polymers[${index}]`);
    required(polymer, ["id", "molecule_type", "sequence"], `polymers[${index}]`);
    string(polymer.id, `polymers[${index}].id`, { min: 1, max: 8, pattern: CHAIN });
    enumeration(polymer.molecule_type, `polymers[${index}].molecule_type`, ["protein", "dna", "rna"]);
    if (polymer.molecule_type === "protein") proteinSequence(polymer.sequence, `polymers[${index}].sequence`);
    else string(polymer.sequence, `polymers[${index}].sequence`, { min: 2, max: LIMITS.sequenceLength, pattern: /^[ACGTUN]+$/iu });
    optional(polymer, "msa", (item) => assertObject(item, `polymers[${index}].msa`));
  });
  if (value.ligands !== undefined) array(value.ligands, "ligands", { max: 20 }).forEach((ligand, index) => {
    assertObject(ligand, `ligands[${index}]`);
    onlyKeys(ligand, ["id", "smiles", "ccd", "predict_affinity"], `ligands[${index}]`);
    required(ligand, ["id"], `ligands[${index}]`);
    string(ligand.id, `ligands[${index}].id`, { min: 1, max: 8, pattern: CHAIN });
    if (Boolean(ligand.smiles) === Boolean(ligand.ccd)) throw new InputError(`ligands[${index}] must set exactly one of smiles or ccd`);
    optional(ligand, "smiles", (item) => string(item, `ligands[${index}].smiles`, { min: 1, max: 2_048 }));
    optional(ligand, "ccd", (item) => string(item, `ligands[${index}].ccd`, { min: 1, max: 16, pattern: /^[A-Za-z0-9]+$/u }));
    optional(ligand, "predict_affinity", (item) => bool(item, `ligands[${index}].predict_affinity`));
  });
  optional(value, "recycling_steps", (item) => number(item, "recycling_steps", { min: 1, max: 10, integer: true }));
  optional(value, "sampling_steps", (item) => number(item, "sampling_steps", { min: 10, max: 200, integer: true }));
  optional(value, "diffusion_samples", (item) => number(item, "diffusion_samples", { min: 1, max: 3, integer: true }));
  optional(value, "step_scale", (item) => number(item, "step_scale", { min: 0.5, max: 5 }));
  optional(value, "output_format", (item) => enumeration(item, "output_format", ["mmcif", "pdb"]));
  if (value.constraints !== undefined) array(value.constraints, "constraints", { max: 64 });
  return final(value);
}

export function validateDiffDock(input) {
  const value = assertObject(input);
  onlyKeys(value, ["protein", "ligand", "ligand_file_type", "num_poses", "time_divisions", "steps", "save_trajectory"]);
  required(value, ["protein", "ligand"]);
  inlinePdb(value.protein, "protein");
  value.protein = value.protein.split(/\r?\n/u).filter((line) => line.startsWith("ATOM")).join("\n");
  if (!value.protein) throw new InputError("protein must contain at least one PDB ATOM record");
  value.protein += "\n";
  string(value.ligand, "ligand", { min: 1, max: 200_000 });
  optional(value, "ligand_file_type", (item) => enumeration(item, "ligand_file_type", ["txt", "sdf", "mol2"]));
  optional(value, "num_poses", (item) => number(item, "num_poses", { min: 1, max: 20, integer: true }));
  optional(value, "time_divisions", (item) => number(item, "time_divisions", { min: 1, max: 20, integer: true }));
  optional(value, "steps", (item) => number(item, "steps", { min: 1, max: 18, integer: true }));
  optional(value, "save_trajectory", (item) => {
    bool(item, "save_trajectory");
    if (item) throw new InputError("save_trajectory must be false for bounded event requests");
  });
  return final(value);
}

export function validateEvo2(input) {
  const value = assertObject(input);
  onlyKeys(value, ["sequence", "num_tokens", "temperature", "top_k", "top_p", "random_seed"]);
  required(value, ["sequence"]);
  string(value.sequence, "sequence", { min: 1, max: LIMITS.sequenceLength, pattern: DNA });
  optional(value, "num_tokens", (item) => number(item, "num_tokens", { min: 1, max: 512, integer: true }));
  optional(value, "temperature", (item) => number(item, "temperature", { min: 0, max: 1.3 }));
  optional(value, "top_k", (item) => number(item, "top_k", { min: 0, max: 6, integer: true }));
  optional(value, "top_p", (item) => number(item, "top_p", { min: 0, max: 1 }));
  optional(value, "random_seed", (item) => number(item, "random_seed", { min: 0, max: 2_147_483_647, integer: true }));
  return final(value);
}

export function validateGenMol(input) {
  const value = assertObject(input);
  onlyKeys(value, ["smiles", "num_molecules", "scoring", "unique", "temperature", "noise", "step_size"]);
  required(value, ["smiles"]);
  string(value.smiles, "smiles", { min: 1, max: 2_048 });
  optional(value, "num_molecules", (item) => number(item, "num_molecules", { min: 1, max: 100, integer: true }));
  optional(value, "scoring", (item) => enumeration(item, "scoring", ["QED", "LogP"]));
  optional(value, "unique", (item) => bool(item, "unique"));
  for (const key of ["temperature", "noise"]) optional(value, key, (item) => {
    string(item, key, { min: 1, max: 8, pattern: /^(?:0(?:\.\d+)?|1(?:\.0+)?)$/u });
  });
  optional(value, "step_size", (item) => number(item, "step_size", { min: 1, max: 10, integer: true }));
  return final(value);
}

export function validateMolMim(input) {
  const value = assertObject(input);
  onlyKeys(value, ["smi", "algorithm", "num_molecules", "num_iterations", "property_name", "minimize", "min_similarity", "particles", "radius"]);
  required(value, ["smi"]);
  string(value.smi, "smi", { min: 1, max: 2_048 });
  optional(value, "algorithm", (item) => enumeration(item, "algorithm", ["CMA-ES", "none"]));
  optional(value, "num_molecules", (item) => number(item, "num_molecules", { min: 1, max: 100, integer: true }));
  optional(value, "num_iterations", (item) => number(item, "num_iterations", { min: 1, max: 100, integer: true }));
  optional(value, "property_name", (item) => enumeration(item, "property_name", ["QED", "plogP"]));
  optional(value, "minimize", (item) => bool(item, "minimize"));
  optional(value, "min_similarity", (item) => number(item, "min_similarity", { min: 0, max: 1 }));
  optional(value, "particles", (item) => number(item, "particles", { min: 2, max: 100, integer: true }));
  optional(value, "radius", (item) => number(item, "radius", { min: 0, max: 2 }));
  return final(value);
}

export function validateMsaSearch(input) {
  const value = assertObject(input);
  onlyKeys(value, ["sequence", "sequences", "databases", "e_value", "iterations", "max_msa_sequences", "output_alignment_formats"]);
  if (Boolean(value.sequence) === Boolean(value.sequences)) throw new InputError("set exactly one of sequence or sequences");
  if (value.sequence) proteinSequence(value.sequence);
  if (value.sequences) array(value.sequences, "sequences", { min: 2, max: 8 }).forEach((item, index) => proteinSequence(item, `sequences[${index}]`));
  optional(value, "databases", (items) => array(items, "databases", { min: 1, max: 3 }).forEach((item) => enumeration(item, "databases", ["Uniref30_2302", "colabfold_envdb_202108", "all"])));
  optional(value, "e_value", (item) => number(item, "e_value", { min: 1e-20, max: 10 }));
  optional(value, "iterations", (item) => number(item, "iterations", { min: 1, max: 5, integer: true }));
  optional(value, "max_msa_sequences", (item) => number(item, "max_msa_sequences", { min: 1, max: 500, integer: true }));
  optional(value, "output_alignment_formats", (items) => array(items, "output_alignment_formats", { min: 1, max: 2 }).forEach((item) => enumeration(item, "output_alignment_formats", ["a3m", "fasta"])));
  return final(value);
}

export function validateOpenFold2(input) {
  const value = assertObject(input);
  onlyKeys(value, ["sequence", "input_id", "alignments", "templates", "selected_models", "relax"]);
  required(value, ["sequence"]);
  string(value.sequence, "sequence", { min: 2, max: 1_000, pattern: PROTEIN });
  optional(value, "input_id", (item) => string(item, "input_id", { min: 1, max: 128, pattern: /^[A-Za-z0-9._-]+$/u }));
  optional(value, "alignments", (item) => assertObject(item, "alignments"));
  optional(value, "templates", (items) => array(items, "templates", { max: 20 }));
  optional(value, "selected_models", (items) => array(items, "selected_models", { min: 1, max: 2 }).forEach((item) => number(item, "selected_models", { min: 1, max: 5, integer: true })));
  optional(value, "relax", (item) => bool(item, "relax"));
  return final(value);
}

function validateOpenFoldMolecule(molecule, index) {
  assertObject(molecule, `molecules[${index}]`);
  onlyKeys(molecule, ["type", "sequence", "smiles", "ccd", "diffusion_samples", "msa", "paired_msa"], `molecules[${index}]`);
  required(molecule, ["type"], `molecules[${index}]`);
  enumeration(molecule.type, `molecules[${index}].type`, ["protein", "dna", "rna", "ligand"]);
  if (molecule.type === "ligand") {
    if (Boolean(molecule.smiles) === Boolean(molecule.ccd)) throw new InputError(`molecules[${index}] ligand must set exactly one of smiles or ccd`);
    optional(molecule, "smiles", (item) => string(item, `molecules[${index}].smiles`, { min: 1, max: 2_048 }));
    optional(molecule, "ccd", (item) => string(item, `molecules[${index}].ccd`, { min: 1, max: 16, pattern: /^[A-Za-z0-9]+$/u }));
  } else {
    required(molecule, ["sequence"], `molecules[${index}]`);
    if (molecule.type === "protein") proteinSequence(molecule.sequence, `molecules[${index}].sequence`);
    else string(molecule.sequence, `molecules[${index}].sequence`, { min: 2, max: LIMITS.sequenceLength, pattern: /^[ACGTUN]+$/iu });
  }
  optional(molecule, "diffusion_samples", (item) => number(item, `molecules[${index}].diffusion_samples`, { min: 1, max: 3, integer: true }));
  optional(molecule, "msa", (item) => assertObject(item, `molecules[${index}].msa`));
  optional(molecule, "paired_msa", (item) => assertObject(item, `molecules[${index}].paired_msa`));
}

export function validateOpenFold3(input) {
  const value = assertObject(input);
  onlyKeys(value, ["inputs"]);
  required(value, ["inputs"]);
  array(value.inputs, "inputs", { min: 1, max: 1 }).forEach((entry, inputIndex) => {
    assertObject(entry, `inputs[${inputIndex}]`);
    onlyKeys(entry, ["input_id", "output_format", "molecules"], `inputs[${inputIndex}]`);
    required(entry, ["input_id", "molecules"], `inputs[${inputIndex}]`);
    string(entry.input_id, `inputs[${inputIndex}].input_id`, { min: 1, max: 128, pattern: /^[A-Za-z0-9._-]+$/u });
    optional(entry, "output_format", (item) => enumeration(item, "output_format", ["pdb", "cif"]));
    array(entry.molecules, `inputs[${inputIndex}].molecules`, { min: 1, max: 32 }).forEach(validateOpenFoldMolecule);
  });
  return final(value);
}

export function validateProteinMpnn(input) {
  const value = assertObject(input);
  onlyKeys(value, ["input_pdb", "input_pdb_chains", "ca_only", "use_soluble_model", "random_seed", "num_seq_per_target", "sampling_temp", "fixed_positions_jsonl", "omit_AAs"]);
  required(value, ["input_pdb"]);
  inlinePdb(value.input_pdb);
  optional(value, "input_pdb_chains", (items) => array(items, "input_pdb_chains", { min: 1, max: 16 }).forEach((item) => string(item, "input_pdb_chains", { min: 1, max: 4, pattern: CHAIN })));
  optional(value, "ca_only", (item) => bool(item, "ca_only"));
  optional(value, "use_soluble_model", (item) => bool(item, "use_soluble_model"));
  optional(value, "random_seed", (item) => number(item, "random_seed", { min: 0, max: 2_147_483_647, integer: true }));
  optional(value, "num_seq_per_target", (item) => number(item, "num_seq_per_target", { min: 1, max: 20, integer: true }));
  optional(value, "sampling_temp", (items) => array(items, "sampling_temp", { min: 1, max: 4 }).forEach((item) => number(item, "sampling_temp", { min: 0, max: 1 })));
  optional(value, "fixed_positions_jsonl", (item) => string(item, "fixed_positions_jsonl", { max: 200_000 }));
  optional(value, "omit_AAs", (items) => array(items, "omit_AAs", { max: 20 }).forEach((item) => string(item, "omit_AAs", { min: 1, max: 1, pattern: AMINO_ACID })));
  return final(value);
}

export function validateRfDiffusion(input) {
  const value = assertObject(input);
  onlyKeys(value, ["input_pdb", "contigs", "hotspot_res", "diffusion_steps", "random_seed"]);
  required(value, ["input_pdb", "contigs"]);
  inlinePdb(value.input_pdb);
  string(value.contigs, "contigs", { min: 1, max: 512, pattern: CONTIG });
  optional(value, "hotspot_res", (items) => array(items, "hotspot_res", { max: 64 }).forEach((item) => string(item, "hotspot_res", { min: 2, max: 8, pattern: HOTSPOT })));
  optional(value, "diffusion_steps", (item) => number(item, "diffusion_steps", { min: 1, max: 50, integer: true }));
  optional(value, "random_seed", (item) => number(item, "random_seed", { min: 0, max: 2_147_483_647, integer: true }));
  return final(value);
}

export const VALIDATORS = Object.freeze({
  boltz2: validateBoltz2,
  diffdock: validateDiffDock,
  evo2: validateEvo2,
  genmol: validateGenMol,
  molmim: validateMolMim,
  msa_search: validateMsaSearch,
  openfold2: validateOpenFold2,
  openfold3: validateOpenFold3,
  proteinmpnn: validateProteinMpnn,
  rfdiffusion: validateRfDiffusion,
});

export function validateWorkflowInput(workflowId, input) {
  const value = assertObject(input);
  if (workflowId === "drug_discovery") {
    onlyKeys(value, ["protein_pdb", "protein_sequence", "safe_notation", "generated_molecules", "dock_candidates", "affinity_candidates"]);
    required(value, ["protein_pdb", "protein_sequence", "safe_notation"]);
    inlinePdb(value.protein_pdb, "protein_pdb");
    proteinSequence(value.protein_sequence, "protein_sequence");
    safeGenerationMask(value.safe_notation);
    optional(value, "generated_molecules", (item) => number(item, "generated_molecules", { min: 1, max: 20, integer: true }));
    optional(value, "dock_candidates", (item) => number(item, "dock_candidates", { min: 1, max: 5, integer: true }));
    optional(value, "affinity_candidates", (item) => number(item, "affinity_candidates", { min: 1, max: 3, integer: true }));
  } else if (workflowId === "msa_to_structure") {
    onlyKeys(value, ["sequence", "max_msa_sequences", "output_format"]);
    required(value, ["sequence"]);
    proteinSequence(value.sequence);
    optional(value, "max_msa_sequences", (item) => number(item, "max_msa_sequences", { min: 1, max: 500, integer: true }));
    optional(value, "output_format", (item) => enumeration(item, "output_format", ["pdb", "cif"]));
  } else if (workflowId === "protein_binder_design") {
    onlyKeys(value, ["target_pdb", "target_sequence", "contigs", "hotspot_res", "binder_chain", "validation_model", "sampling_temperature"]);
    required(value, ["target_pdb", "target_sequence", "contigs", "binder_chain"]);
    inlinePdb(value.target_pdb, "target_pdb");
    proteinSequence(value.target_sequence, "target_sequence");
    string(value.contigs, "contigs", { min: 1, max: 512, pattern: CONTIG });
    string(value.binder_chain, "binder_chain", { min: 1, max: 4, pattern: CHAIN });
    optional(value, "hotspot_res", (items) => array(items, "hotspot_res", { max: 64 }).forEach((item) => string(item, "hotspot_res", { min: 2, max: 8, pattern: HOTSPOT })));
    optional(value, "validation_model", (item) => enumeration(item, "validation_model", ["openfold3", "boltz2"]));
    optional(value, "sampling_temperature", (item) => number(item, "sampling_temperature", { min: 0, max: 1 }));
  } else {
    throw new InputError(`unknown workflow ${workflowId}`);
  }
  return final(value);
}

export const JSON_SCHEMAS = Object.freeze({
  boltz2: { type: "object", additionalProperties: false, required: ["polymers"], properties: { polymers: { type: "array" }, ligands: { type: "array" }, constraints: { type: "array" }, recycling_steps: { type: "integer" }, sampling_steps: { type: "integer" }, diffusion_samples: { type: "integer" }, step_scale: { type: "number" }, output_format: { type: "string", enum: ["mmcif", "pdb"] } } },
  diffdock: { type: "object", additionalProperties: false, required: ["ligand"], properties: { protein: { type: "string" }, protein_sample: { type: "string", enum: ["egfr_kinase_public"] }, ligand: { type: "string" }, ligand_file_type: { type: "string", enum: ["txt", "sdf", "mol2"] }, num_poses: { type: "integer", minimum: 1, maximum: 20 }, time_divisions: { type: "integer" }, steps: { type: "integer" }, save_trajectory: { type: "boolean", const: false } } },
  evo2: { type: "object", additionalProperties: false, required: ["sequence"], properties: { sequence: { type: "string" }, num_tokens: { type: "integer", minimum: 1, maximum: 512 }, temperature: { type: "number" }, top_k: { type: "integer" }, top_p: { type: "number" }, random_seed: { type: "integer" } } },
  genmol: { type: "object", additionalProperties: false, required: ["smiles"], properties: { smiles: { type: "string", description: "SAFE notation (upstream field name is smiles)." }, num_molecules: { type: "integer", minimum: 1, maximum: 100 }, scoring: { type: "string", enum: ["QED", "LogP"] }, unique: { type: "boolean" }, temperature: { type: "string" }, noise: { type: "string" }, step_size: { type: "integer" } } },
  molmim: { type: "object", additionalProperties: false, required: ["smi"], properties: { smi: { type: "string" }, algorithm: { type: "string", enum: ["CMA-ES", "none"] }, num_molecules: { type: "integer" }, num_iterations: { type: "integer" }, property_name: { type: "string", enum: ["QED", "plogP"] }, minimize: { type: "boolean" }, min_similarity: { type: "number" }, particles: { type: "integer" }, radius: { type: "number" } } },
  msa_search: { type: "object", additionalProperties: false, properties: { sequence: { type: "string" }, sequences: { type: "array", items: { type: "string" } }, databases: { type: "array", items: { type: "string" } }, e_value: { type: "number" }, iterations: { type: "integer" }, max_msa_sequences: { type: "integer" }, output_alignment_formats: { type: "array", items: { type: "string", enum: ["a3m", "fasta"] } } } },
  // Keep the model-facing OpenFold2 contract deliberately small. Nemotron is
  // reliable with the single required sequence, while exposing every optional
  // upstream field can make it serialize several parameters into one malformed
  // tool argument. The runtime validator still supports the full bounded
  // OpenFold2 input for direct/programmatic calls.
  openfold2: { type: "object", additionalProperties: false, required: ["sequence"], properties: { sequence: { type: "string", description: "Protein amino-acid sequence to fold." } } },
  openfold3: { type: "object", additionalProperties: false, required: ["inputs"], properties: { inputs: { type: "array", minItems: 1, maxItems: 1 } } },
  proteinmpnn: { type: "object", additionalProperties: false, properties: { input_pdb: { type: "string" }, input_pdb_sample: { type: "string", enum: ["egfr_kinase_public"] }, input_pdb_chains: { type: "array", items: { type: "string" } }, ca_only: { type: "boolean" }, use_soluble_model: { type: "boolean" }, random_seed: { type: "integer" }, num_seq_per_target: { type: "integer" }, sampling_temp: { type: "array", items: { type: "number" } }, fixed_positions_jsonl: { type: "string" }, omit_AAs: { type: "array", items: { type: "string" } } } },
  rfdiffusion: { type: "object", additionalProperties: false, required: ["contigs"], properties: { input_pdb: { type: "string" }, input_pdb_sample: { type: "string", enum: ["egfr_kinase_public"] }, contigs: { type: "string" }, hotspot_res: { type: "array", items: { type: "string" } }, diffusion_steps: { type: "integer" }, random_seed: { type: "integer" } } },
  drug_discovery: { type: "object", additionalProperties: false, required: ["safe_notation"], properties: { protein_pdb: { type: "string" }, protein_sequence: { type: "string" }, protein_sample: { type: "string", enum: ["egfr_kinase_public"], description: "Use the bundled full EGFR kinase PDB and matching 312-aa sequence; do not combine this with protein_pdb or protein_sequence." }, safe_notation: { type: "string", pattern: "^\\[\\*\\{[1-9][0-9]{0,2}-[1-9][0-9]{0,2}\\}\\]$", description: "GenMol de novo SAFE mask, for example [*{5-10}]. Never invent a label such as SAFE_1." }, generated_molecules: { type: "integer", minimum: 1, maximum: 20 }, dock_candidates: { type: "integer", minimum: 1, maximum: 5 }, affinity_candidates: { type: "integer", minimum: 1, maximum: 3 } } },
  msa_to_structure: { type: "object", additionalProperties: false, required: ["sequence"], properties: { sequence: { type: "string" }, max_msa_sequences: { type: "integer", minimum: 1, maximum: 500 }, output_format: { type: "string", enum: ["pdb", "cif"] } } },
  protein_binder_design: { type: "object", additionalProperties: false, required: ["contigs", "binder_chain"], properties: { target_pdb: { type: "string" }, target_sequence: { type: "string" }, target_sample: { type: "string", enum: ["egfr_kinase_public"] }, contigs: { type: "string" }, hotspot_res: { type: "array", items: { type: "string" } }, binder_chain: { type: "string" }, validation_model: { type: "string", enum: ["openfold3", "boltz2"] }, sampling_temperature: { type: "number" } } },
});
