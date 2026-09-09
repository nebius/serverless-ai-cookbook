---
name: molmim
description: Optimize or sample research molecules around a SMILES seed with the molmim native model (CMA-ES, QED objective).
license: Apache-2.0 AND CC-BY-4.0
---

# molmim (native)

Public model ID `molmim`; MCP `molmim_run_native` or `invoke_model`
(`model_id: "molmim"`, `protocol: "native"`). Shared rules: `scientific-gateway`.

## Payload contract (verified against the deployed adapter, 2026-09-09)

`GenerateRequest` rejects unknown fields:

- `smi`: seed SMILES, 1–512 chars (tokenized against the deployed vocabulary).
- `algorithm`: fixed `"CMA-ES"`.
- `num_molecules` 1–16 (default 1), `property_name` fixed `"QED"`,
  `min_similarity` 0–1 (default 0.3), `particles` 1–32 (default 2),
  `iterations` 1–16 (default 1), `radius` 0–10 (default 1.0).

```json
{
  "operation": "generate",
  "payload": {
    "smi": "CC(=O)OC1=CC=CC=C1C(=O)O",
    "num_molecules": 4,
    "min_similarity": 0.4
  }
}
```

(Confirm the advertised operation name from discovery.)

## Result

Optimized SMILES with QED and similarity to the seed. Candidates still need
docking/affinity evaluation; do not present QED as drug-likeness proof.
Live verification status: readiness report.
