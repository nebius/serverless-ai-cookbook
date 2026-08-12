# Tool boundary

The direct NVIDIA backend has exactly thirteen scientific tools:

- Atomic NIM tools: `bionemo_boltz2`, `bionemo_diffdock`, `bionemo_evo2`,
  `bionemo_genmol`, `bionemo_molmim`, `bionemo_msa_search`,
  `bionemo_openfold2`, `bionemo_openfold3`, `bionemo_proteinmpnn`, and
  `bionemo_rfdiffusion`.
- Composed workflows: `bionemo_drug_discovery`,
  `bionemo_msa_to_structure`, and `bionemo_protein_binder_design`.

All requests are validated by task-owned adapters, sent only to
`https://health.api.nvidia.com`, bounded by timeout and size limits, and saved
under an isolated artifact root. No general-purpose execution tool is enabled.

When the `clawbio_*` MCP tools are present, they are the selected BioNeMo
backend and the direct tools above are hidden. Follow their displayed flat
schemas: pass request fields at the top level, use native JSON arrays and
objects, and include only required `ack_*` booleans after explicit acceptance.
The local adapter creates the remote request envelope and idempotency key.
Each submission tool may be called only once per user request. After a job ID
is returned, poll only `clawbio_job_status` for that exact ID, at most four
times; never resubmit or search/list jobs while waiting. Report a still-running
job's exact ID and current status so it can be continued in a later turn.
