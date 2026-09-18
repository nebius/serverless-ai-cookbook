import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { ArtifactStore } from "../../openclaw-plugin/src/artifacts.mjs";
import { NimClient } from "../../openclaw-plugin/src/client.mjs";
import { publicError } from "../../openclaw-plugin/src/errors.mjs";
import { WorkflowRunner } from "../../openclaw-plugin/src/workflows.mjs";

const LIVE = process.env.BIONEMO_RUN_LIVE === "1";
const RECIPE = path.resolve(new URL("../..", import.meta.url).pathname);
const OUTPUT = path.join(RECIPE, ".task-output", "live-nims");
const CRAMBIN = "TTCCPSIVARSNFNVCRLPGTPEAICATYTGCIIIPGATCPGDYAN";
const DUMMY_PDB = "CRYST1    1.000    1.000    1.000  90.00  90.00  90.00 P 1           1\nATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\nEND\n";

async function publicPdb() {
  return readFile(path.join(RECIPE, "vendor", "bionemo-agent-toolkit", "nim-skills", "diffdock-nim", "evals", "files", "protein.pdb"), "utf8");
}

function pdbChain(pdb, chain = "A") {
  const amino = { ALA: "A", ARG: "R", ASN: "N", ASP: "D", CYS: "C", GLN: "Q", GLU: "E", GLY: "G", HIS: "H", ILE: "I", LEU: "L", LYS: "K", MET: "M", PHE: "F", PRO: "P", SER: "S", THR: "T", TRP: "W", TYR: "Y", VAL: "V" };
  const seen = new Set();
  const residues = [];
  for (const line of pdb.split(/\r?\n/u)) {
    if (!line.startsWith("ATOM") || line.slice(21, 22) !== chain) continue;
    const author = line.slice(22, 26).trim();
    const key = `${chain}:${author}`;
    if (seen.has(key)) continue;
    seen.add(key);
    residues.push({ author: Number(author), amino: amino[line.slice(17, 20).trim()] || "X" });
  }
  return { sequence: residues.map((item) => item.amino).join(""), first: residues[0]?.author, last: residues.at(-1)?.author };
}

function summarize(id, payload) {
  return {
    id,
    bytes: Buffer.byteLength(JSON.stringify(payload)),
    sequenceLength: payload.sequence?.length ?? payload.protein_sequence?.length ?? null,
    pdbBytes: payload.protein ? Buffer.byteLength(payload.protein) : payload.input_pdb ? Buffer.byteLength(payload.input_pdb) : null,
    moleculeCount: payload.num_molecules ?? null,
  };
}

async function writeEvidence(name, evidence) {
  await mkdir(OUTPUT, { recursive: true });
  await writeFile(path.join(OUTPUT, name), `${JSON.stringify({ generatedAt: new Date().toISOString(), hostedOrigin: "https://health.api.nvidia.com", ...evidence }, null, 2)}\n`, { mode: 0o600 });
}

test("all ten hosted NIM skills return real responses", { skip: !LIVE, timeout: 10_800_000 }, async () => {
  assert.ok(process.env.NVIDIA_API_KEY || process.env.NGC_API_KEY, "NVIDIA_API_KEY or NGC_API_KEY is required");
  const receptor = await publicPdb();
  const matrix = {
    boltz2: { polymers: [{ id: "A", molecule_type: "protein", sequence: CRAMBIN }], recycling_steps: 1, sampling_steps: 10, diffusion_samples: 1, output_format: "mmcif" },
    diffdock: { protein: receptor, ligand: "CCO", ligand_file_type: "txt", num_poses: 1, time_divisions: 5, steps: 5, save_trajectory: false },
    evo2: { sequence: "ACGTACGTACGTACGT", num_tokens: 16, temperature: 0.7, top_k: 4, random_seed: 7 },
    genmol: { smiles: "[*{5-10}]", num_molecules: 2, scoring: "QED", unique: true, temperature: "1.0", noise: "1.0", step_size: 1 },
    molmim: { smi: "c1ccccc1", algorithm: "CMA-ES", num_molecules: 2, num_iterations: 2, property_name: "QED", particles: 2, radius: 1 },
    msa_search: { sequence: CRAMBIN, databases: ["Uniref30_2302"], e_value: 0.0001, max_msa_sequences: 20, output_alignment_formats: ["a3m"] },
    openfold2: { sequence: CRAMBIN, input_id: "crambin-public-1crn", selected_models: [1], relax: false },
    openfold3: { inputs: [{ input_id: "crambin-public-1crn", output_format: "pdb", molecules: [{ type: "protein", sequence: CRAMBIN, diffusion_samples: 1 }] }] },
    proteinmpnn: { input_pdb: receptor, input_pdb_chains: ["A"], num_seq_per_target: 1, sampling_temp: [0.1], random_seed: 7 },
    rfdiffusion: { input_pdb: DUMMY_PDB, contigs: "20-20", diffusion_steps: 5, random_seed: 7 },
  };
  const client = new NimClient();
  const store = await new ArtifactStore(path.join(OUTPUT, "artifacts")).initialize();
  const evidence = [];
  for (const [id, payload] of Object.entries(matrix)) {
    const startedAt = new Date().toISOString();
    try {
      const result = await client.call(id, payload);
      const run = await store.createRun({ kind: "live-skill", id, inputSummary: summarize(id, payload) });
      await store.saveNimResult(run, result);
      await store.complete(run);
      evidence.push({ ...summarize(id, payload), status: "completed", startedAt, elapsedMs: result.elapsedMs, requestId: result.requestId, responseKeys: Object.keys(result.data), artifacts: run.manifest.artifacts });
    } catch (error) {
      evidence.push({ ...summarize(id, payload), status: "failed", startedAt, error: publicError(error) });
    }
  }
  await writeEvidence("skills.json", { skills: evidence });
  assert.deepEqual(evidence.filter((item) => item.status !== "completed").map((item) => ({ id: item.id, error: item.error })), []);
});

test("all three composed hosted workflows finish end to end", { skip: !LIVE, timeout: 10_800_000 }, async () => {
  assert.ok(process.env.NVIDIA_API_KEY || process.env.NGC_API_KEY, "NVIDIA_API_KEY or NGC_API_KEY is required");
  const receptor = await publicPdb();
  const receptorChain = pdbChain(receptor);
  const store = await new ArtifactStore(path.join(OUTPUT, "workflow-artifacts")).initialize();
  const runner = new WorkflowRunner({ client: new NimClient(), store });
  const workflows = {
    drug_discovery: { protein_pdb: receptor, protein_sequence: receptorChain.sequence, safe_notation: "[*{5-10}]", generated_molecules: 2, dock_candidates: 1, affinity_candidates: 1 },
    msa_to_structure: { sequence: CRAMBIN, max_msa_sequences: 20, output_format: "pdb" },
    protein_binder_design: { target_pdb: receptor, target_sequence: receptorChain.sequence, contigs: `A${receptorChain.first}-${receptorChain.last}/0 20-20`, binder_chain: "B", validation_model: "openfold3", sampling_temperature: 0.1 },
  };
  const evidence = [];
  for (const [id, payload] of Object.entries(workflows)) {
    const started = performance.now();
    try {
      const output = await runner.run(id, payload);
      evidence.push({ id, status: "completed", elapsedMs: Math.round(performance.now() - started), runId: output.runId, steps: output.steps, artifacts: output.artifacts });
    } catch (error) {
      evidence.push({ id, status: "failed", elapsedMs: Math.round(performance.now() - started), error: publicError(error) });
    }
  }
  await writeEvidence("workflows.json", { workflows: evidence });
  assert.deepEqual(evidence.filter((item) => item.status !== "completed").map((item) => ({ id: item.id, error: item.error })), []);
});
