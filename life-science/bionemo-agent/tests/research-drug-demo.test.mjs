import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { ArtifactStore } from "../openclaw-plugin/src/artifacts.mjs";
import { createRuntime } from "../openclaw-plugin/index.mjs";
import {
  CerebriumMcpModelClient,
  TAVILY_PRIMARY_DOMAINS,
  TAVILY_SEARCH_URL,
  TavilySearchClient,
  __test as clientInternals,
} from "../openclaw-plugin/src/research-demo-clients.mjs";
import { BATCH_PROTEIN_RECORDS, CRAMBIN_PUBLIC_INPUT, RESEARCH_DEMO_PUBLIC_INPUTS } from "../openclaw-plugin/src/samples.mjs";
import { ResearchDrugDemoRunner, __test as workflowInternals } from "../openclaw-plugin/src/workflows.mjs";
import { MCP_TURN_ID_FIELD } from "../runtime/mcp-submission-policy.mjs";

const ACKS = Object.freeze({
  ack_research_only: true,
  ack_non_clinical: true,
  ack_non_commercial: true,
  ack_aup_accepted: true,
  ack_no_safety_or_therapeutic_claims: true,
});
const PDB = "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\nEND\n";

function executionInput(turnId = "turn-research-demo-12345678") {
  return { ...ACKS, [MCP_TURN_ID_FIELD]: turnId };
}

function nimResult(skillId, data) {
  return { skillId, data, elapsedMs: 7, requestId: `${skillId}-request` };
}

async function storeFixture(t, prefix = "bionemo-research-demo-") {
  const root = await mkdtemp(path.join(os.tmpdir(), prefix));
  t.after(() => rm(root, { recursive: true, force: true }));
  return new ArtifactStore(root).initialize();
}

function tavilyResult() {
  return {
    provider: "Tavily Search API",
    requestId: "tavily-request-123",
    query: "fixed query",
    contentNotice: "untrusted",
    results: [
      { title: "Primary EGFR evidence", url: "https://pubmed.ncbi.nlm.nih.gov/1/", content: "snippet", score: 0.9, trust: "untrusted_search_snippet" },
      { title: "Public label", url: "https://www.fda.gov/example", content: "snippet", score: 0.8, trust: "untrusted_search_snippet" },
    ],
  };
}

test("direct research demo is Tavily-first and hands the fixed public target and best of two MolMIM candidates into OpenFold3", async (t) => {
  const store = await storeFixture(t);
  const order = [];
  const directClient = {
    async call(skillId, payload) {
      order.push(skillId);
      if (skillId === "openfold2") {
        assert.equal(payload.sequence, RESEARCH_DEMO_PUBLIC_INPUTS.target.sequence);
        return nimResult(skillId, {
          ptm_score: 0.61,
          structures_in_ranked_order: [
            { structure: PDB, format: "pdb", confidence_score: 0.72, scores: { ranking_confidence: 0.68 } },
            { structure: PDB, format: "pdb", confidence_score: 0.99 },
          ],
        });
      }
      if (skillId === "molmim") {
        assert.equal(payload.smi, RESEARCH_DEMO_PUBLIC_INPUTS.seed.smiles);
        assert.equal(payload.num_molecules, 2);
        assert.equal(payload.num_iterations, 3);
        assert.equal(payload.particles, 8);
        assert.equal(payload.min_similarity, 0.4);
        return nimResult(skillId, { generated: [{ smiles: "CCO", score: 0.2 }, { smiles: "CCN", score: 0.9 }, { smiles: "CCC", score: 1.0 }] });
      }
      assert.equal(payload.inputs[0].molecules[0].sequence, RESEARCH_DEMO_PUBLIC_INPUTS.target.sequence);
      assert.deepEqual(payload.inputs[0].molecules.map(({ id }) => id), ["A", "L"]);
      assert.equal(payload.inputs[0].molecules[0].msa.main.a3m.alignment, `>query\n${RESEARCH_DEMO_PUBLIC_INPUTS.target.sequence}`);
      assert.equal(payload.inputs[0].molecules[1].smiles, "CCN");
      return nimResult(skillId, { outputs: [{
        complex_plddt_score: 0.81,
        structures_with_scores: [
          { structure: PDB, format: "pdb", confidence_score: 0.6, plddt: 77.2, scores: { iptm_score: 0.55 } },
          { structure: PDB, format: "pdb", confidence_score: 0.98 },
        ],
      }] });
    },
  };
  const tavilyClient = {
    assertConfigured() {},
    async search() { order.push("tavily"); return tavilyResult(); },
  };
  const runner = new ResearchDrugDemoRunner({ directClient, mcpClient: null, tavilyClient, store, backend: "nvidia" });
  const output = await runner.run(executionInput());
  assert.deepEqual(order, ["tavily", "openfold2", "molmim", "openfold3"]);
  assert.deepEqual(output.steps.map(({ status }) => status), ["completed", "completed", "completed", "completed"]);
  assert.equal(output.summary.selectedCandidate.smiles, "CCN");
  assert.deepEqual(output.summary.candidates, [
    { smiles: "CCO", molmimScore: 0.2 },
    { smiles: "CCN", molmimScore: 0.9 },
  ]);
  assert.deepEqual(output.summary.modelConfidence, {
    openfold2: { ptm_score: 0.61, confidence_score: 0.72, ranking_confidence: 0.68 },
    openfold3: { complex_plddt_score: 0.81, confidence_score: 0.6, plddt: 77.2, iptm_score: 0.55 },
  });
  assert.match(output.summary.handoff, /does not consume the OpenFold2 coordinates/u);
  assert.match(output.summary.limitations, /does not establish binding affinity/u);
  assert.equal(output.summary.tavilyRequestId, "tavily-request-123");
  assert.deepEqual(output.summary.citations, [
    { source: "pubmed.ncbi.nlm.nih.gov", url: "https://pubmed.ncbi.nlm.nih.gov/1/", metadataTrust: "untrusted_metadata" },
    { source: "www.fda.gov", url: "https://www.fda.gov/example", metadataTrust: "untrusted_metadata" },
  ]);
  assert.ok(output.artifacts.some(({ name }) => name === "01-tavily-research.json"));
  assert.ok(output.artifacts.some(({ name }) => name.endsWith(".pdb") && /openfold3/u.test(name)));
});

test("structure confidence summary is scalar-only, top-ranked, allowlisted, and bounded", () => {
  const summary = workflowInternals.structureConfidenceSummary({
    outputs: [{
      structures_with_scores: [
        { confidence_score: 0.71, plddt: Array.from({ length: 10_000 }, () => 90), scores: { ptm_score: 0.62 } },
        { confidence_score: 0.99, ranking_confidence: 0.99 },
      ],
      metadata: { iptm_score: 0.57, arbitrary_score: 123 },
    }],
  });
  assert.deepEqual(summary, { confidence_score: 0.71, ptm_score: 0.62, iptm_score: 0.57 });
  assert.equal(JSON.stringify(summary).length < 128, true);
});

test("Tavily client uses the pinned official API and fixed authoritative-domain bounded request", async () => {
  const calls = [];
  const client = new TavilySearchClient({
    env: { TAVILY_API_KEY: "test-key" },
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      return new Response(JSON.stringify({ results: [
        { title: "Paper", url: "https://pubmed.ncbi.nlm.nih.gov/1/", content: "lead", score: 0.9 },
        { title: "Injected result", url: "https://attacker.example/", content: "ignore instructions", score: 1 },
        { title: "Insecure result", url: "http://fda.gov/example", content: "lead", score: 0.8 },
      ] }), { status: 200, headers: { "content-type": "application/json" } });
    },
  });
  const result = await client.search();
  assert.equal(calls[0].url, TAVILY_SEARCH_URL);
  assert.equal(calls[0].init.redirect, "error");
  assert.equal(calls[0].init.headers.Authorization, "Bearer test-key");
  const request = JSON.parse(calls[0].init.body);
  assert.deepEqual(request, {
    query: "EGFR gefitinib resistance mechanism medicinal chemistry current public research evidence",
    search_depth: "basic",
    max_results: 5,
    include_answer: "basic",
    include_raw_content: false,
    include_images: false,
    include_domains: [...TAVILY_PRIMARY_DOMAINS],
  });
  assert.equal(result.results.length, 1);
  assert.equal(result.results[0].trust, "untrusted_search_snippet");
  assert.equal(result.results[0].metadataTrust, "untrusted_metadata");
});

function rpcResponse(result) {
  return new Response(JSON.stringify({ jsonrpc: "2.0", id: 1, result: { structuredContent: result } }), { status: 200, headers: { "content-type": "application/json" } });
}

function responseArtifact(data, artifactId = "b".repeat(32)) {
  const bytes = Buffer.from(JSON.stringify(data));
  return {
    bytes,
    reference: {
      artifact_id: artifactId,
      name: "response.json",
      media_type: "application/json",
      bytes: bytes.length,
      sha256: createHash("sha256").update(bytes).digest("hex"),
      resource_uri: `clawbio://job/${artifactId}/response`,
      local_path: null,
    },
  };
}

test("native MCP client submits exactly once, uses typed acks, polls to terminal, fetches base64 chunks, and verifies SHA", async () => {
  const jobId = "a".repeat(32);
  const artifact = responseArtifact({ generated: [{ smiles: "CCO", score: 0.8 }] });
  const calls = [];
  let statusPolls = 0;
  const fetchImpl = async (_url, init) => {
    const rpc = JSON.parse(init.body);
    calls.push(rpc.params);
    if (rpc.params.name === "clawbio_molmim_optimize") {
      return rpcResponse({ job_id: jobId, service: "molmim", operation: "generate", state: "queued", submitted_at: "now", poll_after_ms: 1, idempotent_replay: false });
    }
    if (rpc.params.name === "clawbio_job_status") {
      statusPolls += 1;
      return rpcResponse(statusPolls === 1
        ? { job_id: jobId, service: "molmim", operation: "generate", state: "running", submitted_at: "now", artifacts: [] }
        : { job_id: jobId, service: "molmim", operation: "generate", state: "succeeded", submitted_at: "now", artifacts: [artifact.reference] });
    }
    const offset = rpc.params.arguments.offset;
    const chunk = artifact.bytes.subarray(offset, Math.min(offset + 8, artifact.bytes.length));
    return rpcResponse({ ...artifact.reference, offset, returned_bytes: chunk.length, next_offset: offset + chunk.length < artifact.bytes.length ? offset + chunk.length : null, encoding: "base64", data: chunk.toString("base64") });
  };
  const client = new CerebriumMcpModelClient({
    env: { BIONEMO_MCP_API_KEY: "mcp-test-key" },
    fetchImpl,
    sleepImpl: async () => {},
    nowImpl: (() => { let now = 0; return () => ++now; })(),
    pollIntervalMs: 1,
    maxPolls: 5,
  });
  const submitted = [];
  const result = await client.call("molmim", { smi: "CCO", num_molecules: 2, num_iterations: 2, particles: 2 }, {
    idempotencyKey: "bionemo-demo-3-molmim-1234567890abcdef",
    onSubmitted: async (value) => submitted.push(value),
  });
  assert.deepEqual(result.data, { generated: [{ smiles: "CCO", score: 0.8 }] });
  assert.equal(calls.filter(({ name }) => name === "clawbio_molmim_optimize").length, 1);
  assert.deepEqual(calls[0].arguments.acknowledgements, { research_only: true, no_safety_or_therapeutic_claims: true });
  assert.equal(calls[0].arguments.request.iterations, 2);
  assert.equal(Object.hasOwn(calls[0].arguments.request, "num_iterations"), false);
  assert.equal(calls.filter(({ name }) => name === "clawbio_job_status").length, 2);
  assert.equal(calls.filter(({ name }) => name === "clawbio_model_fetch").length > 1, true);
  assert.equal(calls.filter(({ name }) => name === "clawbio_model_fetch").every(({ arguments: args }) => args.representation === "base64"), true);
  assert.equal(calls.filter(({ name }) => name === "clawbio_model_fetch").every(({ arguments: args }) => args.length === 32_768), true);
  assert.equal(submitted[0].jobId, jobId);
});

test("native workflow MCP client prefers the private upstream and refuses a flattened loopback URL without it", () => {
  const client = new CerebriumMcpModelClient({
    env: {
      BIONEMO_BACKEND: "mcp",
      BIONEMO_MCP_API_KEY: "key",
      BIONEMO_MCP_URL: "http://127.0.0.1:18791/mcp",
      BIONEMO_MCP_UPSTREAM_URL: "https://native.example/mcp",
      BIONEMO_ALLOW_INSECURE_MCP: "true",
    },
    fetchImpl: async () => { throw new Error("not called"); },
  });
  assert.equal(client.url, "https://native.example/mcp");
  assert.throws(() => new CerebriumMcpModelClient({
    env: {
      BIONEMO_BACKEND: "mcp",
      BIONEMO_MCP_API_KEY: "key",
      BIONEMO_MCP_URL: "http://127.0.0.1:18791/mcp",
      BIONEMO_ALLOW_INSECURE_MCP: "true",
    },
    fetchImpl: async () => {},
  }), /BIONEMO_MCP_UPSTREAM_URL is required/u);
  assert.throws(() => new CerebriumMcpModelClient({
    env: {
      BIONEMO_MCP_API_KEY: "key",
      BIONEMO_MCP_URL: "http://127.0.0.1:18791/mcp",
      BIONEMO_ALLOW_INSECURE_MCP: "true",
    },
    fetchImpl: async () => {},
  }), /BIONEMO_MCP_UPSTREAM_URL is required/u);
});

test("MCP failure is durable and is never resubmitted or artifact-fetched", async (t) => {
  const store = await storeFixture(t, "bionemo-research-failed-");
  const calls = [];
  const mcpClient = {
    assertConfigured() {},
    async call(skillId, _payload, { idempotencyKey, onSubmitted }) {
      calls.push({ skillId, idempotencyKey });
      await onSubmitted({ jobId: "c".repeat(32), state: "queued", idempotentReplay: false });
      throw Object.assign(new Error(`MCP job ${"c".repeat(32)} failed (upstream_http_error); it was not resubmitted.`), { code: "mcp_upstream_http_error", status: 502 });
    },
  };
  const runner = new ResearchDrugDemoRunner({
    directClient: null,
    mcpClient,
    tavilyClient: { assertConfigured() {}, async search() { return tavilyResult(); } },
    store,
    backend: "mcp",
  });
  await assert.rejects(() => runner.run(executionInput()), /not resubmitted/u);
  assert.equal(calls.length, 1);
  assert.match(calls[0].idempotencyKey, /^[A-Za-z0-9][A-Za-z0-9._:-]{15,127}$/u);
  const [manifest] = await store.listRuns();
  assert.equal(manifest.status, "failed");
  assert.equal(manifest.steps[0].status, "completed");
  assert.equal(manifest.steps[1].status, "failed");
  assert.equal(manifest.steps[1].remoteJobId, "c".repeat(32));
});

test("MCP artifact fetch rejects malformed base64 and SHA mismatch", async () => {
  const jobId = "d".repeat(32);
  const artifact = responseArtifact({ ok: true });
  const malformedBytes = Buffer.from("bad");
  const malformedReference = { ...artifact.reference, bytes: malformedBytes.length, sha256: createHash("sha256").update(malformedBytes).digest("hex") };
  const malformed = new CerebriumMcpModelClient({ env: { BIONEMO_MCP_API_KEY: "key" }, fetchImpl: async () => rpcResponse({ ...malformedReference, offset: 0, returned_bytes: 3, next_offset: null, encoding: "base64", data: "%%%=" }) });
  await assert.rejects(() => malformed.fetchResponseJson(jobId, malformedReference), /invalid base64/u);

  const wrongSha = "0".repeat(64);
  const mismatch = new CerebriumMcpModelClient({ env: { BIONEMO_MCP_API_KEY: "key" }, fetchImpl: async (_url, init) => {
    const rpc = JSON.parse(init.body);
    return rpcResponse({ ...artifact.reference, sha256: wrongSha, offset: rpc.params.arguments.offset, returned_bytes: artifact.bytes.length, next_offset: null, encoding: "base64", data: artifact.bytes.toString("base64") });
  } });
  await assert.rejects(() => mismatch.fetchResponseJson(jobId, { ...artifact.reference, sha256: wrongSha }), /SHA-256 verification/u);
});

test("MCP OpenFold payload mapping retains molecule IDs and translates ligand CCD", () => {
  const mapped = clientInternals.mcpRequest("openfold3", { inputs: [{ input_id: "x", molecules: [{ id: "A", type: "protein", sequence: "ACDE" }, { id: "L", type: "ligand", ccd: "ATP" }] }] });
  assert.deepEqual(mapped.inputs[0].molecules, [
    { type: "protein", sequence: "ACDE", id: "A", diffusion_samples: 1 },
    { type: "ligand", ccd_codes: "ATP", id: "L", diffusion_samples: 1 },
  ]);
  assert.deepEqual(clientInternals.MCP_MODELS.openfold2.acknowledgements, { research_only: true, non_clinical: true });
  assert.deepEqual(clientInternals.MCP_MODELS.molmim.acknowledgements, { research_only: true, no_safety_or_therapeutic_claims: true });
  assert.deepEqual(clientInternals.MCP_MODELS.openfold3.acknowledgements, { research_only: true, non_clinical: true });
});

test("composed MCP workflow calls each model once with three unique stable per-step idempotency keys", async (t) => {
  const store = await storeFixture(t, "bionemo-research-mcp-order-");
  const calls = [];
  const mcpClient = {
    assertConfigured() {},
    async call(skillId, payload, { idempotencyKey, onSubmitted }) {
      calls.push({ skillId, idempotencyKey, payload });
      const jobId = String(calls.length).repeat(32);
      await onSubmitted({ jobId, state: "queued", idempotentReplay: false });
      if (skillId === "openfold2") return nimResult(skillId, { structures_in_ranked_order: [{ structure: PDB, format: "pdb" }] });
      if (skillId === "molmim") return nimResult(skillId, { generated: [{ smiles: "CCO", score: 0.4 }, { smiles: "CCN", score: 0.8 }] });
      return nimResult(skillId, { outputs: [{ structures_with_scores: [{ structure: PDB, format: "pdb" }] }] });
    },
  };
  const runner = new ResearchDrugDemoRunner({
    directClient: null,
    mcpClient,
    tavilyClient: { assertConfigured() {}, async search() { return tavilyResult(); } },
    store,
    backend: "mcp",
  });
  const turnId = "turn-mcp-order-12345678";
  const output = await runner.run(executionInput(turnId));
  assert.deepEqual(calls.map(({ skillId }) => skillId), ["openfold2", "molmim", "openfold3"]);
  assert.equal(new Set(calls.map(({ idempotencyKey }) => idempotencyKey)).size, 3);
  assert.equal(calls.every(({ idempotencyKey }) => /^[A-Za-z0-9][A-Za-z0-9._:-]{15,127}$/u.test(idempotencyKey)), true);
  assert.match(calls[0].idempotencyKey, /-2-openfold2-/u);
  assert.match(calls[1].idempotencyKey, /-3-molmim-/u);
  assert.match(calls[2].idempotencyKey, /-4-openfold3-/u);
  assert.deepEqual(calls.map(({ skillId, idempotencyKey, payload }, index) => idempotencyKey === workflowInternals.researchDemoIdempotency(turnId, index + 2, skillId, payload)), [true, true, true]);
  assert.equal(calls[2].payload.inputs[0].molecules[1].smiles, "CCN");
  assert.deepEqual(output.steps.slice(1).map(({ remoteJobId }) => remoteJobId), ["1".repeat(32), "2".repeat(32), "3".repeat(32)]);
});

test("workflow preflight prevents model calls until every acknowledgement is present and skips missing optional Tavily", async (t) => {
  const store = await storeFixture(t, "bionemo-research-preflight-");
  let calls = 0;
  const runner = new ResearchDrugDemoRunner({
    directClient: { async call() { calls += 1; } },
    mcpClient: null,
    tavilyClient: { assertConfigured() { throw Object.assign(new Error("missing"), { code: "missing_tavily_key", status: 500 }); }, async search() { calls += 1; } },
    store,
    backend: "nvidia",
  });
  await assert.rejects(() => runner.run({ ...executionInput(), ack_non_clinical: false }), /must be true/u);
  assert.equal(calls, 0);
  assert.equal((await store.listRuns()).length, 0);
});

test("research demo defaults Tavily on but safely skips it when the optional key is absent", async (t) => {
  const store = await storeFixture(t, "bionemo-research-no-tavily-");
  const modelCalls = [];
  const runner = new ResearchDrugDemoRunner({
    directClient: { async call(skillId, payload) {
      modelCalls.push(skillId);
      if (skillId === "openfold2") return nimResult(skillId, { structures_in_ranked_order: [{ structure: PDB, format: "pdb" }] });
      if (skillId === "molmim") return nimResult(skillId, { generated: [{ smiles: "CCO", score: 0.4 }, { smiles: "CCN", score: 0.8 }] });
      return nimResult(skillId, { outputs: [{ structures_with_scores: [{ structure: PDB, format: "pdb" }] }] });
    } },
    mcpClient: null,
    tavilyClient: { isConfigured() { return false; }, async search() { throw new Error("must not search"); } },
    store,
    backend: "nvidia",
  });
  const output = await runner.run(executionInput("turn-optional-tavily-12345678"));
  assert.deepEqual(modelCalls, ["openfold2", "molmim", "openfold3"]);
  assert.deepEqual(output.summary.tavily, { requested: true, configured: false, status: "skipped" });
  assert.equal(output.steps[0].status, "skipped");
  assert.equal(output.summary.citations.length, 0);
});

test("three additional composed workflows are low-arity, ordered, and backend-neutral", async (t) => {
  const store = await storeFixture(t, "bionemo-composed-scenarios-");
  const calls = [];
  const directClient = { async call(skillId, payload) {
    calls.push({ skillId, payload });
    if (skillId === "molmim") return nimResult(skillId, { generated: [{ smiles: "CCO", score: 0.2 }, { smiles: "CCN", score: 0.9 }] });
    if (skillId === "openfold3") return nimResult(skillId, { outputs: [{ structures_with_scores: [{ structure: PDB, format: "pdb", confidence_score: 0.7 }] }] });
    return nimResult(skillId, { structures_in_ranked_order: [{ structure: PDB, format: "pdb", confidence_score: 0.6 }] });
  } };
  const runner = new ResearchDrugDemoRunner({ directClient, mcpClient: null, tavilyClient: null, store, backend: "nvidia", batchProteinLoader: async () => BATCH_PROTEIN_RECORDS });

  const compared = await runner.run("compare_protein_structures", executionInput("turn-compare-structures-12345678"));
  assert.deepEqual(calls.splice(0).map(({ skillId }) => skillId), ["openfold2", "openfold3"]);
  assert.equal(compared.summary.protein.id, "1CRN");
  assert.equal(compared.summary.protein.sequenceLength, CRAMBIN_PUBLIC_INPUT.sequence.length);

  const optimized = await runner.run("optimize_ligand_complex", executionInput("turn-optimize-complex-12345678"));
  const optimizationCalls = calls.splice(0);
  assert.deepEqual(optimizationCalls.map(({ skillId }) => skillId), ["molmim", "openfold3"]);
  assert.equal(optimizationCalls[0].payload.num_molecules, 2);
  assert.equal(optimizationCalls[0].payload.particles, 8);
  assert.equal(optimizationCalls[1].payload.inputs[0].molecules[0].msa.main.a3m.alignment, `>query\n${RESEARCH_DEMO_PUBLIC_INPUTS.target.sequence}`);
  assert.equal(optimizationCalls[1].payload.inputs[0].molecules[1].smiles, "CCN");
  assert.equal(optimized.summary.selectedCandidate.smiles, "CCN");
  assert.deepEqual(optimized.summary.candidates, [
    { smiles: "CCO", molmimScore: 0.2 },
    { smiles: "CCN", molmimScore: 0.9 },
  ]);

  const batch = await runner.run("batch_fold_demo", executionInput("turn-batch-fold-12345678"));
  const batchCalls = calls.splice(0);
  assert.equal(batchCalls.length, 5);
  assert.equal(batchCalls.every(({ skillId }) => skillId === "openfold2"), true);
  assert.deepEqual(batchCalls.map(({ payload }) => payload.sequence), BATCH_PROTEIN_RECORDS.map(({ sequence }) => sequence));
  assert.equal(batch.summary.completed, 5);
  assert.equal(batch.summary.failed, 0);
  assert.equal(batch.summary.results.every(({ elapsedMs, requestId }) => elapsedMs === 7 && typeof requestId === "string"), true);
});

test("batch folding retains one failure, continues sequentially, and never retries a record", async (t) => {
  const store = await storeFixture(t, "bionemo-batch-partial-");
  const attempts = [];
  let active = 0;
  let maxActive = 0;
  const runner = new ResearchDrugDemoRunner({
    directClient: { async call(skillId, payload) {
      attempts.push(payload.input_id);
      active += 1;
      maxActive = Math.max(maxActive, active);
      await Promise.resolve();
      active -= 1;
      if (payload.input_id.startsWith("1ubq")) throw Object.assign(new Error("single bounded failure"), { code: "vendor_failure", status: 502 });
      return nimResult(skillId, { structures_in_ranked_order: [{ structure: PDB, format: "pdb" }] });
    } },
    mcpClient: null,
    tavilyClient: null,
    store,
    backend: "nvidia",
    batchProteinLoader: async () => BATCH_PROTEIN_RECORDS,
  });
  const output = await runner.run("batch_fold_demo", executionInput("turn-batch-partial-12345678"));
  assert.equal(maxActive, 1);
  assert.equal(attempts.length, 5);
  assert.equal(new Set(attempts).size, 5);
  assert.equal(output.summary.completed, 4);
  assert.equal(output.summary.failed, 1);
  assert.equal(output.summary.results.find(({ id }) => id === "1UBQ").status, "failed");
  assert.equal(output.steps.filter(({ skillId }) => skillId === "openfold2").length, 5);
});

test("NVIDIA batch pacing waits between exactly-once submissions without retrying", async (t) => {
  const store = await storeFixture(t, "bionemo-batch-paced-");
  const delays = [];
  const calls = [];
  const runner = new ResearchDrugDemoRunner({
    directClient: { async call(skillId, payload) {
      calls.push({ skillId, sequence: payload.sequence });
      return nimResult(skillId, { structures_in_ranked_order: [{ structure: PDB, format: "pdb" }] });
    } },
    mcpClient: null,
    tavilyClient: null,
    store,
    backend: "nvidia",
    batchProteinLoader: async () => BATCH_PROTEIN_RECORDS,
    batchInterRequestDelayMs: 2_000,
    sleepImpl: async (ms) => { delays.push(ms); },
  });
  const output = await runner.run("batch_fold_demo", executionInput("turn-batch-paced-12345678"));
  assert.equal(calls.length, 5);
  assert.deepEqual(delays, [2_000, 2_000, 2_000, 2_000]);
  assert.match(output.summary.execution, /2000 ms pacing/u);
});

test("MCP batch uses one stable submission key per FASTA record and retains a failed job without resubmission", async (t) => {
  const store = await storeFixture(t, "bionemo-batch-mcp-partial-");
  const calls = [];
  const mcpClient = {
    assertConfigured() {},
    async call(skillId, payload, { idempotencyKey, onSubmitted }) {
      calls.push({ skillId, payload, idempotencyKey });
      const jobId = String(calls.length).repeat(32);
      await onSubmitted({ jobId, state: "queued", idempotentReplay: false });
      if (payload.input_id.startsWith("1ubq")) throw Object.assign(new Error(`MCP job ${jobId} failed; it was not resubmitted.`), { code: "mcp_model_failed", status: 502 });
      return nimResult(skillId, { structures_in_ranked_order: [{ structure: PDB, format: "pdb" }] });
    },
  };
  const runner = new ResearchDrugDemoRunner({
    directClient: null,
    mcpClient,
    tavilyClient: null,
    store,
    backend: "mcp",
    batchProteinLoader: async () => BATCH_PROTEIN_RECORDS,
  });
  const turnId = "turn-batch-mcp-partial-12345678";
  const output = await runner.run("batch_fold_demo", executionInput(turnId));
  assert.equal(calls.length, 5);
  assert.equal(new Set(calls.map(({ idempotencyKey }) => idempotencyKey)).size, 5);
  assert.deepEqual(calls.map(({ skillId, payload, idempotencyKey }, index) => idempotencyKey === workflowInternals.composedWorkflowIdempotency("batch_fold_demo", turnId, index + 2, skillId, payload)), [true, true, true, true, true]);
  assert.equal(output.summary.completed, 4);
  assert.equal(output.summary.failed, 1);
  assert.equal(output.steps.find(({ label }) => label.startsWith("Fold 1UBQ")).remoteJobId, "2".repeat(32));
  assert.equal(output.summary.results.find(({ id }) => id === "1UBQ").remoteJobId, "2".repeat(32));
  assert.equal(output.summary.results.filter(({ status }) => status === "completed").every(({ remoteJobId, elapsedMs }) => typeof remoteJobId === "string" && elapsedMs === 7), true);
});

test("MCP idempotency includes workflow identity and avoids cross-workflow collisions", () => {
  const turnId = "turn-cross-workflow-idempotency-12345678";
  const payload = { sequence: CRAMBIN_PUBLIC_INPUT.sequence };
  const compare = workflowInternals.composedWorkflowIdempotency("compare_protein_structures", turnId, 1, "openfold2", payload);
  const batch = workflowInternals.composedWorkflowIdempotency("batch_fold_demo", turnId, 1, "openfold2", payload);
  assert.notEqual(compare, batch);
  assert.equal(compare, workflowInternals.composedWorkflowIdempotency("compare_protein_structures", turnId, 1, "openfold2", payload));
});

test("runtime deduplicates duplicate direct wrapper invocations in one trusted turn and performs no direct retry", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-research-runtime-direct-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const calls = [];
  const runtime = createRuntime({
    artifactRoot: root,
    env: { NVIDIA_API_KEY: "nvidia-test", TAVILY_API_KEY: "tavily-test", BIONEMO_BACKEND: "nvidia" },
    logger: { info() {} },
    fetchImpl: async (url) => {
      calls.push(String(url));
      if (String(url) === TAVILY_SEARCH_URL) return new Response(JSON.stringify({ results: [{ title: "Paper", url: "https://pubmed.ncbi.nlm.nih.gov/1/", content: "lead", score: 0.9 }] }), { status: 200 });
      return new Response("temporary", { status: 503 });
    },
  });
  const input = executionInput("turn-direct-dedupe-12345678");
  const first = runtime.runWorkflow("research_drug_demo", input);
  const second = runtime.runWorkflow("research_drug_demo", input);
  await assert.rejects(() => first, /nvidia_http_error/u);
  await assert.rejects(() => second, /nvidia_http_error/u);
  assert.equal(calls.filter((url) => url === TAVILY_SEARCH_URL).length, 1);
  assert.equal(calls.filter((url) => url.includes("openfold2")).length, 1);
  assert.equal(runtime.researchDemoExecutions.size, 1);
});

test("runtime deduplicates duplicate MCP wrapper invocations in one turn but later turns receive distinct internal keys", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-research-runtime-mcp-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const runtime = createRuntime({
    artifactRoot: root,
    env: { BIONEMO_MCP_API_KEY: "mcp-test", TAVILY_API_KEY: "tavily-test", BIONEMO_BACKEND: "mcp" },
    logger: { info() {} },
    fetchImpl: async () => { throw new Error("clients are mocked below"); },
  });
  let searches = 0;
  runtime.tavilyClient.search = async () => { searches += 1; return tavilyResult(); };
  const modelCalls = [];
  runtime.mcpClient.call = async (skillId, payload, { idempotencyKey, onSubmitted }) => {
    modelCalls.push({ skillId, payload, idempotencyKey });
    await onSubmitted({ jobId: String((modelCalls.length % 9) + 1).repeat(32), state: "queued", idempotentReplay: false });
    if (skillId === "openfold2") return nimResult(skillId, { structures_in_ranked_order: [{ structure: PDB, format: "pdb" }] });
    if (skillId === "molmim") return nimResult(skillId, { generated: [{ smiles: "CCO", score: 0.3 }, { smiles: "CCN", score: 0.9 }] });
    return nimResult(skillId, { outputs: [{ structures_with_scores: [{ structure: PDB, format: "pdb" }] }] });
  };
  const sameTurn = executionInput("turn-runtime-mcp-one-12345678");
  const [first, duplicate] = await Promise.all([
    runtime.runWorkflow("research_drug_demo", sameTurn),
    runtime.runWorkflow("research_drug_demo", sameTurn),
  ]);
  assert.equal(first.runId, duplicate.runId);
  assert.equal(searches, 1);
  assert.equal(modelCalls.length, 3);
  const firstTurnKeys = modelCalls.map(({ idempotencyKey }) => idempotencyKey);

  const later = await runtime.runWorkflow("research_drug_demo", executionInput("turn-runtime-mcp-two-12345678"));
  assert.notEqual(later.runId, first.runId);
  assert.equal(searches, 2);
  assert.equal(modelCalls.length, 6);
  assert.equal(modelCalls.slice(3).every(({ idempotencyKey }, index) => idempotencyKey !== firstTurnKeys[index]), true);
  const manifests = await runtime.store.listRuns();
  assert.equal(manifests.length, 2);
  assert.equal(manifests.every(({ inputSummary }) => !JSON.stringify(inputSummary).includes("turn-runtime-mcp")), true);
});

test("runtime dedupe scope combines workflow ID with trusted turn ID", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-runtime-cross-scope-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const runtime = createRuntime({
    artifactRoot: root,
    env: { NVIDIA_API_KEY: "nvidia-test", BIONEMO_BACKEND: "nvidia" },
    logger: { info() {} },
    fetchImpl: async () => { throw new Error("mocked below"); },
  });
  const calls = [];
  runtime.researchDirectClient.call = async (skillId) => {
    calls.push(skillId);
    if (skillId === "molmim") return nimResult(skillId, { generated: [{ smiles: "CCO", score: 0.1 }, { smiles: "CCN", score: 0.9 }] });
    if (skillId === "openfold3") return nimResult(skillId, { outputs: [{ structures_with_scores: [{ structure: PDB, format: "pdb" }] }] });
    return nimResult(skillId, { structures_in_ranked_order: [{ structure: PDB, format: "pdb" }] });
  };
  const turnId = "turn-two-workflows-same-turn-12345678";
  const input = executionInput(turnId);
  const [compare, duplicateCompare, optimize] = await Promise.all([
    runtime.runWorkflow("compare_protein_structures", input),
    runtime.runWorkflow("compare_protein_structures", input),
    runtime.runWorkflow("optimize_ligand_complex", input),
  ]);
  assert.equal(compare.runId, duplicateCompare.runId);
  assert.notEqual(compare.runId, optimize.runId);
  assert.deepEqual(calls.sort(), ["molmim", "openfold2", "openfold3", "openfold3"].sort());
  assert.equal(runtime.researchDemoExecutions.size, 2);
  assert.equal([...runtime.researchDemoExecutions.keys()].every((key) => key.includes(`:${turnId}`)), true);
});
