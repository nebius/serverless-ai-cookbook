---
name: protein-binder-design
description: Run one bounded RFdiffusion to ProteinMPNN to structure-verification binder workflow with the scientific gateway skills and tools.
license: Apache-2.0 AND CC-BY-4.0
---

# Protein binder design workflow

Compose the gateway skills yourself — there is no bundled pipeline tool.
Before starting, confirm the legitimate research target, target chain,
epitope/hotspots, contig/pdbnn chain conventions, and verification model.
Decline designs intended to enhance pathogens, toxins, or other harmful
biological functions.

1. **Backbone** with batch `rfdiffusion` (`scientific-batch`): upload target
   PDB, submit `operation: "design-backbone"` (or `scaffold-motif`) as a real
   run document with this customer's artifact IDs.
2. **Sequence** with `proteinmpnn` native: feed the designed backbone PDB,
   `num_seq_per_target` up to 8, low `sampling_temp` for conservative designs.
3. **Verify** by folding the designed binder with the target using batch
   `alphafold3`/`openfold3-openbind`/`protenix-v2` or native `boltz2`/`openfold3`
   per their contracts.

Report every step and artifact through the shared `scientific-gateway`
lifecycle (one idempotency key per logical request; poll; download; acknowledge
last). This workflow does not compute self-consistency RMSD or prove binding:
expert review, negative controls, and wet-lab validation are required.
