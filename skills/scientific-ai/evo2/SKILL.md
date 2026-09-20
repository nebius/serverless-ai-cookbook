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
not functional genomics claims. The example is a synthetic schema example,
not a claim of successful execution or functional biological validation.

## Durable continuation analysis

For a bounded multi-window study, declare the whole inference→analysis→report
plan before starting it. Use the typed `evo2-continuation` analysis method in
the discovered scientific workflow contract rather than writing a one-off
sequence/CSV parser. Provide the actual reference file and explicit cases with
`id`, `start_zero_based`, `input_file`, `result_file`, and `operation_file`.
Use dependency file references for results that the preceding native phases
will publish. Keep original sampling settings and seeds in the saved requests.

The packaged `/opt/hcls-librechat/sequence-analysis.py --plan PLAN --output-dir OUT`
uses the same contract. A reference may be plain DNA or FASTA; multi-record
FASTA requires `reference_id`. Default `sequence_mode: suffix` matches the
current Evo2 raw result `sequence` field: it contains newly generated bases,
not the original prompt. Only explicitly declare `prefix-and-suffix` for a
source known to return both; never strip a coincidentally matching sequence.

The helper publishes `metrics.json`, `rows.csv`, `report.md` and a verified
`completion-manifest.json`. It checks the original prefix against its declared
reference window, preserves every returned suffix (including non-ACGT symbols,
underfill and poor reference agreement), measures GC with explicit denominators,
and compares only identical windows/sampling controls. Actual operation IDs
come from saved operation envelopes, not raw sequence results. Model
`elapsed_ms` is milliseconds; its seconds field divides by1000. Operation wall
intervals are distinct from model time, cold-start time and GPU occupancy.

First discover the deployed App schema. If logits or sampled probabilities are
disabled, say likelihood/variant-effect scoring is unavailable; do not rename
generation as scoring. Any genuinely returned probabilities retain their
original sampling meaning. Reference agreement and two-seed differences are
descriptive, not gene-function, variant-effect, training-data independence or
full-paper benchmark validation. A helper completion manifest proves measured
file publication, not successful biology or a completed inference study.
