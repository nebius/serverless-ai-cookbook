---
name: evo2
description: Generate bounded research DNA continuations with the evo2-40b native model.
license: Apache-2.0 AND CC-BY-4.0
---

# evo2 (native)

Public model ID `evo2-40b`; MCP `generate_dna_native` or `invoke_model`
(`model_id: "evo2-40b"`, `protocol: "native"`). Shared rules:
`scientific-gateway`.

## Payload contract

The deployed evo2 runtime generates DNA continuations from a prompt sequence.
Exact field names and bounds were being pinned from the deployed adapter at
adaptation time — run discovery, then send the smallest valid prompt and read
the 400/422 detail before constructing larger requests. Do not assume
`prompt`/`context`/`n` field names or upstream NIM defaults. Confirm the
advertised operation name (discovery shows a single native operation) before
submitting.

## Result

Continued DNA sequence text. Present outputs as research sequence generation,
not functional genomics claims. Live verification status: readiness report
(explicitly not yet live-tested for the exact payload contract).
