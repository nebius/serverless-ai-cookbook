---
name: openfold2
description: Predict a research protein monomer structure with the openfold2 App via the infer_openfold2_native typed MCP tool. Exactly four flat fields; single-checkpoint, no external MSA/template or relaxation.
license: Apache-2.0 AND CC-BY-4.0
---

# openfold2 (native App, typed tool `infer_openfold2_native`)

Runtime variant `openfold2-upstream-portable` (HuggingFace `nz/OpenFold`,
upstream OpenFold2; single-checkpoint with one-sequence MSA representation, no
external templates or relaxation path — despite the inherited upstream endpoint
name). Call `get_model_schema` for `model_id: "openfold2"`,
`protocol: "native"` when unsure — its current schema wins over this skill.

## Flat model fields (typed tool; no wrapper)

The adapter requires **exactly** these four fields — nothing more, nothing
less:

- `input_id`: bounded identifier (letters/digits/dash/underscore).
- `sequence`: 1–1024 canonical uppercase amino acids.
- `selected_models`: exactly `[1]` (this runtime exposes parameter set 1 only).
- `relax_prediction`: exactly `false`.

Do not send MSA/template fields and do not advertise them as supported. Do not
silently substitute openfold3, alphafold3 or ESMFold for a user asking for
OpenFold2.

```json
{
  "input_id": "skill-smoke-openfold2",
  "sequence": "MKTAYIAKQRQISFVK",
  "selected_models": [1],
  "relax_prediction": false
}
```

Pass `idempotency_key` per `scientific-gateway`; leave `wait_seconds` at 0 and
poll `get_operation` / `get_operation_result`.

## Result

PDB/mmCIF structure with per-residue pLDDT and PAE matrices. Report confidence
values with their limitations and require experimental validation. Download
artifacts per the shared manual; verify hashes; call `acknowledge_operation`
only after the user has the outputs. Live-verified 2026-09-09 (sync 200,
confidence 93.22).
