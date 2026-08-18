import { readFile } from "node:fs/promises";
import path from "node:path";
import { InputError } from "./errors.mjs";
import { BATCH_DEMO_INPUT_FILE } from "./validation.mjs";

export const SAMPLE_IDS = Object.freeze(["egfr_kinase_public"]);
export const EGFR_KINASE_SEQUENCE = "GEAPNQALLRILKETEFKKIKVLGSGAFGTVYKGLWIPEGEKVKIPVAIKELREATSPKANKEILDEAYVMASVDNPHVCRLLGICLTSTVQLITQLMPFGCLLDYVREHKDNIGSQYLLNWCVQIAKGMNYLEDRRLVHRDLAARNVLVKTPQHVKITDFGLAKLLGAEEKEYHAEGGKVPIKWMALESILHRIYTHQSDVWSYGVTVWELMTFGSKPYDGIPASEISSILEKGERLPQPPICTIDVYMIMVKCWMIDADSRPKFRELIIEFSKMARDPQRYLVIQGDERMHLMDEEDMDDVVDADEYLIP";
export const GEFITINIB_SMILES = "COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCCCN1CCOCC1";
export const GEFITINIB_KEKULE_SMILES = "COC1=C(C=C2C(=C1)N=CN=C2NC3=CC(=C(C=C3)F)Cl)OCCCN4CCOCC4";
export const RESEARCH_DEMO_PUBLIC_INPUTS = Object.freeze({
  target: Object.freeze({
    name: "EGFR kinase domain",
    sequence: EGFR_KINASE_SEQUENCE,
    source: "https://www.uniprot.org/uniprotkb/P00533/entry",
  }),
  seed: Object.freeze({
    name: "gefitinib",
    smiles: GEFITINIB_SMILES,
    source: "https://pubchem.ncbi.nlm.nih.gov/compound/Gefitinib",
  }),
});

export const CRAMBIN_PUBLIC_INPUT = Object.freeze({
  id: "1CRN",
  name: "Crambin",
  sequence: "TTCCPSIVARSNFNVCRLPGTPEAICATYTGCIIIPGATCPGDYAN",
  source: "https://www.rcsb.org/structure/1CRN",
});

export const BATCH_FASTA_RELATIVE_PATH = BATCH_DEMO_INPUT_FILE;
export const BAKED_WORKFLOW_DATA_ROOT = "/workspace/agent";
export const BATCH_PROTEIN_RECORDS = Object.freeze([
  CRAMBIN_PUBLIC_INPUT,
  Object.freeze({ id: "1UBQ", name: "Ubiquitin", sequence: "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG", source: "https://www.rcsb.org/structure/1UBQ" }),
  Object.freeze({ id: "1PGA", name: "Protein G B1 domain", sequence: "MTYKLILNGKTLKGETTTEAVDAATAEKVFKQYANDNGVDGEWTYDDATKTFTVTE", source: "https://www.rcsb.org/structure/1PGA" }),
  Object.freeze({ id: "2CI2", name: "Chymotrypsin inhibitor 2", sequence: "SSVEKKPEGVNTGAGDRHNLKTEWPELVGKSVEEAKKVILQDKPEAQIIVLPVGTIVTMEYRIDRVRLFVDKLDNIAEVPRVG", source: "https://www.rcsb.org/structure/2CI2" }),
  Object.freeze({ id: "1VII", name: "Villin headpiece subdomain", sequence: "MLSDEDFKAVFGMTRSAFANLPLWKQQNLKKEKGLF", source: "https://www.rcsb.org/structure/1VII" }),
]);

const BATCH_RECORD_BY_ID = new Map(BATCH_PROTEIN_RECORDS.map((record) => [record.id, record]));
const BATCH_PROTEIN = /^[ACDEFGHIKLMNPQRSTVWY]+$/u;

export function parseBatchProteinFasta(text) {
  if (typeof text !== "string" || text.length < 1 || Buffer.byteLength(text, "utf8") > 16_384) {
    throw new InputError("bundled batch FASTA must be a nonempty file no larger than 16384 bytes");
  }
  const records = [];
  let active = null;
  for (const [index, rawLine] of text.split(/\r?\n/u).entries()) {
    const line = rawLine.trim();
    if (!line) continue;
    if (line.startsWith(">")) {
      const id = line.slice(1).trim().split(/\s+/u)[0];
      if (!id) throw new InputError(`batch FASTA header on line ${index + 1} is missing an ID`);
      active = { id, sequence: "" };
      records.push(active);
      continue;
    }
    if (!active) throw new InputError(`batch FASTA sequence on line ${index + 1} appears before a header`);
    if (!BATCH_PROTEIN.test(line)) throw new InputError(`batch FASTA record ${active.id} contains an invalid protein sequence`);
    active.sequence += line;
  }
  if (records.length !== BATCH_PROTEIN_RECORDS.length) {
    throw new InputError(`bundled batch FASTA must contain exactly ${BATCH_PROTEIN_RECORDS.length} records`);
  }
  if (new Set(records.map(({ id }) => id)).size !== records.length) throw new InputError("bundled batch FASTA record IDs must be unique");
  return records.map((record, index) => {
    const expected = BATCH_RECORD_BY_ID.get(record.id);
    if (!expected || BATCH_PROTEIN_RECORDS[index].id !== record.id) {
      throw new InputError("bundled batch FASTA must contain the five reviewed public IDs in the documented order");
    }
    if (record.sequence !== expected.sequence) {
      throw new InputError(`bundled batch FASTA record ${record.id} does not match its reviewed public sequence and length`);
    }
    return { ...expected };
  });
}

function batchProteinFilePath(workflowDataRoot = BAKED_WORKFLOW_DATA_ROOT, relativePath = BATCH_FASTA_RELATIVE_PATH) {
  if (relativePath !== BATCH_FASTA_RELATIVE_PATH) throw new InputError("batch input_file must be the fixed bundled FASTA path");
  const root = path.resolve(workflowDataRoot);
  const target = path.resolve(root, relativePath);
  if (!target.startsWith(`${root}${path.sep}`)) throw new InputError("batch FASTA path escapes the baked workflow data root");
  return target;
}

export async function loadBatchProteinFile(relativePath = BATCH_FASTA_RELATIVE_PATH, options = {}) {
  const workflowDataRoot = options.workflowDataRoot || BAKED_WORKFLOW_DATA_ROOT;
  return parseBatchProteinFasta(await readFile(batchProteinFilePath(workflowDataRoot, relativePath), "utf8"));
}

const SAMPLES = Object.freeze({
  egfr_kinase_public: {
    label: "Public EGFR kinase-domain structure bundled by the pinned upstream toolkit",
    source: "NVIDIA BioNeMo Agent Toolkit drug-discovery evaluation asset (egfr.pdb)",
    relativePath: "nim-skills/meta-skills/drug-discovery-pipeline/evals/files/egfr.pdb",
    sequence: EGFR_KINASE_SEQUENCE,
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
export const __test = { loadSample, SAMPLES, batchProteinFilePath };
