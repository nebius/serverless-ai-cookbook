---
name: protein-binder-design
description: Run one bounded RFdiffusion to ProteinMPNN to structure-verification binder workflow with the scientific gateway skills and tools.
license: Apache-2.0 AND CC-BY-4.0
---

# Protein binder design workflow

Use the installed durable scientific study workflow for orchestration when
available; it does not make incompatible scientific inputs interchangeable.
For multi-candidate or multi-model campaigns also read `binder-design-campaigns`.
Before starting, confirm the legitimate research target, target chain,
epitope/hotspots, contig/pdbnn chain conventions, and verification model.
Decline designs intended to enhance pathogens, toxins, or other harmful
biological functions.

1. **Backbone** with batch `rfdiffusion` (`scientific-batch`): `design-backbone`
   is unconditional and takes a text/plain provenance note, not a target PDB;
   its typed parameters determine the design. Target/motif-conditioned work
   must use the separately published `scaffold-motif` input contract if it
   supports the scientific request. Do not label unconditional generation as
   target-conditioned binder design. Use this customer's finalized artifacts.
2. **Sequence** with `proteinmpnn` native: feed the designed backbone PDB,
   `num_seq_per_target` up to 8, low `sampling_temp` for conservative designs.
3. **Verify** by folding the designed binder with the target using batch
   `alphafold3`/`openfold3-openbind`/`protenix-v2` or native `boltz2`/`openfold3`
   per their contracts.

Report every step and artifact through the shared `scientific-gateway`
lifecycle (one idempotency key per logical request; poll; download; acknowledge
last). The installed structure/design analysis phases can measure aligned RMSD
and contacts with explicit chains and residue correspondence. Those measurements
do not prove binding: expert review, negative controls and experimental
validation remain necessary.
