---
name: openfold3-nim
description: Predict research biomolecular complexes through the bounded bionemo_openfold3 NVIDIA-hosted tool.
license: Apache-2.0 AND CC-BY-4.0
---

# OpenFold3 NIM (hosted, bounded)

Use `bionemo_openfold3` with exactly one input containing up to 32 protein,
DNA, RNA, or ligand molecules. Each molecule is bounded to 4096 residues and 3
diffusion samples. Discuss pLDDT, pTM, ipTM, and confidence only when returned.
The pinned upstream toolkit notes that hosted-route availability may vary; if
unavailable, report that fact and do not substitute a model. Return structure
and JSON artifacts.
