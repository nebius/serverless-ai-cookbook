---
name: boltz2-nim
description: Predict research biomolecular structures and optional ligand affinity through the bounded bionemo_boltz2 NVIDIA-hosted tool.
license: Apache-2.0 AND CC-BY-4.0
---

# Boltz2 NIM (hosted, bounded)

Use `bionemo_boltz2` for protein/DNA/RNA polymers and optional SMILES or CCD
ligands. Keep diffusion samples at 1 for event use. Only one ligand may request
affinity. Report structure-confidence fields and affinity as model predictions,
not biological truth. Return the generated mmCIF/PDB and JSON artifact links.
The task-owned adapter accepts only the pinned hosted route, up to 12 polymers,
20 ligands, 4096 residues per polymer, and 3 diffusion samples.
