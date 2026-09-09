---
name: protein-binder-design
description: Run one bounded RFdiffusion to ProteinMPNN to OpenFold3 or Boltz2 binder workflow with bionemo_protein_binder_design.
license: Apache-2.0 AND CC-BY-4.0
---

# Protein binder design workflow

Before calling `bionemo_protein_binder_design`, confirm the legitimate research
target, target chain, epitope/hotspots, contig, binder chain, and validation
model. The bounded workflow creates one RFdiffusion backbone, designs four
ProteinMPNN sequences, excludes native/WT rows, and co-folds the first designed
sequence with OpenFold3 or Boltz2. Report every step and artifact. This event
workflow does not calculate self-consistency RMSD or prove binding; expert
review, negative controls, and wet-lab validation are required. Decline designs
intended to enhance pathogens, toxins, or other harmful biological functions.
