---
name: proteinmpnn
description: Design research protein sequences for an inline PDB backbone with the proteinmpnn native model.
license: Apache-2.0 AND CC-BY-4.0
---

# proteinmpnn (native)

Public model ID `proteinmpnn`; MCP `infer_proteinmpnn_native` or
`invoke_model` (`model_id: "proteinmpnn"`, `protocol: "native"`). Shared
lifecycle rules: `scientific-gateway`.

## Payload contract (verified against the deployed adapter, 2026-09-09)

Allowed fields only:

- `input_pdb`: 40 B–2 MB UTF-8 PDB text containing `ATOM` records (inline).
- `input_pdb_chains`: optional list of 1–16 one-character chain IDs to design.
- `num_seq_per_target` 1–8 (default 1).
- `sampling_temp`: number or single-element list (default 0.1; lower is more
  conservative).
- `random_seed` 1–2^31-1 (default 1).
- `omit_AAs`: optional amino acids to exclude from design.

```json
{
  "operation": "sequence-design",
  "payload": {
    "input_pdb": "ATOM  ...PDB records...",
    "num_seq_per_target": 2,
    "sampling_temp": 0.1
  }
}
```

(Confirm the advertised operation name from discovery before submitting.)

## Result

Designed sequences per requested chain with per-position log-probabilities.
Sequences are research suggestions; validation by structure prediction
(`openfold2`/`boltz2`) is recommended before synthesis. Live verification
status: readiness report.
