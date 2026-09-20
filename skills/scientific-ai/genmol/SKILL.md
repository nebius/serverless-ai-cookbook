---
name: genmol
description: Generate research molecules from SMILES scaffolds with masked growing sites through the genmol native model.
license: Apache-2.0 AND CC-BY-4.0
---

# genmol (native)

Public model ID `genmol`; MCP typed tool `genmol_generate_native` (the server is `scientific-ai-apps`; LibreChat suffixes tool IDs). Shared rules: `scientific-gateway`.

## Payload contract (qualification clarification, 2026-09-18)

Read the current caller-authorized `genmol` schema before admission. Cached
examples do not override its exact fields or semantics.

`GenerateRequest` rejects unknown fields:

- `smiles`: SMILES string with masked growing sites written `[*{n-m}]`
  (e.g. `CC(=O)[*{1-2}]`). These bounds concern a **SAFE-mask token-length
  heuristic**, not heavy atoms. The pinned adapter takes the floored midpoint
  as the minimum token length and upstream samples from an empirical length
  distribution above it. `[*{10-20}]` therefore uses minimum15 SAFE tokens;
  neither10 nor20 defines a guaranteed atom count or maximum token count.
- `num_molecules` 1–16 (default 1), `scoring` (default `"QED"`),
  `temperature` (default 1.0), `noise` (default 1.0),
  `step_size` 1–100 (default 1), `unique` bool (default false).

```json
{"smiles": "[*{20-30}]", "num_molecules": 1}
```


## Result

Generated SMILES with score values. Treat generated molecules as research
candidates, not experimentally validated binders or drugs. QED is a molecular
property proxy, not affinity. DiffDock may support a separate, explicitly
chosen receptor/ligand pose study; protein-binder Apps are not interchangeable
small-molecule affinity tools.

Use actual saved outputs to calculate validity, canonical uniqueness, QED and
heavy-atom counts. Compute counts/frequencies in code and retain per-molecule
rows, input/result hashes, RDKit version and metric definitions. Generate a
table from those saved numbers; do not manually recount them in the narrative.
Heavy-atom minima/maxima and counts above a selected descriptive threshold are
**measurements only**. Never call them mask-constraint passes or failures:
there is no guaranteed minimum15 heavy atoms, no10–20 heavy-atom interval and
no heavy-atom upper bound implied by `[*{10-20}]`.

If the model cannot satisfy requested yield/uniqueness, preserve its structured
exhaustion outcome and returned counters. Do not silently accept an underfilled
set, change generation settings, or claim experimental validity from a
successful service response. Live verification status belongs to the dated
readiness report for the exact deployed runtime.
