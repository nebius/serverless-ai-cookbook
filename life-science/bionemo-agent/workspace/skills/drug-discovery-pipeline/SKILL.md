---
name: drug-discovery-pipeline
description: Run the bounded GenMol to DiffDock to Boltz2 research workflow with bionemo_drug_discovery.
license: Apache-2.0 AND CC-BY-4.0
---

# Drug discovery pipeline

After confirming the public/synthetic target, inline target PDB, target protein
sequence, SAFE seed, and request count, call `bionemo_drug_discovery`. It
generates a small QED-ranked set with GenMol, docks a capped shortlist with
DiffDock, and affinity-scores at most three candidates with Boltz2. Report each
step and all artifacts. QED, docking confidence, pIC50, and P(bind) are model
outputs—not evidence of efficacy, toxicity, or clinical suitability.
