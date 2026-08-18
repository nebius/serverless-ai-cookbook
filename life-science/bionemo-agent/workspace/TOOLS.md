# Tool boundary

The workbench plugin has exactly eighteen clean tools:

- Atomic NIM tools: `bionemo_boltz2`, `bionemo_diffdock`, `bionemo_evo2`,
  `bionemo_genmol`, `bionemo_molmim`, `bionemo_msa_search`,
  `bionemo_openfold2`, `bionemo_openfold3`, `bionemo_proteinmpnn`, and
  `bionemo_rfdiffusion`.
- Composed workflows: `bionemo_drug_discovery`,
  `bionemo_msa_to_structure`, and `bionemo_protein_binder_design`.
- Four backend-neutral composed workflows: `bionemo_research_drug_demo`,
  `bionemo_compare_protein_structures`, `bionemo_optimize_ligand_complex`, and
  `bionemo_batch_fold_demo`. They use the configured NVIDIA or BioNeMo MCP
  backend. The research demo can optionally start with bounded Tavily research.
- One read-only model inventory tool: `bionemo_models_list`. It returns only
  sanitized model identities, families, and readiness, and never submits a
  model job or exposes routes or credentials.

When MCP is configured, the browser also materializes `bionemo_models` with 24
product-neutral operations: all 17 compute contracts covering the 16 inventory
services, plus bounded inventory/description, upload, status, and fetch helpers.
Examples include `bionemo_models__alphagenome_predict`,
`bionemo_models__esm2_embed`, `bionemo_models__deepvariant_call`, and
`bionemo_models__scanvi_fit_transform`. The adapter supplies the private
request envelope and per-turn idempotency key. It does not expose `jobs_list`,
host-local path staging, credentials, or upstream `clawbio_*` names.

All requests are validated by task-owned adapters, bounded by timeout and size
limits, and saved under an isolated artifact root. `bionemo_molmim`,
`bionemo_openfold2`, `bionemo_openfold3`, and the four backend-neutral composed
workflows use the configured NVIDIA or MCP backend. The remaining seven atomics
and three direct workflows use fixed NVIDIA routes and are hidden without an
NVIDIA credential; the corresponding cluster services remain available through
their `bionemo_models__*` MCP tools. No general-purpose execution tool is enabled.

After a compute submission, never submit it again in the same turn. Poll only
the exact returned job through `bionemo_models__job_status`, at most four times.
After a successful completed result, call no other tool in that turn and
immediately narrate the result.

OpenClaw, Codex, and Claude connect to the same hosted gateway under the server
key `bionemo_models`. When colocated with the browser launcher, its loopback
adapter exposes product-neutral operation names such as `models_list`,
`molmim_optimize`, and `job_status`, then maps those names back to the private
compatibility API.
