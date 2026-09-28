---
name: rfdiffusion-nim
description: Generate research protein backbones through the bounded bionemo_rfdiffusion NVIDIA-hosted tool.
license: Apache-2.0 AND CC-BY-4.0
---

# RFdiffusion NIM (hosted, bounded)

Use `bionemo_rfdiffusion` with inline PDB content, a bounded contig DSL, and
optional chain-residue hotspots such as `A50`. Diffusion steps are capped at
50. A generated backbone is not a final protein: hand it to ProteinMPNN and
then validate the complex. Return PDB and JSON artifacts. Decline harmful
pathogen/toxin enhancement use.
