# Tool boundary

This agent has exactly thirteen scientific tools:

- Atomic NIM tools: `bionemo_boltz2`, `bionemo_diffdock`, `bionemo_evo2`,
  `bionemo_genmol`, `bionemo_molmim`, `bionemo_msa_search`,
  `bionemo_openfold2`, `bionemo_openfold3`, `bionemo_proteinmpnn`, and
  `bionemo_rfdiffusion`.
- Composed workflows: `bionemo_drug_discovery`,
  `bionemo_msa_to_structure`, and `bionemo_protein_binder_design`.

All requests are validated by task-owned adapters, sent only to
`https://health.api.nvidia.com`, bounded by timeout and size limits, and saved
under an isolated artifact root. No general-purpose execution tool is enabled.
