---
name: openfold2
description: Predict a research protein monomer structure with the openfold2 native model (operation predict-structure). Exactly four payload fields; single-sequence MSA, no templates.
license: Apache-2.0 AND CC-BY-4.0
---

# openfold2 (native, operation `predict-structure`)

Applies to public model ID `openfold2`, runtime variant
`openfold2-upstream-portable` (HuggingFace `nz/OpenFold`, upstream OpenFold2;
single-sequence MSA representation, no external templates — despite the
inherited upstream endpoint name). MCP: `infer_openfold2_native` or
`invoke_model` with `model_id: "openfold2"`, `protocol: "native"`.

## Payload contract (verified against `parse_request`, 2026-09-09)

The adapter requires **exactly** these four inner fields — nothing more,
nothing less:

- `input_id`: bounded identifier (letters/digits/dash/underscore).
- `sequence`: 1–1024 canonical uppercase amino acids.
- `selected_models`: exactly `[1]` (this runtime exposes parameter set 1 only).
- `relax_prediction`: exactly `false`.

Do not send MSA/template fields and do not advertise them as supported. Do not
silently substitute openfold3, alphafold3 or ESMFold for a user asking for
OpenFold2. For MCP, the inner `payload` is the object below; supply
`model_id`/`protocol: "native"` separately.

```json
{
  "operation": "predict-structure",
  "payload": {
    "input_id": "skill-smoke-openfold2",
    "sequence": "MKTAYIAKQRQISFVK",
    "selected_models": [1],
    "relax_prediction": false
  }
}
```

## Result

PDB/mmCIF structure with per-residue pLDDT and PAE matrices. Report confidence
values with their limitations and require experimental validation. Download
artifacts per the shared `scientific-gateway` manual; verify hashes; call
acknowledge only after the user has the outputs. An upstream 400/422 can be an
adapter-mapped execution error — inspect the detail before blaming input.
Live verification status: see the readiness report.
