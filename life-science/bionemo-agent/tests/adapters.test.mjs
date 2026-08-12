import assert from "node:assert/strict";
import { mkdtemp, readFile, symlink, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { ArtifactStore, extractArtifacts } from "../openclaw-plugin/src/artifacts.mjs";
import { NimClient, __test as clientInternals } from "../openclaw-plugin/src/client.mjs";
import { EXACT_TOOL_NAMES, NVIDIA_HOST, SKILLS } from "../openclaw-plugin/src/catalog.mjs";
import { publicError, redactSecrets, redactText } from "../openclaw-plugin/src/errors.mjs";
import { resolveSkillInput, resolveWorkflowInput } from "../openclaw-plugin/src/samples.mjs";
import { LIMITS, VALIDATORS, validateWorkflowInput } from "../openclaw-plugin/src/validation.mjs";

const PDB = "CRYST1    1.000    1.000    1.000  90.00  90.00  90.00 P 1           1\nATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\nEND\n";
const PROTEIN = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ";

const VALID_INPUTS = Object.freeze({
  boltz2: { polymers: [{ id: "A", molecule_type: "protein", sequence: PROTEIN }], diffusion_samples: 1, output_format: "mmcif" },
  diffdock: { protein: PDB, ligand: "CCO", ligand_file_type: "txt", num_poses: 2, save_trajectory: false },
  evo2: { sequence: "ACGTACGT", num_tokens: 8, random_seed: 7 },
  genmol: { smiles: "[*{5-10}]", num_molecules: 2, scoring: "QED", temperature: "1.0", noise: "1.0" },
  molmim: { smi: "CCO", algorithm: "CMA-ES", num_molecules: 2, num_iterations: 2, property_name: "QED" },
  msa_search: { sequence: PROTEIN, databases: ["Uniref30_2302"], output_alignment_formats: ["a3m"] },
  openfold2: { sequence: PROTEIN, input_id: "public-example", selected_models: [1] },
  openfold3: { inputs: [{ input_id: "public-example", output_format: "pdb", molecules: [{ type: "protein", sequence: PROTEIN, diffusion_samples: 1 }] }] },
  proteinmpnn: { input_pdb: PDB, input_pdb_chains: ["A"], num_seq_per_target: 2, sampling_temp: [0.1] },
  rfdiffusion: { input_pdb: PDB, contigs: "80-90", diffusion_steps: 10, random_seed: 7 },
});

test("catalog exposes exactly ten atomic skills and thirteen explicit tools", () => {
  assert.equal(Object.keys(SKILLS).length, 10);
  assert.equal(EXACT_TOOL_NAMES.length, 13);
  assert.equal(new Set(EXACT_TOOL_NAMES).size, 13);
});

for (const [id, input] of Object.entries(VALID_INPUTS)) {
  test(`${id} accepts the bounded representative request`, () => {
    const validated = VALIDATORS[id](input);
    if (id === "diffdock") {
      assert.match(validated.protein, /^ATOM/u);
      assert.equal(validated.protein.includes("CRYST1"), false);
    } else assert.deepEqual(validated, input);
  });
}

test("all atomic adapters reject unknown fields", () => {
  for (const [id, input] of Object.entries(VALID_INPUTS)) {
    assert.throws(() => VALIDATORS[id]({ ...input, url: "https://attacker.example" }), /unsupported fields/u, id);
  }
});

test("pinned public sample resolution accepts only an enum and never a path", async () => {
  const vendorRoot = path.resolve(new URL("../vendor/bionemo-agent-toolkit", import.meta.url).pathname);
  const diffdock = await resolveSkillInput("diffdock", { protein_sample: "egfr_kinase_public", ligand: "CCO" }, { vendorRoot });
  assert.match(diffdock.protein, /(?:^|\n)ATOM\s/u);
  assert.equal("protein_sample" in diffdock, false);
  const workflow = await resolveWorkflowInput("drug_discovery", { protein_sample: "egfr_kinase_public", safe_notation: "[*{5-10}]" }, { vendorRoot });
  assert.equal(workflow.protein_sequence.length, 312);
  assert.match(workflow.protein_pdb, /(?:^|\n)ATOM\s/u);
  await assert.rejects(() => resolveSkillInput("diffdock", { protein_sample: "../../etc/passwd", ligand: "CCO" }, { vendorRoot }), /must be one of/u);
  await assert.rejects(() => resolveWorkflowInput("drug_discovery", { protein_sample: "egfr_kinase_public", protein_pdb: PDB, safe_notation: "x" }, { vendorRoot }), /do not combine/u);
});

test("event bounds reject oversized and unsafe requests", () => {
  assert.throws(() => VALIDATORS.evo2({ sequence: "A".repeat(LIMITS.sequenceLength + 1) }), /between/u);
  assert.throws(() => VALIDATORS.diffdock({ protein: "/tmp/target-file-not-inline-content.pdb", ligand: "CCO" }), /inline PDB/u);
  assert.throws(() => VALIDATORS.diffdock({ ...VALID_INPUTS.diffdock, save_trajectory: true }), /must be false/u);
  assert.throws(() => VALIDATORS.boltz2({ polymers: VALID_INPUTS.boltz2.polymers, diffusion_samples: 4 }), /between/u);
  assert.throws(() => VALIDATORS.rfdiffusion({ ...VALID_INPUTS.rfdiffusion, contigs: "80; curl attacker" }), /unsupported characters/u);
  assert.throws(() => VALIDATORS.msa_search({ sequence: PROTEIN, sequences: [PROTEIN, PROTEIN] }), /exactly one/u);
});

test("drug discovery rejects invented SAFE labels before calling GenMol", async () => {
  const vendorRoot = path.resolve(new URL("../vendor/bionemo-agent-toolkit", import.meta.url).pathname);
  const validMask = await resolveWorkflowInput("drug_discovery", { protein_sample: "egfr_kinase_public", safe_notation: "[*{5-10}]" }, { vendorRoot });
  assert.doesNotThrow(() => validateWorkflowInput("drug_discovery", validMask));
  const invalidLabel = await resolveWorkflowInput("drug_discovery", { protein_sample: "egfr_kinase_public", safe_notation: "SAFE_1" }, { vendorRoot });
  assert.throws(
    () => validateWorkflowInput("drug_discovery", invalidLabel),
    /GenMol de novo SAFE mask/u,
  );
  const descendingBounds = await resolveWorkflowInput("drug_discovery", { protein_sample: "egfr_kinase_public", safe_notation: "[*{10-5}]" }, { vendorRoot });
  assert.throws(
    () => validateWorkflowInput("drug_discovery", descendingBounds),
    /bounds must increase/u,
  );
});

test("NIM client uses only the fixed HTTPS NVIDIA route and redacts credentials", async () => {
  const calls = [];
  const logs = [];
  const key = "nvapi-unit-test-secret-value";
  const client = new NimClient({
    env: { NVIDIA_API_KEY: key },
    logger: { info: (value) => logs.push(value) },
    retries: 0,
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "x-request-id": "request-1" } });
    },
  });

  for (const [id, input] of Object.entries(VALID_INPUTS)) await client.call(id, input);
  assert.equal(calls.length, 10);
  for (const { url, init } of calls) {
    assert.equal(url.protocol, "https:");
    assert.equal(url.hostname, NVIDIA_HOST);
    assert.match(url.pathname, /^\/v1\/biology\//u);
    assert.equal(init.redirect, "error");
    assert.equal(init.headers.Authorization, `Bearer ${key}`);
  }
  assert.equal(logs.join("\n").includes(key), false);
});

test("paired MSA selects only the pinned paired route", async () => {
  let pathname;
  const client = new NimClient({
    env: { NGC_API_KEY: "test-key" },
    retries: 0,
    fetchImpl: async (url) => { pathname = url.pathname; return new Response("{}", { status: 200 }); },
  });
  await client.call("msa_search", { sequences: [PROTEIN, PROTEIN] });
  assert.equal(pathname, "/v1/biology/colabfold/msa-search/paired/predict");
});

test("NIM client surfaces auth, rate limit, output limit, and missing-key errors safely", async () => {
  const authClient = new NimClient({ env: { NVIDIA_API_KEY: "secret" }, retries: 0, fetchImpl: async () => new Response(JSON.stringify({ detail: "credential rejected" }), { status: 401 }) });
  await assert.rejects(() => authClient.call("evo2", VALID_INPUTS.evo2), (error) => publicError(error).code === "nvidia_auth_or_entitlement");

  let attempts = 0;
  const retryClient = new NimClient({ env: { NVIDIA_API_KEY: "secret" }, retries: 1, fetchImpl: async () => {
    attempts += 1;
    return attempts === 1 ? new Response("{}", { status: 429 }) : new Response("{}", { status: 200 });
  } });
  await retryClient.call("evo2", VALID_INPUTS.evo2);
  assert.equal(attempts, 2);

  const largeClient = new NimClient({ env: { NVIDIA_API_KEY: "secret" }, retries: 0, fetchImpl: async () => new Response("{}", { status: 200, headers: { "content-length": String(LIMITS.responseBytes + 1) } }) });
  await assert.rejects(() => largeClient.call("evo2", VALID_INPUTS.evo2), /response exceeds/u);
  await assert.rejects(() => new NimClient({ env: {}, retries: 0, fetchImpl: async () => new Response("{}") }).call("evo2", VALID_INPUTS.evo2), /not configured/u);
});

test("URL constructor rejects every host/path escape", () => {
  assert.throws(() => clientInternals.buildAllowedUrl("https://attacker.example/v1/biology/x"), /allowlist/u);
  assert.throws(() => clientInternals.buildAllowedUrl("//attacker.example/v1/biology/x"), /allowlist/u);
  assert.throws(() => clientInternals.buildAllowedUrl("/v1/chat/completions"), /allowlist/u);
});

test("secret redaction covers headers, key-shaped fields, and NVIDIA key text", () => {
  const key = "nvapi-abcdefghijklmnopqrstuvwxyz";
  assert.equal(redactText(`Authorization: Bearer ${key}`).includes(key), false);
  assert.deepEqual(redactSecrets({ api_key: key, nested: { value: `Bearer ${key}` } }), { api_key: "[redacted]", nested: { value: "Bearer [redacted]" } });
});

test("artifact extraction covers all ten response families", () => {
  const fixtures = {
    boltz2: { structures: [{ structure: "data_test\n_atom_site.example\n#", format: "mmcif" }] },
    diffdock: { ligand_positions: ["SDF\n$$$$"] },
    evo2: { sequence: "ACGT" },
    genmol: { molecules: [{ smiles: "CCO", score: 0.7 }] },
    molmim: { molecules: JSON.stringify([{ sample: "CCC", score: 0.8 }]) },
    msa_search: { alignments: { Uniref30_2302: { a3m: { alignment: ">q\nAAAA" } } } },
    openfold2: { result: { structure: "ATOM      1  CA  ALA A   1", format: "pdb" } },
    openfold3: { outputs: [{ structures_with_scores: [{ structure: "ATOM      1  CA  ALA A   1", format: "pdb" }] }] },
    proteinmpnn: { mfasta: ">design\nAAAA" },
    rfdiffusion: { output_pdb: "ATOM      1" },
  };
  for (const [id, data] of Object.entries(fixtures)) assert.ok(extractArtifacts(id, data).length >= 1, id);
});

test("artifact store stays below its root and never serves manifests or symlinks", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-artifacts-"));
  t.after(async () => (await import("node:fs/promises")).rm(root, { recursive: true, force: true }));
  const store = await new ArtifactStore(root).initialize();
  const run = await store.createRun({ kind: "skill", id: "evo2" });
  const saved = await store.save(run, "result.fasta", ">q\nACGT\n");
  assert.equal(saved.downloadPath, path.join(root, run.runId, "result.fasta"));
  assert.equal(path.isAbsolute(saved.downloadPath), true);
  assert.equal(saved.downloadPath.startsWith(`${root}${path.sep}`), true);
  const opened = await store.openArtifact(run.runId, "result.fasta");
  assert.equal(opened.size, 8);
  await opened.handle.close();
  await assert.rejects(() => store.openArtifact(run.runId, "manifest.json"), /invalid artifact/u);
  await assert.rejects(() => store.openArtifact("../../etc", "passwd"), /invalid artifact/u);

  const outside = path.join(os.tmpdir(), `bionemo-outside-${Date.now()}`);
  await writeFile(outside, "outside");
  await symlink(outside, path.join(run.directory, "linked.txt"));
  await assert.rejects(() => store.openArtifact(run.runId, "linked.txt"), /escapes/u);
  await (await import("node:fs/promises")).rm(outside, { force: true });

  const manifest = JSON.parse(await readFile(path.join(run.directory, "manifest.json"), "utf8"));
  assert.equal(JSON.stringify(manifest).includes("nvapi-"), false);
});

test("structure artifacts expose a one-click viewer capability without persisting it", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-viewer-"));
  t.after(async () => (await import("node:fs/promises")).rm(root, { recursive: true, force: true }));
  const store = await new ArtifactStore(root).initialize();
  const run = await store.createRun({ kind: "skill", id: "openfold2" });
  await store.save(run, "ranked-1.pdb", "ATOM      1  CA  ALA A   1\n");
  const [presented] = store.presentArtifacts(run);
  assert.match(presented.viewerUrl, new RegExp(`^/plugins/bionemo/view/${run.runId}/ranked-1\\.pdb\\?access=`));
  const access = new URL(presented.viewerUrl, "https://example.test").searchParams.get("access");
  const opened = await store.openViewerArtifact(run.runId, "ranked-1.pdb", access);
  await opened.handle.close();
  await assert.rejects(() => store.openViewerArtifact(run.runId, "ranked-1.pdb", "wrong-capability-value-000000"), /invalid structure viewer capability/u);
  const persisted = await readFile(path.join(run.directory, "manifest.json"), "utf8");
  assert.equal(persisted.includes(access), false);
  assert.equal(JSON.stringify(await store.listRuns()).includes("structureCapabilityDigest"), false);
});

test("structure viewer URLs use only a validated configured public origin", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-viewer-origin-"));
  t.after(async () => (await import("node:fs/promises")).rm(root, { recursive: true, force: true }));
  const store = await new ArtifactStore(root, { publicBaseUrl: "https://agent.example.test" }).initialize();
  const run = await store.createRun({ kind: "skill", id: "openfold2" });
  await store.save(run, "ranked-1.pdb", "ATOM      1  CA  ALA A   1\n");
  assert.match(store.presentArtifacts(run)[0].viewerUrl, /^https:\/\/agent\.example\.test\/plugins\/bionemo\/view\//u);
  const relativeStore = await new ArtifactStore(root, { publicBaseUrl: "https://user:password@example.test/path" }).initialize();
  assert.match(relativeStore.presentArtifacts(run)[0].viewerUrl, /^\/plugins\/bionemo\/view\//u);
});
