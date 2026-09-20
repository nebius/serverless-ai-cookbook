---
name: drug-discovery-pipeline
description: Generate molecules with GenMol and dock a bounded shortlist with DiffDock; explain why the hosted protein-only Boltz2 adapter cannot score ligand affinity.
license: Apache-2.0 AND CC-BY-4.0
---

# Drug discovery pipeline

Use the durable study workflow when installed, with an explicit candidate cap:

1. **Generate** with `genmol`: a real SMILES scaffold with masked growing
   sites `[*{n-m}]` (never placeholder masks such as `SAFE_1`), `num_molecules`
   1–16, `unique: true`.
2. **Dock** a capped shortlist with `diffdock`: inline target PDB bytes
   (40 B–2 MB with `ATOM` records) plus one SMILES ligand per call,
   `num_poses` 1–4.
3. **Analyze** saved ligand structures and docking results using the installed
   docking analysis/report phases. The current `boltz2` App accepts protein
   polymers with explicit A3M only: it does **not** accept ligands or provide
   this affinity-scoring stage. Do not send docking candidates to it, discard
   ligand fields to make a request pass, or fabricate affinity. If affinity is
   required, report this capability gap and obtain an explicitly supported
   alternative before running that stage. Never present docking confidence,
   QED, pIC50 or P(bind) as efficacy, toxicity or clinical evidence.

Report every step and artifact through the shared
`scientific-gateway` lifecycle (one idempotency key per logical request;
poll; download artifacts; acknowledge last). If a step's model is absent from
discovery, report it instead of substituting a different model.
