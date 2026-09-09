---
name: diffdock
description: Dock a research ligand to a protein structure with the diffdock native model (inline PDB bytes plus SMILES).
license: Apache-2.0 AND CC-BY-4.0
---

# diffdock (native)

Public model ID `diffdock`; MCP `infer_diffdock_native` or `invoke_model`
(`model_id: "diffdock"`, `protocol: "native"`). See `scientific-gateway` for
auth, idempotency, polling and artifacts.

## Payload contract (verified against the deployed adapter, 2026-09-09)

Allowed fields only (`extra` rejected):

- `protein`: 40 B–2 MB UTF-8 PDB text containing `ATOM` records (inline bytes,
  not a path or artifact reference).
- `ligand`: 1–4096 character SMILES string.
- `ligand_file_type`: only `"txt"` (inline SMILES) is supported.
- `num_poses` 1–4 (default 1), `time_divisions` 3–20 (default 20),
  `steps` 1–20 (default 18, `steps <= time_divisions`),
  `random_seed` 1–2^31-1 (default 1).
- `save_trajectory` and `skip_gen_conformer` are rejected by the bounded API.

```json
{
  "operation": "predict",
  "payload": {
    "protein": "ATOM  ...PDB records...",
    "ligand": "CC(=O)OC1=CC=CC=C1C(=O)O",
    "num_poses": 1
  }
}
```

(Use the advertised operation from discovery; confirm it is `predict` before
submitting.)

## Result

Ranked poses with confidence scores and pose structures as artifacts. Docking
scores are model predictions; do not compare them numerically to AutoDock
scores. Download poses via the shared manual and hand the user artifact
references, never inline file dumps. Live verification status: readiness report.
