---
name: msa-search
description: Search protein homologs and produce A3M alignments with the msa-search-pdb70 native model, ready for boltz2/openfold3 MSA inputs.
license: Apache-2.0 AND CC-BY-4.0
---

# msa-search (native)

Public model ID `msa-search-pdb70` (ColabFold MSA fallback against PDB70);
MCP `msa_search_native` or `invoke_model` (`model_id: "msa-search-pdb70"`,
`protocol: "native"`). Shared rules: `scientific-gateway`.

## Payload contract (verified against the deployed adapter, 2026-09-09)

- `sequence`: 6–4096 canonical protein residues.
- `max_msa_sequences` 1–5000 (default 500).

```json
{
  "operation": "search",
  "payload": {
    "sequence": "MKTAYIAKQRQISFVK",
    "max_msa_sequences": 500
  }
}
```

(Confirm the advertised operation name from discovery.)

## Result

An A3M alignment artifact. Feed the returned alignment text into `boltz2`
(`msa.msa_search.a3m.alignment`) or the batch structure models that accept
MSA — this is the correct wiring for the `msa-structure-prediction-pipeline`
skill. Single-query alignments are smoke fixtures only; a customer's MSA
workflow deserves the searched alignment. Live verification status: readiness
report.
