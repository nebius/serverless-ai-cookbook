---
name: boltz2
description: Predict research protein structures with the boltz2 App via the boltz2_predict_native typed MCP tool. Protein polymers with explicit A3M MSA only; no ligands on the portable runtime.
license: Apache-2.0 AND CC-BY-4.0
---

# boltz2 (native App, typed tool `boltz2_predict_native`)

Runtime variant `boltz2-hf-portable` (HuggingFace `boltz-community/boltz-2`,
independent portable runtime; NIM artifact parity is not claimed). Call
`get_model_schema` for `model_id: "boltz2"`, `protocol: "native"` when the
conversation has not already established the contract — its current schema and
example win over this skill.

## Flat model fields (typed tool; no `operation`/`payload` wrapper)

- `polymers` (required): 1–8 items; each `id` (1–8 alnum chars),
  `molecule_type` must be `"protein"`, `sequence` 6–2048 canonical uppercase
  amino acids, and a required MSA: `msa.msa_search.a3m.alignment` (3 B–32 MB
  A3M text).
- Optional: `recycling_steps` 1–10 (default 3), `sampling_steps` 1–500
  (default 200), `diffusion_samples` 1–8 (keep 1 for interactive use),
  `output_format` fixed `"mmcif"`.
- Unknown fields are rejected. There is **no** ligand, DNA/RNA, CCD, or
  `use_msa_server` support on this runtime — do not promise them; say so and
  point to `diffdock` or the batch Apps instead.
- The single-query alignment below is a smoke fixture; a real MSA workflow uses
  the customer's own A3M (see `msa-search`).

```json
{
  "polymers": [
    {
      "id": "A",
      "molecule_type": "protein",
      "sequence": "MKTAYIAKQRQISFVK",
      "msa": {
        "msa_search": {
          "a3m": { "alignment": ">query\nMKTAYIAKQRQISFVK\n" }
        }
      }
    }
  ],
  "diffusion_samples": 1
}
```

Pass `idempotency_key` per `scientific-gateway`; leave `wait_seconds` at 0 and
poll `get_operation` / `get_operation_result`.

## Result

Structure artifact in mmCIF plus per-polymer confidence fields. Report
confidences and any affinity as model predictions, not biological truth.
Download artifacts per the shared manual, verify hashes, and never copy
base64/mmCIF payloads into chat or tool arguments. Live-verified 2026-09-09
(operation `adff65b2-a479-42db-ba65-6b0b68c07ee0` → succeeded).
