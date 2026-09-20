# Select one hosted contract

| App | What to preserve / check |
| --- | --- |
| `proteina-complexa` | Select the exact published `target_catalog` task ID. Tasks sharing a PDB can use different hotspots/length ranges. Upstream target/design/sweep/evaluate CLI options are not automatically exposed. |
| `boltzgen` | Use its published design specification and manifest role. Keep target entities, designed entities and constraints distinct; not the protein-only native `boltz2` App. |
| `mosaic` | Record the exact deployed implementation/version, not an assumed paper identity. Use its source bundle/config schema and retain optimization/selection metrics and failed candidates. |
| `bindcraft` | Preserve target chains, hotspots, trajectory limits and filter settings. Report no candidates passing as a result. Model access does not independently grant a PyRosetta license. |

For contracts with `parameters.source.kind: uploaded-bundle`, place
`"source":{"kind":"uploaded-bundle"}` in the parameter file alongside the
scientific settings. The existing batch client replaces it with the finalized
reference for the actual source bytes; do not invent an artifact ID. Match the
entry name, semantic type, media type and compression from the live contract.

Keep `alphafold3`, `openfold3-openbind` and `protenix-v2` verification Apps
distinct from native `openfold3`/`boltz2`. `esmfold2` and `esmfold2-fast` are
separate Apps with runtime-specific limits. Monomer refolding is not target/binder
complex prediction. RFdiffusion unconditional backbone generation is not
target-conditioned design; use its distinct motif contract for that goal.
