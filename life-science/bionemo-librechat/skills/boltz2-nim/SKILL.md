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

After a successful job, do not call `clawbio_model_fetch` or copy an mmCIF,
PDB, JSON, or base64 payload into a tool argument. Call `bionemo_json_summary`
for confidence and affinity values. Call `bionemo_artifact_download` for the
structure, then pass its returned `structure_path` to `protein_viewer`.
