# Tool boundary

The workbench plugin has exactly seventeen scientific tools:

- Atomic NIM tools: `bionemo_boltz2`, `bionemo_diffdock`, `bionemo_evo2`,
  `bionemo_genmol`, `bionemo_molmim`, `bionemo_msa_search`,
  `bionemo_openfold2`, `bionemo_openfold3`, `bionemo_proteinmpnn`, and
  `bionemo_rfdiffusion`.
- Composed workflows: `bionemo_drug_discovery`,
  `bionemo_msa_to_structure`, and `bionemo_protein_binder_design`.
- Four backend-neutral composed workflows: `bionemo_research_drug_demo`,
  `bionemo_compare_protein_structures`, `bionemo_optimize_ligand_complex`, and
  `bionemo_batch_fold_demo`. They use the configured NVIDIA or Cerebrium MCP
  backend. The research demo can optionally start with bounded Tavily research.

All requests are validated by task-owned adapters, bounded by timeout and size
limits, and saved under an isolated artifact root. Direct model calls go only
to `https://health.api.nvidia.com`; backend-neutral workflows instead use the
configured native MCP upstream when MCP mode is selected. No general-purpose
execution tool is enabled.

When the `clawbio_*` MCP tools are present, they are the selected BioNeMo
backend and the thirteen direct-only tools above are hidden; all four
backend-neutral composed workflows remain available. Follow MCP tools' displayed flat
schemas: pass request fields at the top level, use native JSON arrays and
objects, and include only required `ack_*` booleans after explicit acceptance.
After a backend-neutral composed workflow returns a successful completed
result, call no other tool in that turn and immediately narrate the result.
The local adapter creates the remote request envelope and idempotency key.
Each submission tool may be called only once per user request. After a job ID
is returned, poll only `clawbio_job_status` for that exact ID, at most four
times; never resubmit or search/list jobs while waiting. Report a still-running
job's exact ID and current status so it can be continued in a later turn.

The read-only MCP catalog tool has the stable OpenClaw-qualified name
`clawbio_models__models_list`. The local adapter maps it to the upstream
catalog operation; all compute-tool names are unchanged.
