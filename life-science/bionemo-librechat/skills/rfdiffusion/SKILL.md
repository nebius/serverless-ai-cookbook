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
come from the model's deployed parameter schema (`catalog/runtime/schema/` in
the operator solutions source — resolve it, do not guess). Input target PDB
must be uploaded by this customer first; reference the returned immutable
artifact in `input_manifest`. Suggested `service_class: "customer-batch"`
unless the key grants otherwise.

## Result

Designed backbone PDB/mmCIF artifacts. Chain into `proteinmpnn` (sequence
design) and a structure model (verification) per `protein-binder-design`.
Backbones are research hypotheses, not binders. Live verification status:
readiness report (explicitly not yet live-tested).
