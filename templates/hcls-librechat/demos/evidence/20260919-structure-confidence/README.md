# v57 structure delivery and source-only confidence repair

Original customer-path evidence is retained unchanged. This note does not
qualify a successor image or establish biological efficacy.

## Actual v57 outcomes

Exact workbench source `d7cf50364f80e98efa974200d33dbde7f193e6b8`, OCI index
`09406d09cbbb38937648e71708c3ecf2655d032abe933e0b18d560bdece11aa8`.
Each study used one unchanged scientific prompt, continued after the real browser
closed while running, and required no scientific follow-up or operator repair.

| Persona / study | Independent measurement | Actual delivery | Narrow outcome |
| --- | --- | --- | --- |
| 01 / `106d65f6-d44e-5824-a6ee-5fba28dd4b43` | New OpenFold2 operation `1151f5d9-79aa-4b5b-ab92-2f0c9279400b`; 76/76 mapped residues; parser-float32 RMSD 3.144016911595023 Å; confidence/request provenance checked | 5/5 Runs downloads, 306,253 bytes, exact hashes | Delivered and numerically verified for this case, not platform qualification |
| 04 / `0f57e09f-21f6-55ad-9750-fbf5b0faff1d` | New RFdiffusion→ProteinMPNN→ESM operations; exact sequence/input lineage, 48 position pairs (1 identical residue); RMSD 1.7468841544885152 Å | 14/14 Runs downloads, 219,959 bytes, exact hashes | Engine/delivery completed, requested confidence reporting incomplete |

Both reconnect checks retained an initial HTTP401. Each then used one authorized
ordinary existing-user login and verified every declared download. This is an
operator verification intervention, not a clean no-intervention UI-auth pass.
The rejected token lineage was not conclusively proven; do not label it a
product authentication defect. Current browser states were exported and browsers
closed after delivery; older HTTP cache cookies must not replace them. Persona04
also had two pre-admission composer rejections, followed by planner self-recovery
through supported inline v2 without another scientific request.

Protected receipts (relative to the unattended campaign evidence root):

- `natural-v57/scientist-01/delivery-final-r1/receipt.json`, SHA256
  `0f475e6696e1cebc0cd7e9728c8715e915e1b97b71e3a707c407f321f1d260b9`.
- `natural-v57/scientist-04/delivery-final-r1/receipt.json`, SHA256
  `cd0e47ed9ce52a9166bd6dda56e11275bcb06acd7ba2f537732348fd6da07b0c`.
- `natural-v57/scientist-04/terminal-files-r1/receipt.json`, SHA256
  `5053f690313df06f5bc03e0bbe2ec62fbf7a2c8709d61853ef265e4d4a556cd2`.

## Confirmed gap and bounded source change

The correspondence producer retained ESM's confidence JSON in its paired
`prediction-result.json`, but the planner selected coordinates alone. The
structure reader also did not recognize `plddt_mean`. The original short report
therefore said zero retained confidence fields despite a present same-operation
artifact. It remains an incomplete scientific report, not a corrected pass.

The successor source accepts explicit `structure.confidence_result` pointing to
the existing downloaded batch manifest or new paired correspondence envelope.
New correspondence results register their exact coordinate/envelope pair; only
that completed producer's same-generation step reference is carried
automatically. Direct arbitrary files, old unregistered receipts and neighboring
filenames are never automatically joined.

The original confidence JSON bytes are preserved and hash-verified against the
same manifest. Exactly one coordinate SHA256/size entry and one corresponding
versioned confidence row must match. Other samples are not averaged or selected
by rank/order/name. Scalar native values, source hash, runtime/model revision,
input identity and seed/sample labels appear in metrics and the short report.
These labels do not prove deterministic inference. Missing artifacts remain
unavailable; mismatch/ambiguity fails explicitly. Old envelopes missing the new
exact-byte field can be reassessed using their original manifest explicitly;
neither old reports nor old receipts are migrated or rewritten.

The retained04 confidence is exactly:

- `plddt_mean`: `0.720092236995697` (native scale, not multiplied by 100).
- `ptm`: `0.4071556031703949`.
- `iptm`: `0.0` (a real zero, not missing).
- Seed `1`, sample index `0`; structure SHA256
  `717539fd871d3e540aa73138215400624ae78e111af1a9c06a221b0a786d2f9f`.
- Confidence artifact SHA256
  `a8411c543d30c24f103f4e772f973284442b22acbf11f9ce442691a08eb79dc7`.

## Verification, not new acceptance

The focused five-file regression group passed 82 tests, including the optional
private original04 fixture explicitly enabled. It tests exact values/zero/native
scale, wrong/duplicate coordinate entries, absent/duplicate/mismatched sample
rows, nonfinite/boolean metrics, tampered/missing source bytes, manifest/envelope
paths, immutable file references, same-generation automatic pairing, no direct
file discovery, and unchanged geometry/mapping. One initial broader run had a
stale test double missing the already-existing `NATIVE_OPTIONAL` field; the
fixture was corrected, with that initial failure retained.

Commands from `templates/hcls-librechat`:

```sh
SCIENTIFIC_RETAINED_V57_04=/retained-v57-04 python -m pytest -q \
  test_structure_bound_confidence.py test_structure_confidence_study.py \
  test_structure_analysis.py test_structure_native_confidence.py \
  test_scientific_protein_preparation.py
```

Without the private fixture mount, its single test is explicitly skipped, not
called a retained-artifact pass. The new tests use generated coordinates for
portable negative cases; customer payloads are not in Git.

Separate actual-source replay reran correspondence plus structure analysis from
the exact archived04 inputs, with model transport prohibited. It reproduced all
three confidence values through automatic registered pairing while retaining
the identical RMSD, chain metrics and residue-map bytes. All 186 original files
were rehashed unchanged. Protected receipt
`v58-confidence-original04-replay-r1/receipt.json`, SHA256
`ae4c6ebecd7b9b4c01df914cd4201a550d9e95a459290c18beda891450cdac8c`.
This is zero-inference offline source proof only; a new installed/runtime and
natural-client cohort is still required for a successor claim.
