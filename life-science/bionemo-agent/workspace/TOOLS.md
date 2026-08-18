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

When MCP is configured, the browser also materializes `bionemo_models` with 25
product-neutral operations: all 17 compute contracts covering the 16 inventory
services, plus inventory/description, resumable upload, cross-job listing,
status, and fetch helpers. The upstream host-local path-staging operation is not
displayed because its path would not refer to this owner container.
Examples include `bionemo_models__alphagenome_predict`,
`bionemo_models__esm2_embed`, `bionemo_models__deepvariant_call`, and
`bionemo_models__scanvi_fit_transform`. For compute submissions, the adapter
supplies the private request envelope and per-turn idempotency key. It
product-renames upstream operations and does not expose upstream `clawbio_*`
names.

All requests are validated by task-owned adapters, bounded by timeout and size
limits, and saved under an isolated artifact root. `bionemo_molmim`,
`bionemo_openfold2`, `bionemo_openfold3`, and the four backend-neutral composed
workflows use the configured NVIDIA or MCP backend. The remaining seven atomics
and three direct workflows use fixed NVIDIA routes and are hidden without an
NVIDIA credential; the corresponding cluster services remain available through
their `bionemo_models__*` MCP tools. These scientific contracts coexist with
the general-purpose container-admin tools below.

## Owner-admin tools

This private image enables OpenClaw's full tool profile. The agent process and
the Control UI operator terminal run as root inside the container,
with sandbox mode off and exec approvals set to full/no-prompt. Available
general-purpose capabilities include:

- `exec` and `process` for shell commands, background jobs,
  Python, and other interpreters;
- `read`, `write`, `edit`, and `apply_patch` without a workspace-only path
  restriction;
- browser, web, session, subagent, automation, gateway, memory, media, and node
  tools from the full OpenClaw policy profile when their required runtime or
  external service is configured;
- `apt`, `pip`, `uv`, `npm`, and the normal root-owned system paths for installing
  additional tooling at runtime.

These admin tools complement the typed scientific tools; they do not relax the
acknowledgement, exact-once submission, job-polling, or research-only contracts
for BioNeMo compute.

After a compute submission, never submit it again in the same turn. Poll only
the exact returned job through `bionemo_models__job_status`, at most four times.
After a successful completed result, call no other tool in that turn and
immediately narrate the result.

OpenClaw, Codex, and Claude connect to the same hosted gateway under the server
key `bionemo_models`. When colocated with the browser launcher, its loopback
adapter exposes product-neutral operation names such as `models_list`,
`molmim_optimize`, and `job_status`, then maps those names back to the private
compatibility API.
