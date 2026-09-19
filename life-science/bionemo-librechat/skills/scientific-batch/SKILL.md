---
name: scientific-batch
description: Run structure and binder-design models on the scientific batch lane (alphafold3, openfold3-openbind, protenix-v2, esmfold2, esmfold2-fast, proteina-complexa, bindcraft, boltzgen, mosaic, rfdiffusion).
license: Apache-2.0 AND CC-BY-4.0
---

# scientific batch lane

Models: `alphafold3`, `openfold3-openbind`, `protenix-v2` (complex-structure
prediction), `esmfold2`, `esmfold2-fast` (monomer structure), 
`proteina-complexa`, `bindcraft`, `boltzgen`, `mosaic` (binder design),
`rfdiffusion` (`design-backbone`, `scaffold-motif`). Shared rules:
`scientific-gateway` (batch section is mandatory reading). Keep
`openfold3` (native) and `openfold3-openbind` (batch) distinct; preserve the
exact deployed ESMFold/Mosaic runtime identities from discovery rather than
publication names.

## How to submit

1. For a known model, read its live `get_model_schema` directly, including
   `input_artifact_contract`, parameter schema, allowed operation and examples.
   Use exact registered tool names. Do not inspect implementation source or
   load unrelated catalogs to discover a known contract.
2. Whole studies use `run_scientific_workflow_mcp_environment-execution` with
   inline `study` OR existing `plan_file` containing `scientific-workflow/v2`.
   Get only needed phase schemas/output filenames from
   `describe_scientific_workflow_mcp_environment-execution`. The batch phase
   takes real mounted source/parameter files and exact published entry metadata;
   the existing client hashes/uploads/finalizes bytes and constructs the outer
   manifest. No manual handles, copied base64, invented hashes or parallel
   reservation calls are needed. Workspace supports authenticated file upload.
3. Include preparation, dependent model inputs, analysis and final report in
   the immutable study. Longer plans/scripts can be written in bounded logical
   pieces and submitted by path. The supervisor serializes calls and completes
   declared phases after disconnect; no mechanical continuation is required.
   Keep original idempotency keys and settings. A pending study is not completed
   analysis. Direct model tools remain available for supported standalone calls.
4. Successful batch phases publish `output-manifest.json`, `result.json` and
   `output-NN.artifact` siblings. Roles, MIME, compression and hashes are in the
   manifest. Use these exact filenames in `{step,file}` dependencies. Native
   phases publish `result.json`. Do not interpret an artifact index as a seed.

RFdiffusion `design-backbone` is unconditional: its published `text/plain`
source is a human-readable provenance note describing the design, not a PDB,
executable constraint language or guessed JSON. The runtime uses the typed
parameters (`contigs`, `num_designs`, `seed`, `diffuser_T`). Preserve user
settings; any chosen published default must be labelled as a default.
`scaffold-motif` has a different published input contract; never substitute it.

For dependent protein studies, `proteinmpnn-input.chain` and
`design-refold-correspondence.prediction_chain` accept an exact chain ID or an
explicit `{selection:"sole-protein-chain"}`. The latter inspects actual returned
coordinates, records the ID and fails on zero/multiple protein chains; it does
not guess A. The structure phase may derive chain pairs from the already
hash-bound residue map, while still validating both structure hashes and every
position. Multi-chain biological choices remain explicit.

## Result conventions

Structures arrive as mmCIF/PDB artifacts with confidence documents; designs
arrive as sequences/structures per the model schema. Binder-design scores from
different tools are not numerically comparable across model families. Treat
all outputs as research predictions requiring experimental validation. Live
verification status per model: readiness report (explicitly not yet
live-tested at adaptation time).
