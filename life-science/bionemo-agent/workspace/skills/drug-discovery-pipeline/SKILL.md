---
name: drug-discovery-pipeline
description: Run the bounded GenMol to DiffDock to Boltz2 research workflow with bionemo_drug_discovery.
license: Apache-2.0 AND CC-BY-4.0
---

# Drug discovery pipeline

Prefer the bundled target by calling `bionemo_drug_discovery` with
`protein_sample: "egfr_kinase_public"` and a real GenMol de novo SAFE mask such
as `safe_notation: "[*{5-10}]"`. Never invent placeholder values such as
`SAFE_1`, and never combine the bundled sample with inline PDB/sequence fields.
For another public or synthetic target, confirm its full inline PDB, matching
protein sequence, SAFE mask, and request count before calling the tool. It
generates a small QED-ranked set with GenMol, docks a capped shortlist with
DiffDock, and affinity-scores at most three candidates with Boltz2. Report each
step and all artifacts. QED, docking confidence, pIC50, and P(bind) are model
outputs—not evidence of efficacy, toxicity, or clinical suitability.
