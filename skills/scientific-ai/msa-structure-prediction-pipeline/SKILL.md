---
name: msa-structure-prediction-pipeline
description: Run the bounded MSA-search to structure-prediction research workflow with the scientific gateway skills and tools.
license: Apache-2.0 AND CC-BY-4.0
---

# MSA-to-structure pipeline

Compose the gateway skills yourself — there is no bundled pipeline tool:

1. **Search** with `msa-search` (`msa-search-pdb70`): `sequence` 6–4096
   residues, `max_msa_sequences` as needed (1–5000). Retrieve the A3M
   alignment artifact and verify its hash.
2. **Fold** with MSA-aware structure prediction: `boltz2` native (nested
   `msa.msa_search.a3m.alignment`) or the batch lane MSA-capable models via
   `scientific-batch` (e.g. openfold3-openbind/protenix-v2 per their schemas).
   `openfold2` ignores external alignments by design — do not substitute it
   here unless the user explicitly accepts single-sequence folding.

Report alignment sequence count, structure confidence fields, and artifact
links per `scientific-gateway`. MSA depth and model confidence are not
experimental validation. If the search or structure model is missing from
discovery, report it without substitution.
