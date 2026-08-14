import { createHash } from "node:crypto";
import { InputError, publicError } from "./errors.mjs";
import { LocalLigandEmbeddabilityPreflight } from "./ligand-preflight.mjs";
import { BATCH_FASTA_RELATIVE_PATH, CRAMBIN_PUBLIC_INPUT, RESEARCH_DEMO_PUBLIC_INPUTS, loadBatchProteinFile } from "./samples.mjs";
import { CROSS_BACKEND_WORKFLOW_IDS, RESEARCH_DEMO_ACK_FIELDS, validateWorkflowInput } from "./validation.mjs";
import { MCP_TURN_ID_FIELD, validMcpTurnId } from "../../runtime/mcp-submission-policy.mjs";

export function generatedMolecules(data) {
  let candidates = data?.molecules ?? data?.generated ?? [];
  if (typeof candidates === "string") {
    try { candidates = JSON.parse(candidates); } catch { candidates = []; }
  }
  if (!Array.isArray(candidates)) throw new InputError("GenMol response did not contain a molecule list for workflow handoff");
  return candidates.map((item) => {
    const score = typeof item === "object" && item?.score !== undefined && item?.score !== null ? Number(item.score) : NaN;
    return {
      smiles: typeof item === "string" ? item : item?.smiles || item?.sample || item?.smi,
      generationScore: Number.isFinite(score) ? score : null,
    };
  }).filter((item) => typeof item.smiles === "string" && item.smiles.length > 0 && item.smiles.length <= 2_048);
}

function firstAlignment(data) {
  const preferred = data?.alignments?.Uniref30_2302?.a3m?.alignment
    || data?.alignments?.uniref30?.a3m?.alignment;
  if (typeof preferred === "string" && preferred.includes(">")) return preferred;
  const visit = (value, depth = 0) => {
    if (depth > 10 || !value) return null;
    if (typeof value === "string" && value.includes(">") && value.includes("\n")) return value;
    if (Array.isArray(value)) {
      for (const item of value) { const found = visit(item, depth + 1); if (found) return found; }
    } else if (typeof value === "object") {
      for (const item of Object.values(value)) { const found = visit(item, depth + 1); if (found) return found; }
    }
    return null;
  };
  const alignment = visit(data?.alignments || data);
  if (!alignment) throw new InputError("MSA Search response did not contain an A3M alignment for OpenFold3 handoff");
  return alignment;
}

function firstDesignedSequence(mfasta) {
  if (typeof mfasta !== "string") throw new InputError("ProteinMPNN response did not contain multi-FASTA output");
  const records = mfasta.split(/^>/mu).filter(Boolean).map((record) => {
    const [header, ...sequenceLines] = record.trim().split(/\r?\n/u);
    return { header, sequence: sequenceLines.join("").trim() };
  });
  const designed = records.find((record) => !/(?:native|\bwt\b)/iu.test(record.header) && record.sequence);
  if (!designed) throw new InputError("ProteinMPNN response did not contain a designed sequence after excluding native/WT rows");
  return designed.sequence;
}

function dockingCandidate(result, molecule) {
  const pose = Array.isArray(result.data?.ligand_positions) ? result.data.ligand_positions[0] : null;
  const confidence = Array.isArray(result.data?.position_confidence) ? result.data.position_confidence[0] : null;
  if (typeof pose !== "string") throw new InputError("DiffDock response did not contain a ranked SDF pose for workflow handoff");
  return { ...molecule, pose, dockingConfidence: Number.isFinite(confidence) ? confidence : null };
}

function affinitySummary(result) {
  const affinities = result.data?.affinities;
  const value = affinities?.L1 || (affinities && Object.values(affinities)[0]);
  const first = (item) => Array.isArray(item) ? item[0] : item;
  return {
    pic50: first(value?.affinity_pic50) ?? null,
    probabilityBinding: first(value?.affinity_probability_binary) ?? null,
  };
}

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  return JSON.stringify(value);
}

function composedWorkflowIdempotency(workflowId, turnId, stepIndex, skillId, payload = {}) {
  if (!CROSS_BACKEND_WORKFLOW_IDS.includes(workflowId)) throw new InputError(`unsupported cross-backend workflow: ${workflowId}`);
  const digest = createHash("sha256").update(`${workflowId}:${turnId}:${stepIndex}:${skillId}:${canonicalJson(payload)}`, "utf8").digest("hex").slice(0, 32);
  return `bionemo-${workflowId}-${stepIndex}-${skillId}-${digest}`;
}

function researchDemoIdempotency(turnId, stepIndex, skillId, payload = {}) {
  return composedWorkflowIdempotency("research_drug_demo", turnId, stepIndex, skillId, payload);
}

function crossBackendExecutionInput(workflowId, rawInput) {
  if (!rawInput || typeof rawInput !== "object" || Array.isArray(rawInput)) return { input: rawInput, turnId: null };
  const turnId = rawInput[MCP_TURN_ID_FIELD];
  if (!validMcpTurnId(turnId)) throw new InputError(`The ${workflowId} workflow requires a trusted per-turn execution identity`);
  const input = Object.fromEntries(Object.entries(rawInput).filter(([key]) => key !== MCP_TURN_ID_FIELD));
  return { input, turnId };
}

function researchDemoExecutionInput(rawInput) {
  return crossBackendExecutionInput("research_drug_demo", rawInput);
}

function selectedMolecule(candidates) {
  if (!Array.isArray(candidates) || !candidates.length) throw new InputError("MolMIM returned no valid molecules for the OpenFold3 handoff");
  return candidates.map((candidate, responseIndex) => ({ candidate, responseIndex })).sort((a, b) => {
    const left = Number.isFinite(a.candidate.generationScore) ? a.candidate.generationScore : -Infinity;
    const right = Number.isFinite(b.candidate.generationScore) ? b.candidate.generationScore : -Infinity;
    return right - left || a.responseIndex - b.responseIndex;
  })[0].candidate;
}

const DEFAULT_LIGAND_PREFLIGHT = new LocalLigandEmbeddabilityPreflight();
const LIGAND_SELECTION_BASIS = "highest_molmim_score_among_openfold3_embeddable_candidates";
const LIGAND_SELECTION_TIE_BREAK = "earliest_candidate_in_molmim_response";

function ligandCandidateSummary(candidate) {
  return {
    smiles: candidate.smiles,
    molmimScore: candidate.generationScore,
    molmimResponseIndex: candidate.molmimResponseIndex,
    preflight: candidate.preflight,
  };
}

async function preflightAndSelectLigand(candidates, ligandPreflight) {
  if (!Array.isArray(candidates) || !candidates.length) throw new InputError("MolMIM returned no valid molecules for the OpenFold3 handoff");
  if (typeof ligandPreflight?.assess !== "function") {
    throw Object.assign(new Error("The local ligand embeddability preflight is not configured; OpenFold3 was not called."), {
      code: "ligand_preflight_unavailable",
      status: 500,
      retryable: false,
    });
  }
  const results = await ligandPreflight.assess(candidates.map(({ smiles }) => smiles));
  if (!Array.isArray(results) || results.length !== candidates.length) {
    throw Object.assign(new Error("The local ligand embeddability preflight returned an invalid result set; OpenFold3 was not called."), {
      code: "ligand_preflight_invalid_response",
      status: 500,
      retryable: false,
    });
  }
  const assessed = candidates.map((candidate, molmimResponseIndex) => {
    const result = results[molmimResponseIndex];
    if (typeof result?.embeddable !== "boolean" || typeof result?.code !== "string" || result.code.length > 64) {
      throw Object.assign(new Error("The local ligand embeddability preflight returned an invalid candidate result; OpenFold3 was not called."), {
        code: "ligand_preflight_invalid_response",
        status: 500,
        retryable: false,
      });
    }
    return {
      ...candidate,
      molmimResponseIndex,
      preflight: { embeddable: result.embeddable, code: result.code },
    };
  });
  const embeddable = assessed.filter((candidate) => candidate.preflight.embeddable);
  if (!embeddable.length) {
    throw Object.assign(new Error("No MolMIM candidate passed the bounded local ligand embeddability preflight; OpenFold3 was not called."), {
      code: "no_embeddable_ligand_candidate",
      status: 422,
      retryable: false,
    });
  }
  return {
    candidates: assessed,
    selected: selectedMolecule(embeddable),
    selection: {
      basis: LIGAND_SELECTION_BASIS,
      tieBreak: LIGAND_SELECTION_TIE_BREAK,
      assessedCandidateCount: assessed.length,
      embeddableCandidateCount: embeddable.length,
    },
  };
}

const STRUCTURE_CONFIDENCE_FIELDS = new Set([
  "confidence_score",
  "complex_plddt_score",
  "ptm_score",
  "iptm_score",
  "ranking_confidence",
  "plddt",
]);

export function structureConfidenceSummary(data) {
  const summary = {};
  let visited = 0;
  const visit = (value, depth = 0) => {
    if (!value || depth > 8 || visited >= 128) return;
    visited += 1;
    if (Array.isArray(value)) {
      // Ranked structure/model arrays are best-first. Only inspect the top item.
      if (value.length) visit(value[0], depth + 1);
      return;
    }
    if (typeof value !== "object") return;
    for (const [key, nested] of Object.entries(value)) {
      if (STRUCTURE_CONFIDENCE_FIELDS.has(key)) {
        if (!(key in summary) && typeof nested === "number" && Number.isFinite(nested)) summary[key] = nested;
        // Never descend into per-residue confidence arrays under an allowed key.
        continue;
      }
      visit(nested, depth + 1);
      if (visited >= 128) break;
    }
  };
  visit(data);
  return summary;
}

function queryOnlyMsa(sequence) {
  return { main: { a3m: { alignment: `>query\n${sequence}`, format: "a3m" } } };
}

export class ResearchDrugDemoRunner {
  constructor({
    directClient,
    mcpClient,
    tavilyClient,
    store,
    backend,
    ligandPreflight = DEFAULT_LIGAND_PREFLIGHT,
    batchProteinLoader = loadBatchProteinFile,
    batchInterRequestDelayMs = 0,
    sleepImpl = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
    onProgress = () => {},
  }) {
    this.directClient = directClient;
    this.mcpClient = mcpClient;
    this.tavilyClient = tavilyClient;
    this.store = store;
    this.backend = backend;
    this.ligandPreflight = ligandPreflight;
    this.batchProteinLoader = batchProteinLoader;
    this.batchInterRequestDelayMs = Math.max(0, Math.min(Number(batchInterRequestDelayMs) || 0, 10_000));
    this.sleepImpl = sleepImpl;
    this.onProgress = onProgress;
  }

  async persistStep(run, steps, step) {
    run.manifest.steps = steps;
    await this.store.writeManifest(run.directory, run.manifest);
    await this.onProgress({ runId: run.runId, ...step });
  }

  async tavilyStep(run, steps) {
    const step = {
      label: "Research current public EGFR and gefitinib evidence",
      skillId: "tavily_search",
      model: "Tavily Search API",
      status: "running",
      startedAt: new Date().toISOString(),
    };
    steps.push(step);
    await this.persistStep(run, steps, step);
    try {
      const research = await this.tavilyClient.search();
      await this.store.save(run, "01-tavily-research.json", `${JSON.stringify(research, null, 2)}\n`);
      step.status = "completed";
      step.sourceCount = research.results.length;
      step.completedAt = new Date().toISOString();
      await this.persistStep(run, steps, step);
      return research;
    } catch (error) {
      step.status = "failed";
      step.completedAt = new Date().toISOString();
      await this.persistStep(run, steps, step);
      throw error;
    }
  }

  async skippedTavilyStep(run, steps, { requested, configured }) {
    const step = {
      label: "Research current public EGFR and gefitinib evidence",
      skillId: "tavily_search",
      model: "Tavily Search API",
      status: "skipped",
      requested,
      configured,
      completedAt: new Date().toISOString(),
    };
    steps.push(step);
    await this.persistStep(run, steps, step);
    return {
      provider: "Tavily Search API",
      requestId: null,
      results: [],
      skipped: true,
      requested,
      configured,
    };
  }

  tavilyConfigured() {
    if (typeof this.tavilyClient?.isConfigured === "function") return this.tavilyClient.isConfigured();
    try {
      this.tavilyClient?.assertConfigured?.();
      return Boolean(this.tavilyClient);
    } catch (error) {
      if (error?.code === "missing_tavily_key") return false;
      throw error;
    }
  }

  assertBackendConfigured() {
    if (this.backend === "mcp" && !this.mcpClient) throw Object.assign(new Error("Cerebrium BioNeMo MCP client is unavailable."), { code: "missing_bionemo_backend", status: 500 });
    if (this.backend === "mcp") this.mcpClient.assertConfigured?.();
    else if (this.backend === "nvidia" && !this.directClient) throw Object.assign(new Error("NVIDIA BioNeMo client is unavailable."), { code: "missing_bionemo_backend", status: 500 });
    else if (!["mcp", "nvidia"].includes(this.backend)) throw Object.assign(new Error("No BioNeMo model backend is configured for this workflow."), { code: "missing_bionemo_backend", status: 500 });
  }

  async modelStep(run, steps, workflowId, turnId, skillId, payload, label, model) {
    const stepIndex = steps.length + 1;
    const step = {
      label,
      skillId,
      model,
      backend: this.backend,
      status: "running",
      startedAt: new Date().toISOString(),
    };
    steps.push(step);
    await this.persistStep(run, steps, step);
    try {
      let result;
      if (this.backend === "mcp") {
        const idempotencyKey = composedWorkflowIdempotency(workflowId, turnId, stepIndex, skillId, payload);
        step.idempotencyKey = idempotencyKey;
        await this.persistStep(run, steps, step);
        result = await this.mcpClient.call(skillId, payload, {
          idempotencyKey,
          onSubmitted: async ({ jobId, state, idempotentReplay }) => {
            step.remoteJobId = jobId;
            step.remoteState = state;
            step.idempotentReplay = idempotentReplay;
            await this.persistStep(run, steps, step);
          },
        });
      } else if (this.backend === "nvidia") {
        result = await this.directClient.call(skillId, payload);
      } else {
        throw Object.assign(new Error("No BioNeMo model backend is configured for this workflow."), { code: "missing_bionemo_backend", status: 500 });
      }
      step.status = "completed";
      step.elapsedMs = result.elapsedMs;
      step.completedAt = new Date().toISOString();
      await this.store.saveNimResult(run, result, `${String(stepIndex).padStart(2, "0")}-${skillId}`);
      await this.persistStep(run, steps, step);
      return result;
    } catch (error) {
      step.status = "failed";
      step.completedAt = new Date().toISOString();
      await this.persistStep(run, steps, step);
      throw error;
    }
  }

  async researchDrugDemo(run, steps, workflowId, turnId, input) {
    const configured = this.tavilyConfigured();
    const research = input.use_tavily && configured
      ? await this.tavilyStep(run, steps)
      : await this.skippedTavilyStep(run, steps, { requested: input.use_tavily, configured });
    const targetCharacterization = await this.modelStep(run, steps, workflowId, turnId, "openfold2", {
      sequence: RESEARCH_DEMO_PUBLIC_INPUTS.target.sequence,
      input_id: "egfr-kinase-public",
      selected_models: [1],
      relax: false,
    }, "Characterize the public EGFR target structure", "OpenFold2");

    const optimized = await this.modelStep(run, steps, workflowId, turnId, "molmim", {
      smi: RESEARCH_DEMO_PUBLIC_INPUTS.seed.smiles,
      algorithm: "CMA-ES",
      num_molecules: 2,
      num_iterations: 3,
      property_name: "QED",
      particles: 8,
      minimize: false,
      min_similarity: 0.4,
      radius: 1,
    }, "Optimize two gefitinib-derived candidates", "MolMIM");
    const preflight = await preflightAndSelectLigand(generatedMolecules(optimized.data).slice(0, 2), this.ligandPreflight);
    const { candidates, selected: best } = preflight;

    const complex = await this.modelStep(run, steps, workflowId, turnId, "openfold3", {
      inputs: [{
        input_id: "egfr-optimized-ligand-public-demo",
        output_format: "pdb",
        molecules: [
          { id: "A", type: "protein", sequence: RESEARCH_DEMO_PUBLIC_INPUTS.target.sequence, diffusion_samples: 1, msa: queryOnlyMsa(RESEARCH_DEMO_PUBLIC_INPUTS.target.sequence) },
          { id: "L", type: "ligand", smiles: best.smiles, diffusion_samples: 1 },
        ],
      }],
    }, "Model the same EGFR sequence with the best MolMIM candidate", "OpenFold3");

    return {
      researchOnly: true,
      nonClinical: true,
      nonCommercial: true,
      backend: this.backend,
      target: {
        name: RESEARCH_DEMO_PUBLIC_INPUTS.target.name,
        sequenceLength: RESEARCH_DEMO_PUBLIC_INPUTS.target.sequence.length,
        source: RESEARCH_DEMO_PUBLIC_INPUTS.target.source,
      },
      seed: {
        name: RESEARCH_DEMO_PUBLIC_INPUTS.seed.name,
        source: RESEARCH_DEMO_PUBLIC_INPUTS.seed.source,
      },
      tavily: { requested: input.use_tavily, configured, status: research.skipped ? "skipped" : "completed" },
      tavilyRequestId: research.requestId || null,
      citations: research.results.map(({ url }) => ({
        source: new URL(url).hostname,
        url,
        metadataTrust: "untrusted_metadata",
      })),
      modelSteps: steps.map(({ model, skillId, remoteJobId }) => ({ model, skillId, ...(remoteJobId ? { remoteJobId } : {}) })),
      candidates: candidates.map(ligandCandidateSummary),
      selectedCandidate: ligandCandidateSummary(best),
      candidateSelection: preflight.selection,
      modelConfidence: {
        openfold2: structureConfidenceSummary(targetCharacterization.data),
        openfold3: structureConfidenceSummary(complex.data),
      },
      openfold3OutputCount: complex.data?.outputs?.[0]?.structures_with_scores?.length ?? null,
      handoff: "OpenFold2 characterizes the target structure. After deterministic local embeddability preflight, OpenFold3 independently models the same target sequence with the highest-scoring passing MolMIM ligand; OpenFold3 does not consume the OpenFold2 coordinates.",
      limitations: "Search snippets are untrusted evidence leads. This bounded workflow does not establish binding affinity, safety, therapeutic efficacy, or clinical validity. Review primary sources, model confidence, chemical validity, and structure plausibility, then perform appropriate computational replication and wet-lab validation.",
    };
  }

  async compareProteinStructures(run, steps, workflowId, turnId) {
    const openfold2 = await this.modelStep(run, steps, workflowId, turnId, "openfold2", {
      sequence: CRAMBIN_PUBLIC_INPUT.sequence,
      input_id: "1crn-crambin-public",
      selected_models: [1],
      relax: false,
    }, "Predict public Crambin with OpenFold2", "OpenFold2");
    const openfold3 = await this.modelStep(run, steps, workflowId, turnId, "openfold3", {
      inputs: [{
        input_id: "1crn-crambin-public",
        output_format: "pdb",
        molecules: [{ id: "A", type: "protein", sequence: CRAMBIN_PUBLIC_INPUT.sequence, diffusion_samples: 1, msa: queryOnlyMsa(CRAMBIN_PUBLIC_INPUT.sequence) }],
      }],
    }, "Predict the identical public Crambin sequence with OpenFold3", "OpenFold3");
    return {
      researchOnly: true,
      nonClinical: true,
      nonCommercial: true,
      backend: this.backend,
      protein: { id: CRAMBIN_PUBLIC_INPUT.id, name: CRAMBIN_PUBLIC_INPUT.name, sequenceLength: CRAMBIN_PUBLIC_INPUT.sequence.length, source: CRAMBIN_PUBLIC_INPUT.source },
      predictions: {
        openfold2: { confidence: structureConfidenceSummary(openfold2.data) },
        openfold3: { confidence: structureConfidenceSummary(openfold3.data), outputCount: openfold3.data?.outputs?.[0]?.structures_with_scores?.length ?? null },
      },
      comparisonScope: "Both models receive the identical reviewed 1CRN Crambin sequence. Their predictions are presented side by side; this workflow does not claim experimental agreement or calculate an RMSD.",
      limitations: "Model confidence is not experimental validation. Inspect both structures and validate any conclusion against the public experimental reference and appropriate structural metrics.",
    };
  }

  async optimizeLigandComplex(run, steps, workflowId, turnId) {
    const optimized = await this.modelStep(run, steps, workflowId, turnId, "molmim", {
      smi: RESEARCH_DEMO_PUBLIC_INPUTS.seed.smiles,
      algorithm: "CMA-ES",
      num_molecules: 2,
      num_iterations: 3,
      property_name: "QED",
      particles: 8,
      minimize: false,
      min_similarity: 0.4,
      radius: 1,
    }, "Optimize exactly two gefitinib-derived candidates", "MolMIM");
    const preflight = await preflightAndSelectLigand(generatedMolecules(optimized.data).slice(0, 2), this.ligandPreflight);
    const { candidates, selected: best } = preflight;
    const complex = await this.modelStep(run, steps, workflowId, turnId, "openfold3", {
      inputs: [{
        input_id: "egfr-gefitinib-optimization-public",
        output_format: "pdb",
        molecules: [
          { id: "A", type: "protein", sequence: RESEARCH_DEMO_PUBLIC_INPUTS.target.sequence, diffusion_samples: 1, msa: queryOnlyMsa(RESEARCH_DEMO_PUBLIC_INPUTS.target.sequence) },
          { id: "L", type: "ligand", smiles: best.smiles, diffusion_samples: 1 },
        ],
      }],
    }, "Model public EGFR with the best-scoring MolMIM candidate", "OpenFold3");
    return {
      researchOnly: true,
      nonClinical: true,
      nonCommercial: true,
      backend: this.backend,
      target: { name: RESEARCH_DEMO_PUBLIC_INPUTS.target.name, sequenceLength: RESEARCH_DEMO_PUBLIC_INPUTS.target.sequence.length, source: RESEARCH_DEMO_PUBLIC_INPUTS.target.source },
      seed: { name: RESEARCH_DEMO_PUBLIC_INPUTS.seed.name, source: RESEARCH_DEMO_PUBLIC_INPUTS.seed.source },
      requestedCandidateCount: 2,
      validCandidateCount: candidates.length,
      embeddableCandidateCount: preflight.selection.embeddableCandidateCount,
      candidates: candidates.map(ligandCandidateSummary),
      selectedCandidate: ligandCandidateSummary(best),
      candidateSelection: preflight.selection,
      complexConfidence: structureConfidenceSummary(complex.data),
      openfold3OutputCount: complex.data?.outputs?.[0]?.structures_with_scores?.length ?? null,
      limitations: "MolMIM score ranking and a predicted complex do not establish chemical validity, binding affinity, safety, therapeutic efficacy, or clinical utility. Review chemistry and structure plausibility and validate experimentally.",
    };
  }

  async batchFoldDemo(run, steps, workflowId, turnId, input, records) {
    const fileStep = {
      label: "Read and validate the fixed five-protein FASTA",
      skillId: "batch_fasta",
      status: "completed",
      inputFile: input.input_file,
      recordCount: records.length,
      completedAt: new Date().toISOString(),
    };
    steps.push(fileStep);
    await this.store.save(run, "00-five-proteins-input.fasta", `${records.map(({ id, name, sequence }) => `>${id} ${name}\n${sequence}`).join("\n")}\n`);
    await this.persistStep(run, steps, fileStep);

    const results = [];
    for (const [recordIndex, record] of records.entries()) {
      if (recordIndex > 0 && this.batchInterRequestDelayMs > 0) {
        await this.sleepImpl(this.batchInterRequestDelayMs);
      }
      const stepIndex = steps.length;
      try {
        const folded = await this.modelStep(run, steps, workflowId, turnId, "openfold2", {
          sequence: record.sequence,
          input_id: `${record.id.toLowerCase()}-public-batch`,
          selected_models: [1],
          relax: false,
        }, `Fold ${record.id} ${record.name}`, "OpenFold2");
        const completedStep = steps[stepIndex];
        results.push({
          id: record.id,
          name: record.name,
          sequenceLength: record.sequence.length,
          source: record.source,
          status: "completed",
          elapsedMs: folded.elapsedMs ?? completedStep?.elapsedMs,
          ...(completedStep?.remoteJobId ? { remoteJobId: completedStep.remoteJobId } : {}),
          ...(folded.requestId ? { requestId: folded.requestId } : {}),
          confidence: structureConfidenceSummary(folded.data),
        });
      } catch (error) {
        const safe = publicError(error);
        const failedStep = steps[stepIndex];
        results.push({
          id: record.id,
          name: record.name,
          sequenceLength: record.sequence.length,
          source: record.source,
          status: "failed",
          ...(failedStep?.remoteJobId ? { remoteJobId: failedStep.remoteJobId } : {}),
          error: { code: safe.code, message: safe.message },
        });
      }
    }
    const completed = results.filter(({ status }) => status === "completed").length;
    return {
      researchOnly: true,
      nonClinical: true,
      nonCommercial: true,
      backend: this.backend,
      inputFile: BATCH_FASTA_RELATIVE_PATH,
      recordCount: records.length,
      completed,
      failed: records.length - completed,
      execution: `Five records were processed sequentially${this.batchInterRequestDelayMs ? ` with ${this.batchInterRequestDelayMs} ms pacing between submissions` : ""}. Each OpenFold2 request was submitted exactly once with no client retry; a failed record was retained and did not trigger resubmission or abort later records.`,
      results,
      limitations: "Predicted structures are computational hypotheses. Compare confidence per protein, inspect artifacts, and validate conclusions against experimental structures or wet-lab evidence.",
    };
  }

  async run(workflowIdOrInput, maybeRawInput) {
    const workflowId = typeof workflowIdOrInput === "string" ? workflowIdOrInput : "research_drug_demo";
    const rawInput = typeof workflowIdOrInput === "string" ? maybeRawInput : workflowIdOrInput;
    if (!CROSS_BACKEND_WORKFLOW_IDS.includes(workflowId)) throw new InputError(`unsupported cross-backend workflow: ${workflowId}`);
    const { input: suppliedInput, turnId } = crossBackendExecutionInput(workflowId, rawInput);
    const input = validateWorkflowInput(workflowId, suppliedInput);
    this.assertBackendConfigured();
    const records = workflowId === "batch_fold_demo" ? await this.batchProteinLoader(input.input_file) : null;
    const run = await this.store.createRun({
      kind: "workflow",
      id: workflowId,
      inputSummary: summarizeWorkflowInput(workflowId, input),
    });
    const steps = [];
    try {
      let summary;
      if (workflowId === "research_drug_demo") summary = await this.researchDrugDemo(run, steps, workflowId, turnId, input);
      else if (workflowId === "compare_protein_structures") summary = await this.compareProteinStructures(run, steps, workflowId, turnId);
      else if (workflowId === "optimize_ligand_complex") summary = await this.optimizeLigandComplex(run, steps, workflowId, turnId);
      else summary = await this.batchFoldDemo(run, steps, workflowId, turnId, input, records);
      await this.store.save(run, "workflow-summary.json", `${JSON.stringify(summary, null, 2)}\n`);
      await this.store.complete(run, { steps });
      return { runId: run.runId, summary, steps, artifacts: this.store.presentArtifacts(run) };
    } catch (error) {
      const active = steps.findLast((step) => step.status === "running");
      if (active) { active.status = "failed"; active.completedAt = new Date().toISOString(); }
      const safe = publicError(error);
      await this.store.complete(run, { status: "failed", error: safe, steps });
      throw Object.assign(new Error(`${safe.code}: ${safe.message}`), { code: safe.code, status: safe.status });
    }
  }
}

export class WorkflowRunner {
  constructor({ client, store, onProgress = () => {} }) {
    this.client = client;
    this.store = store;
    this.onProgress = onProgress;
  }

  async callStep(run, steps, skillId, payload, label) {
    const step = { label, skillId, status: "running", startedAt: new Date().toISOString() };
    steps.push(step);
    run.manifest.steps = steps;
    await this.store.writeManifest(run.directory, run.manifest);
    await this.onProgress({ runId: run.runId, ...step });
    try {
      const result = await this.client.call(skillId, payload);
      step.status = "completed";
      step.elapsedMs = result.elapsedMs;
      step.completedAt = new Date().toISOString();
      await this.store.saveNimResult(run, result, `${String(steps.length).padStart(2, "0")}-${skillId}`);
      await this.store.writeManifest(run.directory, run.manifest);
      await this.onProgress({ runId: run.runId, ...step });
      return result;
    } catch (error) {
      step.status = "failed";
      step.completedAt = new Date().toISOString();
      await this.store.writeManifest(run.directory, run.manifest);
      await this.onProgress({ runId: run.runId, ...step });
      throw error;
    }
  }

  async run(workflowId, rawInput) {
    const input = validateWorkflowInput(workflowId, rawInput);
    const run = await this.store.createRun({ kind: "workflow", id: workflowId, inputSummary: summarizeWorkflowInput(workflowId, input) });
    const steps = [];
    try {
      let summary;
      if (workflowId === "drug_discovery") summary = await this.drugDiscovery(run, steps, input);
      else if (workflowId === "msa_to_structure") summary = await this.msaToStructure(run, steps, input);
      else if (workflowId === "protein_binder_design") summary = await this.proteinBinderDesign(run, steps, input);
      else throw new InputError(`unsupported workflow: ${workflowId}`);
      await this.store.save(run, "workflow-summary.json", `${JSON.stringify(summary, null, 2)}\n`);
      await this.store.complete(run, { steps });
      return { runId: run.runId, summary, steps, artifacts: this.store.presentArtifacts(run) };
    } catch (error) {
      const active = steps.findLast((step) => step.status === "running");
      if (active) { active.status = "failed"; active.completedAt = new Date().toISOString(); }
      const safe = publicError(error);
      await this.store.complete(run, { status: "failed", error: safe, steps });
      throw Object.assign(new Error(`${safe.code}: ${safe.message}`), { code: safe.code, status: safe.status });
    }
  }

  async drugDiscovery(run, steps, input) {
    const generatedCount = input.generated_molecules ?? 8;
    const dockCount = Math.min(input.dock_candidates ?? 3, generatedCount);
    const affinityCount = Math.min(input.affinity_candidates ?? 2, dockCount);
    const generation = await this.callStep(run, steps, "genmol", {
      smiles: input.safe_notation,
      num_molecules: generatedCount,
      scoring: "QED",
      unique: true,
      temperature: "1.0",
      noise: "1.0",
    }, "Generate bounded molecule candidates");
    const molecules = generatedMolecules(generation.data).sort((a, b) => (b.generationScore ?? -Infinity) - (a.generationScore ?? -Infinity)).slice(0, dockCount);
    if (!molecules.length) throw new InputError("GenMol returned no valid molecules for DiffDock handoff");

    const docked = [];
    for (const [index, molecule] of molecules.entries()) {
      const result = await this.callStep(run, steps, "diffdock", {
        protein: input.protein_pdb,
        ligand: molecule.smiles,
        ligand_file_type: "txt",
        num_poses: 3,
        time_divisions: 20,
        steps: 18,
        save_trajectory: false,
      }, `Dock molecule ${index + 1} of ${molecules.length}`);
      docked.push(dockingCandidate(result, molecule));
    }
    docked.sort((a, b) => (b.dockingConfidence ?? -Infinity) - (a.dockingConfidence ?? -Infinity));

    const ranked = [];
    for (const [index, candidate] of docked.slice(0, affinityCount).entries()) {
      const result = await this.callStep(run, steps, "boltz2", {
        polymers: [{ id: "A", molecule_type: "protein", sequence: input.protein_sequence }],
        ligands: [{ id: "L1", smiles: candidate.smiles, predict_affinity: true }],
        recycling_steps: 3,
        sampling_steps: 50,
        diffusion_samples: 1,
        output_format: "mmcif",
      }, `Predict affinity for docked candidate ${index + 1} of ${affinityCount}`);
      ranked.push({
        smiles: candidate.smiles,
        generationScore: candidate.generationScore,
        dockingConfidence: candidate.dockingConfidence,
        ...affinitySummary(result),
      });
    }
    ranked.sort((a, b) => (b.pic50 ?? -Infinity) - (a.pic50 ?? -Infinity));
    return { researchOnly: true, generated: generatedCount, docked: docked.length, affinityScored: ranked.length, ranked };
  }

  async msaToStructure(run, steps, input) {
    const msa = await this.callStep(run, steps, "msa_search", {
      sequence: input.sequence,
      databases: ["Uniref30_2302", "colabfold_envdb_202108"],
      e_value: 0.0001,
      max_msa_sequences: input.max_msa_sequences ?? 250,
      output_alignment_formats: ["a3m"],
    }, "Search homologs and produce A3M");
    const alignment = firstAlignment(msa.data);
    const structure = await this.callStep(run, steps, "openfold3", {
      inputs: [{
        input_id: "msa-informed-research-structure",
        output_format: input.output_format ?? "pdb",
        molecules: [{
          type: "protein",
          sequence: input.sequence,
          diffusion_samples: 1,
          msa: { uniref30: { a3m: { alignment, format: "a3m" } } },
        }],
      }],
    }, "Predict MSA-informed structure");
    return {
      researchOnly: true,
      msaSequenceCount: (alignment.match(/^>/gmu) || []).length,
      outputCount: structure.data?.outputs?.[0]?.structures_with_scores?.length ?? null,
    };
  }

  async proteinBinderDesign(run, steps, input) {
    const backbone = await this.callStep(run, steps, "rfdiffusion", {
      input_pdb: input.target_pdb,
      contigs: input.contigs,
      ...(input.hotspot_res ? { hotspot_res: input.hotspot_res } : {}),
      diffusion_steps: 50,
    }, "Generate one bounded binder backbone");
    if (typeof backbone.data?.output_pdb !== "string") throw new InputError("RFdiffusion response did not contain a backbone PDB");
    const sequenceDesign = await this.callStep(run, steps, "proteinmpnn", {
      input_pdb: backbone.data.output_pdb,
      input_pdb_chains: [input.binder_chain],
      num_seq_per_target: 4,
      sampling_temp: [input.sampling_temperature ?? 0.1],
      use_soluble_model: true,
    }, "Design sequences for the binder chain");
    const binderSequence = firstDesignedSequence(sequenceDesign.data?.mfasta);
    const validationModel = input.validation_model ?? "openfold3";
    let validation;
    if (validationModel === "boltz2") {
      validation = await this.callStep(run, steps, "boltz2", {
        polymers: [
          { id: "A", molecule_type: "protein", sequence: binderSequence },
          { id: "B", molecule_type: "protein", sequence: input.target_sequence },
        ],
        recycling_steps: 3,
        sampling_steps: 50,
        diffusion_samples: 1,
        output_format: "mmcif",
      }, "Co-fold and score binder-target complex with Boltz2");
    } else {
      validation = await this.callStep(run, steps, "openfold3", {
        inputs: [{
          input_id: "binder-target-research-complex",
          output_format: "pdb",
          molecules: [
            { type: "protein", sequence: binderSequence, diffusion_samples: 1 },
            { type: "protein", sequence: input.target_sequence, diffusion_samples: 1 },
          ],
        }],
      }, "Co-fold and score binder-target complex with OpenFold3");
    }
    return {
      researchOnly: true,
      validationModel,
      designedSequenceLength: binderSequence.length,
      outputCount: validation.data?.outputs?.[0]?.structures_with_scores?.length ?? null,
      caveat: "Computational design requires structural review, experimental validation, and wet-lab testing.",
    };
  }
}

export function summarizeWorkflowInput(workflowId, input) {
  if (CROSS_BACKEND_WORKFLOW_IDS.includes(workflowId)) {
    return {
      backendNeutral: true,
      acknowledgementsAccepted: RESEARCH_DEMO_ACK_FIELDS.filter((field) => input[field] === true),
      ...(workflowId === "research_drug_demo" ? { useTavily: input.use_tavily } : {}),
      ...(workflowId === "batch_fold_demo" ? { inputFile: input.input_file } : {}),
    };
  }
  if (workflowId === "drug_discovery") return { proteinPdbBytes: Buffer.byteLength(input.protein_pdb), proteinSequenceLength: input.protein_sequence.length, safeNotationLength: input.safe_notation.length };
  if (workflowId === "msa_to_structure") return { sequenceLength: input.sequence.length, maxMsaSequences: input.max_msa_sequences ?? 250 };
  return { targetPdbBytes: Buffer.byteLength(input.target_pdb), targetSequenceLength: input.target_sequence.length, contigs: input.contigs, hotspotCount: input.hotspot_res?.length ?? 0, validationModel: input.validation_model ?? "openfold3" };
}

export const __test = { canonicalJson, generatedMolecules, firstAlignment, firstDesignedSequence, dockingCandidate, affinitySummary, crossBackendExecutionInput, researchDemoExecutionInput, composedWorkflowIdempotency, researchDemoIdempotency, selectedMolecule, preflightAndSelectLigand, structureConfidenceSummary, queryOnlyMsa };
