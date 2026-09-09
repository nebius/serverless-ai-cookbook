import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { ArtifactStore } from "../openclaw-plugin/src/artifacts.mjs";
import { WorkflowRunner, __test } from "../openclaw-plugin/src/workflows.mjs";

const PDB = "CRYST1    1.000    1.000    1.000  90.00  90.00  90.00 P 1           1\nATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\nEND\n";
const PROTEIN = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ";

function result(skillId, data, elapsedMs = 5) { return { skillId, data, elapsedMs, requestId: `${skillId}-request` }; }

async function fixture(t, responses) {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-workflow-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const calls = [];
  const client = { async call(skillId, payload) {
    calls.push({ skillId, payload });
    const handler = responses[skillId];
    if (!handler) throw new Error(`unexpected ${skillId}`);
    return typeof handler === "function" ? handler(payload, calls) : handler;
  } };
  const store = await new ArtifactStore(root).initialize();
  return { calls, store, runner: new WorkflowRunner({ client, store }) };
}

test("drug discovery hands GenMol candidates to DiffDock then Boltz2 within event caps", async (t) => {
  const f = await fixture(t, {
    genmol: result("genmol", { molecules: [{ smiles: "CCO", score: 0.8 }, { smiles: "CCC", score: 0.6 }] }),
    diffdock: (payload) => result("diffdock", { ligand_positions: [`${payload.ligand}\n$$$$`], position_confidence: [payload.ligand === "CCO" ? 0.9 : 0.5] }),
    boltz2: result("boltz2", { affinities: { L1: { affinity_pic50: [7.1], affinity_probability_binary: [0.8] } }, structures: [{ structure: "data_complex\n#", format: "mmcif" }] }),
  });
  const output = await f.runner.run("drug_discovery", { protein_pdb: PDB, protein_sequence: PROTEIN, safe_notation: "[*{5-10}]", generated_molecules: 2, dock_candidates: 2, affinity_candidates: 1 });
  assert.deepEqual(f.calls.map((call) => call.skillId), ["genmol", "diffdock", "diffdock", "boltz2"]);
  assert.equal(f.calls[1].payload.ligand, "CCO");
  assert.equal(output.summary.ranked[0].pic50, 7.1);
  assert.ok(output.artifacts.some((item) => item.name === "workflow-summary.json"));
});

test("MSA-to-structure passes the returned A3M directly into OpenFold3", async (t) => {
  const alignment = `>query\n${PROTEIN}\n>homolog\n${PROTEIN}\n`;
  const f = await fixture(t, {
    msa_search: result("msa_search", { alignments: { Uniref30_2302: { a3m: { alignment } } } }),
    openfold3: (payload) => result("openfold3", { outputs: [{ structures_with_scores: [{ structure: "ATOM      1", format: "pdb", confidence_score: 0.7 }] }], echoed: payload }),
  });
  const output = await f.runner.run("msa_to_structure", { sequence: PROTEIN, max_msa_sequences: 20 });
  assert.deepEqual(f.calls.map((call) => call.skillId), ["msa_search", "openfold3"]);
  assert.equal(f.calls[1].payload.inputs[0].molecules[0].msa.uniref30.a3m.alignment, alignment);
  assert.equal(output.summary.msaSequenceCount, 2);
  const [manifest] = await f.store.listRuns();
  assert.deepEqual(manifest.steps.map((step) => step.status), ["completed", "completed"]);
});

test("binder workflow preserves RFdiffusion to ProteinMPNN to OpenFold3 handoffs", async (t) => {
  const designed = "ACDEFGHIKLMNPQRSTVWY";
  const f = await fixture(t, {
    rfdiffusion: result("rfdiffusion", { output_pdb: PDB, elapsed_ms: 3 }),
    proteinmpnn: result("proteinmpnn", { mfasta: `>native\n${PROTEIN}\n>design_1\n${designed}\n`, scores: [0.9] }),
    openfold3: (payload) => result("openfold3", { outputs: [{ structures_with_scores: [{ structure: "ATOM      1", format: "pdb" }] }], echoed: payload }),
  });
  const output = await f.runner.run("protein_binder_design", { target_pdb: PDB, target_sequence: PROTEIN, contigs: "A1-1/0 20-20", hotspot_res: ["A1"], binder_chain: "B", validation_model: "openfold3" });
  assert.deepEqual(f.calls.map((call) => call.skillId), ["rfdiffusion", "proteinmpnn", "openfold3"]);
  assert.equal(f.calls[1].payload.input_pdb, PDB);
  assert.equal(f.calls[1].payload.input_pdb_chains[0], "B");
  assert.equal(f.calls[2].payload.inputs[0].molecules[0].sequence, designed);
  assert.equal(output.summary.designedSequenceLength, designed.length);
});

test("binder workflow can select Boltz2 without adding any other model", async (t) => {
  const f = await fixture(t, {
    rfdiffusion: result("rfdiffusion", { output_pdb: PDB }),
    proteinmpnn: result("proteinmpnn", { mfasta: ">design\nACDEFGHIK\n" }),
    boltz2: result("boltz2", { structures: [{ structure: "data_binder\n#", format: "mmcif" }] }),
  });
  await f.runner.run("protein_binder_design", { target_pdb: PDB, target_sequence: PROTEIN, contigs: "A1-1/0 9-9", binder_chain: "B", validation_model: "boltz2" });
  assert.deepEqual(f.calls.map((call) => call.skillId), ["rfdiffusion", "proteinmpnn", "boltz2"]);
});

test("workflow parsers reject missing handoff data and exclude native rows", () => {
  assert.equal(__test.firstDesignedSequence(`>native\nAAAA\n>designed\nCCCC\n`), "CCCC");
  assert.throws(() => __test.firstDesignedSequence(">native\nAAAA\n"), /designed sequence/u);
  assert.throws(() => __test.firstAlignment({ alignments: {} }), /A3M/u);
  assert.throws(() => __test.generatedMolecules({ molecules: [] }).at(0).smiles, TypeError);
});

test("workflow failure is durable and contains no credential", async (t) => {
  const f = await fixture(t, { msa_search: async () => { const error = new Error("Bearer nvapi-super-secret failed"); error.code = "vendor"; throw error; } });
  await assert.rejects(() => f.runner.run("msa_to_structure", { sequence: PROTEIN }), /Bearer \[redacted\]/u);
  const runs = await f.store.listRuns();
  assert.equal(runs[0].status, "failed");
  assert.equal(runs[0].steps[0].status, "failed");
  assert.equal(JSON.stringify(runs[0]).includes("nvapi-super-secret"), false);
});
