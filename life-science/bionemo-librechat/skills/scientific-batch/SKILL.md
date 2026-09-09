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

1. Discover `GET /v1/scientific-models` — each entry lists its `operations`
   and the deployed runtime identity; the per-model parameter schema is
   exposed by the operator (`catalog/runtime/schema/<model>-parameters.schema.json`
   in the solutions-library source; resolve the actual schema, never guess).
2. Prepare real inputs: upload FASTA/PDB/A3M bytes via
   `begin_scientific_artifact_upload` → `put_scientific_artifact_bytes` →
   `finalize_scientific_artifact_upload`; compute sha256/size from the actual
   bytes; build the `input_manifest` from returned immutable artifact refs.
   Fixture artifact IDs from checked-in examples are templates, never
   submissions.
3. Submit once with the named typed tool — `submit_alphafold3`,
   `submit_openfold3_openbind`, `submit_protenix_v2`, `submit_esmfold2`,
   `submit_esmfold2_fast`, `submit_proteina_complexa`, `submit_bindcraft`,
   `submit_boltzgen`, `submit_mosaic`, `submit_rfdiffusion` (LibreChat
   suffixes tool IDs) — or `submit_scientific_run` as the model-agnostic
   route. The run document fields go in **flat** (no `request` wrapper):
   `schema: "fs2-serve.nebius.ai/scientific-run-request/v1"`, `operation`
   from discovery, `service_class` your key may select — checked-in examples
   use `customer-batch`, `parameters` from the model schema, optional
   `client_context` with `batch_id`/`correlation_id`/`display_name`, plus the
   optional `idempotency_key`. For `rfdiffusion`, `operation` selects
   `design-backbone` or `scaffold-motif`.
4. Follow with `get_scientific_status` / `list_scientific_events`, then
   `get_scientific_result`; download artifacts and verify hashes; acknowledge
   only after the user has outputs.

## Result conventions

Structures arrive as mmCIF/PDB artifacts with confidence documents; designs
arrive as sequences/structures per the model schema. Binder-design scores from
different tools are not numerically comparable across model families. Treat
all outputs as research predictions requiring experimental validation. Live
verification status per model: readiness report (explicitly not yet
live-tested at adaptation time).
