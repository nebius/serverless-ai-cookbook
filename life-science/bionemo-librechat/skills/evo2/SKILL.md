---
name: evo2
description: Generate bounded research DNA continuations with the evo2-40b native model.
license: Apache-2.0 AND CC-BY-4.0
---

# evo2 (native)

Public model ID `evo2-40b`; MCP `generate_dna_native` or `invoke_model`
(`model_id: "evo2-40b"`, `protocol: "native"`). Shared rules:
`scientific-gateway`.

## Flat model fields (typed tool `generate_dna_native`; verified 2026-09-09)

All nine fields are required by the deployed contract:

- `sequence`: DNA prompt text.
- `num_tokens`: continuation length to generate.
- `temperature`, `top_k`, `top_p`: sampling controls.
- `random_seed`: integer seed.
- `enable_logits`, `enable_sampled_probs`, `enable_elapsed_ms_per_token`:
  boolean output switches (logits/probs enlarge the response — keep false
  unless the user asks).

```json
{
  "sequence": "ATCGATCGATCG",
  "num_tokens": 20,
  "temperature": 0.7,
  "top_k": 1,
  "top_p": 0.0,
  "random_seed": 2407001,
  "enable_logits": false,
  "enable_sampled_probs": false,
  "enable_elapsed_ms_per_token": true
}
```

Pass `idempotency_key` per `scientific-gateway`; leave `wait_seconds` at 0 and
poll `get_operation` / `get_operation_result`.

## Result

Continued DNA sequence text. Present outputs as research sequence generation,
not functional genomics claims. Live verification status: readiness report
(contract pinned from get_model_schema; example is the schema-embedded synthetic one).
