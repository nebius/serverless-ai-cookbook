---
name: openfold3
description: Predict research biomolecular structures with the openfold3 native model (mmCIF output; optional MSA per molecule).
license: Apache-2.0 AND CC-BY-4.0
---

# openfold3 (native)

Public model ID `openfold3`; MCP `infer_openfold3_native` or `invoke_model`
(`model_id: "openfold3"`, `protocol: "native"`). Keep this distinct from the
batch model `openfold3-openbind` (different runtime and request document; see
that skill).

## Payload contract (verified against the deployed adapter parser, 2026-09-09)

Each input item must have exactly `input_id`, `output_format: "cif"` and
`molecules`:

- molecule allowed keys: `type`, `id`, `sequence`, `diffusion_samples`, `msa`;
- protein `sequence` must be nonempty canonical amino acids;
- optional `msa` switches the runtime's `use_msas` behavior;
- seeds are platform-fixed (42) — do not send seed fields.

```json
{
  "operation": "predict-complex-structure",
  "payload": {
    "input_id": "skill-smoke-openfold3",
    "output_format": "cif",
    "molecules": [
      { "type": "protein", "id": "A", "sequence": "MKTAYIAKQRQISFVK" }
    ]
  }
}
```

(Confirm the advertised operation name from discovery.)

## Result

mmCIF structure with confidence scores (`confidence_score`, `complex_plddt`,
`ptm`, `iptm` variants as rendered by the adapter). Report scores as model
predictions. Multi-chain complexes follow the same molecules list. Live
verification status: readiness report.
