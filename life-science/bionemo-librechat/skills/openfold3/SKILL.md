---
name: openfold3
description: Predict research biomolecular structures with the openfold3 native model (mmCIF output; optional MSA per molecule).
license: Apache-2.0 AND CC-BY-4.0
---

# openfold3 (native)

Public model ID `openfold3`; typed tool `infer_openfold3_native` on the
`bionemo-models` MCP server (LibreChat suffixes tool IDs). Keep this distinct
from the batch model `openfold3-openbind` (different runtime and run document;
see `scientific-batch`). Call `get_model_schema` when unsure — its live schema
and example win over this skill.

## Flat model fields (typed tool; no wrapper)

- `request_id` (required): bounded identifier for the prediction request.
- `inputs` (required): list of items, each with exactly `input_id`,
  `output_format: "cif"` and `molecules`; molecule allowed keys `type`, `id`,
  `sequence`, `diffusion_samples`, `msa`; protein `sequence` must be nonempty
  canonical amino acids. Seeds are platform-fixed — do not send seed fields.

```json
{
  "request_id": "synthetic-protein",
  "inputs": [
    {
      "input_id": "protein",
      "output_format": "cif",
      "molecules": [
        {
          "id": "A",
          "type": "protein",
          "sequence": "ACDEFGHIKLMNPQRSTVWY"
        }
      ]
    }
  ]
}
```

Pass `idempotency_key` per `scientific-gateway`; leave `wait_seconds` at 0 and
poll `get_operation` / `get_operation_result`.

## Result

mmCIF structure with confidence scores (`confidence_score`, `complex_plddt`,
`ptm`, `iptm` variants as rendered by the adapter). Report scores as model
predictions. Multi-chain complexes follow the same molecules list. Live
verification status: readiness report.
