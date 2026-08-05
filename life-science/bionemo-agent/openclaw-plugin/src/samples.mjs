import { readFile } from "node:fs/promises";
import path from "node:path";
import { InputError } from "./errors.mjs";

export const SAMPLE_IDS = Object.freeze(["egfr_kinase_public"]);
const EGFR_SEQUENCE = "GEAPNQALLRILKETEFKKIKVLGSGAFGTVYKGLWIPEGEKVKIPVAIKELREATSPKANKEILDEAYVMASVDNPHVCRLLGICLTSTVQLITQLMPFGCLLDYVREHKDNIGSQYLLNWCVQIAKGMNYLEDRRLVHRDLAARNVLVKTPQHVKITDFGLAKLLGAEEKEYHAEGGKVPIKWMALESILHRIYTHQSDVWSYGVTVWELMTFGSKPYDGIPASEISSILEKGERLPQPPICTIDVYMIMVKCWMIDADSRPKFRELIIEFSKMARDPQRYLVIQGDERMHLMDEEDMDDVVDADEYLIP";

const SAMPLES = Object.freeze({
  egfr_kinase_public: {
    label: "Public EGFR kinase-domain structure bundled by the pinned upstream toolkit",
    source: "NVIDIA BioNeMo Agent Toolkit drug-discovery evaluation asset (egfr.pdb)",
    relativePath: "nim-skills/meta-skills/drug-discovery-pipeline/evals/files/egfr.pdb",
    sequence: EGFR_SEQUENCE,
  },
});

async function loadSample(id, vendorRoot = process.env.BIONEMO_VENDOR_ROOT || "/opt/bionemo/vendor/bionemo-agent-toolkit") {
  const definition = SAMPLES[id];
  if (!definition) throw new InputError(`sample must be one of: ${SAMPLE_IDS.join(", ")}`);
  const root = path.resolve(vendorRoot);
  const target = path.resolve(root, definition.relativePath);
  if (!target.startsWith(`${root}${path.sep}`)) throw new InputError("sample path escapes the pinned vendor root");
  const pdb = await readFile(target, "utf8");
  return { ...definition, pdb };
}

function exactlyOne(value, directKey, sampleKey) {
  if (Boolean(value[directKey]) === Boolean(value[sampleKey])) {
    throw new InputError(`set exactly one of ${directKey} or ${sampleKey}`);
  }
}

export async function resolveSkillInput(skillId, raw, options = {}) {
  const value = structuredClone(raw || {});
  if (skillId === "diffdock" && value.protein_sample !== undefined) {
    exactlyOne(value, "protein", "protein_sample");
    value.protein = (await loadSample(value.protein_sample, options.vendorRoot)).pdb;
    delete value.protein_sample;
  } else if ((skillId === "proteinmpnn" || skillId === "rfdiffusion") && value.input_pdb_sample !== undefined) {
    exactlyOne(value, "input_pdb", "input_pdb_sample");
    value.input_pdb = (await loadSample(value.input_pdb_sample, options.vendorRoot)).pdb;
    delete value.input_pdb_sample;
  }
  return value;
}

export async function resolveWorkflowInput(workflowId, raw, options = {}) {
  const value = structuredClone(raw || {});
  const sampleKey = workflowId === "drug_discovery" ? "protein_sample" : workflowId === "protein_binder_design" ? "target_sample" : null;
  if (!sampleKey || value[sampleKey] === undefined) return value;
  const directPdbKey = workflowId === "drug_discovery" ? "protein_pdb" : "target_pdb";
  const directSequenceKey = workflowId === "drug_discovery" ? "protein_sequence" : "target_sequence";
  if (value[directPdbKey] || value[directSequenceKey]) throw new InputError(`do not combine ${sampleKey} with ${directPdbKey} or ${directSequenceKey}`);
  const sample = await loadSample(value[sampleKey], options.vendorRoot);
  value[directPdbKey] = sample.pdb;
  value[directSequenceKey] = sample.sequence;
  delete value[sampleKey];
  return value;
}

export const PUBLIC_SAMPLES = Object.freeze(Object.fromEntries(Object.entries(SAMPLES).map(([id, item]) => [id, { label: item.label, source: item.source, sequenceLength: item.sequence.length }])));
export const __test = { loadSample, SAMPLES };
