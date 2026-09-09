---
name: boltz2
description: Predict research protein structures with the boltz2 native model on the scientific gateway (operation predict). Protein polymers with MSA only; no ligands on the qualified portable runtime.
license: Apache-2.0 AND CC-BY-4.0
---

# boltz2 (native, operation `predict`)

Applies to public model ID `boltz2`, runtime variant `boltz2-hf-portable`
(HuggingFace `boltz-community/boltz-2`, independent portable runtime; NIM
artifact parity is not claimed). Native protocol only. MCP:
`boltz2_predict_native` or `invoke_model` with `model_id: "boltz2"`,
`protocol: "native"`, and the inner payload below.

## Payload contract (verified against the deployed adapter, 2026-09-09)

- `polymers`: 1–8 items; each `id` (1–8 alnum chars), `molecule_type` must be
  `"protein"`, `sequence` 6–2048 canonical uppercase amino acids, and a
  required MSA: `msa.msa_search.a3m.alignment` (3 B–32 MB A3M text).
- Unknown fields are rejected (`extra=forbid`). There is **no** ligand, DNA/RNA,
  CCD, or `use_msa_server` support on this runtime — do not promise them.
- Optional: `recycling_steps` 1–10 (default 3), `sampling_steps` 1–500
  (default 200), `diffusion_samples` 1–8 (keep 1 for interactive use),
  `output_format` is fixed `"mmcif"`.
- The single-query alignment below is a smoke fixture; a real MSA workflow must
  use the customer's own A3M (see `msa-search` to produce one).

```json
{
  "operation": "predict",
  "payload": {
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
    ]
  }
}
```

## Result

Structure artifact in mmCIF plus per-polymer confidence fields
(pLDDT/PAE-style). Report confidences and any affinity as model predictions,
not biological truth. Download artifacts via the shared manual, verify hashes,
and never copy base64/mmCIF payloads into chat or tool arguments. An upstream
400/422 can be an execution error, not only a schema error — inspect detail
before correcting input. Live verification status: see the readiness report.
