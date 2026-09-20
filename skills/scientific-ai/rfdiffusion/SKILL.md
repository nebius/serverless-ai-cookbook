---
name: rfdiffusion
description: Generate research protein backbones or scaffold motifs with the rfdiffusion scientific batch model (operations design-backbone and scaffold-motif).
license: Apache-2.0 AND CC-BY-4.0
---

# rfdiffusion (scientific batch)

Public model ID `rfdiffusion`; MCP `submit_rfdiffusion` or
`submit_scientific_run` (`model_id: "rfdiffusion"`). Shared batch mechanics
(artifact upload, run document, polling): `scientific-batch`.

## Run document

`operation` selects `"design-backbone"` or `"scaffold-motif"`; `parameters`
come from `get_model_schema` and its `input_artifact_contract`; customers do
not need the operator's source checkout. For `design-backbone`, upload a
text/plain human-readable provenance note, not a PDB; typed `contigs`,
`num_designs`, `seed` and `diffuser_T` determine this unconditional run.
For `scaffold-motif`, follow that operation's distinct published source role
and structure contract. Reference the finalized manifest in `input_manifest`.
Suggested `service_class: "customer-batch"`
unless the key grants otherwise.

## Result

Designed backbone PDB/mmCIF artifacts. Chain into `proteinmpnn` (sequence
design) and a structure model (verification) per `protein-binder-design`.
Backbones are research hypotheses, not demonstrated binders. Check release
evidence for the exact runtime and workflow; this skill is not a live-readiness
certificate.
