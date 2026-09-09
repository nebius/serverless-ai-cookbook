---
name: drug-discovery-pipeline
description: Run the bounded GenMol to DiffDock to Boltz2 research workflow with the scientific gateway skills and tools.
license: Apache-2.0 AND CC-BY-4.0
---

# Drug discovery pipeline

Compose the gateway skills yourself — there is no bundled pipeline tool:

1. **Generate** with `genmol`: a real SMILES scaffold with masked growing
   sites `[*{n-m}]` (never placeholder masks such as `SAFE_1`), `num_molecules`
   1–16, `unique: true`.
2. **Dock** a capped shortlist with `diffdock`: inline target PDB bytes
   (40 B–2 MB with `ATOM` records) plus one SMILES ligand per call,
   `num_poses` 1–4.
3. **Score** at most three candidates with `boltz2` — noting the portable
   runtime takes protein polymers with MSA only; treat any affinity output as
   a prediction, and never present docking confidence, QED, pIC50 or P(bind)
   as efficacy, toxicity or clinical evidence.

Report every step and artifact through the shared
`scientific-gateway` lifecycle (one idempotency key per logical request;
poll; download artifacts; acknowledge last). If a step's model is absent from
discovery, report it instead of substituting a different model.
