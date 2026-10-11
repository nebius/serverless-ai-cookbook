---
name: proteinmpnn-nim
description: Design research protein sequences for an inline backbone through the bounded bionemo_proteinmpnn NVIDIA-hosted tool.
license: Apache-2.0 AND CC-BY-4.0
---

# ProteinMPNN NIM (hosted, bounded)

Use `bionemo_proteinmpnn` with inline PDB content. Specify chains to redesign
for complexes, keep `sampling_temp` as a list, and request at most 20 sequences.
Exclude native/WT FASTA rows when pairing returned scores with designs. Return
FASTA and JSON artifacts. Recommend co-folding, structural review, and wet-lab
testing.
