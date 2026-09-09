---
name: genmol
description: Generate research molecules from SMILES scaffolds with masked growing sites through the genmol native model.
license: Apache-2.0 AND CC-BY-4.0
---

# genmol (native)

Public model ID `genmol`; MCP typed tool `genmol_generate_native` (the server is `bionemo-models`; LibreChat suffixes tool IDs). Shared rules: `scientific-gateway`.

## Payload contract (verified against the deployed adapter, 2026-09-09)

`GenerateRequest` rejects unknown fields:

- `smiles`: SMILES string with masked growing sites written `[*{n-m}]`
  (e.g. `CC(=O)[*{1-2}]`).
- `num_molecules` 1–16 (default 1), `scoring` (default `"QED"`),
  `temperature` (default 1.0), `noise` (default 1.0),
  `step_size` 1–100 (default 1), `unique` bool (default false).

```json
{"smiles": "[*{20-30}]", "num_molecules": 1}
```


## Result

Generated SMILES with score values. Treat generated molecules as research
candidates requiring downstream docking/affinity evaluation (`diffdock`,
batch `bindcraft`/`boltzgen`). Live verification status: readiness report.
