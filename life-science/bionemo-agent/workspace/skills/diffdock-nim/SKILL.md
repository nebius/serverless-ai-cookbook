---
name: diffdock-nim
description: Dock a research ligand to an inline PDB through the bounded bionemo_diffdock NVIDIA-hosted tool.
license: Apache-2.0 AND CC-BY-4.0
---

# DiffDock NIM (hosted, bounded)

Use `bionemo_diffdock` with inline PDB ATOM records and a SMILES, SDF, or MOL2
ligand. Request no more than 20 poses and never request trajectories. Rank poses
with `position_confidence`; this is confidence, not binding affinity. Return SDF
and JSON artifact links and recommend orthogonal scoring and experimental
validation.
