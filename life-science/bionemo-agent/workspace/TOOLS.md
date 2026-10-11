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

When the hosted MCP backend is selected, the thirteen direct-only tools above
are hidden and the four backend-neutral composed workflows remain available.
Those wrappers privately submit and monitor hosted jobs; raw hosted-model MCP
operations are intentionally absent from the OpenClaw browser tool surface.
After a backend-neutral composed workflow returns a successful completed
result, call no other tool in that turn and immediately narrate the result.

Codex and Claude can connect to the same hosted gateway under the client-side
server key `bionemo_models`. When colocated with the browser launcher, its
loopback adapter exposes product-neutral operation names such as `models_list`,
`molmim_optimize`, and `job_status`, then maps those names back to the private
compatibility API. A standalone CLI connects directly under the same clean
server alias and may show the upstream compatibility operation IDs.
