import { InputError, publicError } from "./errors.mjs";
import { validateWorkflowInput } from "./validation.mjs";

function generatedMolecules(data) {
  let candidates = data?.molecules ?? data?.generated ?? [];
  if (typeof candidates === "string") {
    try { candidates = JSON.parse(candidates); } catch { candidates = []; }
  }
  if (!Array.isArray(candidates)) throw new InputError("GenMol response did not contain a molecule list for workflow handoff");
  return candidates.map((item) => ({
    smiles: typeof item === "string" ? item : item?.smiles || item?.sample || item?.smi,
    generationScore: typeof item === "object" ? item?.score ?? null : null,
  })).filter((item) => typeof item.smiles === "string" && item.smiles.length > 0);
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
  if (workflowId === "drug_discovery") return { proteinPdbBytes: Buffer.byteLength(input.protein_pdb), proteinSequenceLength: input.protein_sequence.length, safeNotationLength: input.safe_notation.length };
  if (workflowId === "msa_to_structure") return { sequenceLength: input.sequence.length, maxMsaSequences: input.max_msa_sequences ?? 250 };
  return { targetPdbBytes: Buffer.byteLength(input.target_pdb), targetSequenceLength: input.target_sequence.length, contigs: input.contigs, hotspotCount: input.hotspot_res?.length ?? 0, validationModel: input.validation_model ?? "openfold3" };
}

export const __test = { generatedMolecules, firstAlignment, firstDesignedSequence, dockingCandidate, affinitySummary };
