# Manifest-aware protein-design analysis after natural v52

The original natural PD-L1 Study completed both model operations and its four
declared phases after the browser was closed. Reconnecting Runs showed that
durable completion. Its final report was actually downloaded through Workspace:
804 bytes, SHA-256
`3aec8498851521889c5ad3c14641f926e3ce6054106ffd5c247321d13b387107`.
It contains two empty tables, not the requested scientific comparison. Both
source CSVs contain headers only (24 bytes); the analysis extracted zero fields.
This is a preserved natural scientific-delivery failure, not a successful study
because the engine reached `completed`.

## Concrete defect and source-only successor

The generated script identified content from local `output-NN.artifact` suffixes
and matched manifest entries by byte size. This ignored all actual PDB, CIF,
CSV and JSON artifacts. Its CIF branch also treated mmCIF as fixed-column PDB.
No existing report or live Study was repaired, resumed or resubmitted.

`design-artifact-analysis.py` uses the existing batch-client ABI: an exact
output manifest plus its sibling `output-NN.artifact` files. It verifies each
entry's hash and size in manifest order, parses the declared media type, and
reuses the already-qualified `qualification_evaluators` geometry and Proteina
generated/refolded provenance joins. True PDB and mmCIF parsing is tested.
CSV/JSON native values remain intact; no keyword truncation, re-ranking, changed
filter or invented rejected candidates is introduced.

```text
python design-artifact-analysis.py --manifest /workspace/run/output-manifest.json \
  --output-dir /workspace/analysis
```

Optional explicit binder chain and length bounds are `--binder-chain`,
`--binder-length-min`, `--binder-length-max`. Target checking additionally
requires both `--target-reference` and `--target-chain`. Chain IDs in an input
specification are not assumed to survive output conversion. Roles and target
matches are unknown unless supported by explicit inputs or verified provenance.
Outputs are `measurements.json`, `inventory.csv`, and `report.md`.

## Exact retained-output replay

- Proteina: 18 hash-verified artifacts, 16 coordinate outputs, eight independently
  joined generated/refolded pairs and eight unique binder sequences. Every CSV
  self-consistency RMSD agrees with independent coordinates. Both raw and refolded
  structures pass the existing coarse geometry screen, 8/8 each. Measurement
  SHA-256: `949f67e27189a53bdb51981f494c260aef95a91090b09d9cc1815bb1f08a0983`.
- BoltzGen: two published artifacts, one ranking CSV row and one actual mmCIF
  structure. The exact source target sequence uniquely matches output chain B;
  output chain A is the remaining designed protein, with 64 observed residues
  inside the original 60–80 range. Its adjacent-CA median is 3.817 Å, no adjacent
  steps outside the unchanged 2.5–4.5 Å screen, and no nonlocal CA pairs below
  2 Å. Measurement SHA-256:
  `e538fae68ace0193849ba51b6c985d7b770dbb6eb785a80acbf71330ccf377cb`.
  An earlier operator-only probe incorrectly reused input chain C; its explicit
  no-matching-chain result is retained separately, not attributed to the model.
- Twenty BoltzGen designs were requested with budget one, but only one selected
  structure/ranking row is exposed by the returned manifest. This does not supply
  all rejected candidates or prove their rejection reasons. The helper preserves
  what was published and cannot manufacture unavailable evidence.
- Ten focused tests pass: `.artifact` filename regression, real PDB/CIF parsing,
  hash/size/order, malformed coordinates, compression/archive parsing, verified
  raw/refold linkage, explicit target constraints and uninterpreted content.
  The exact private original-script replay confirms it ignored all 18 Proteina
  entries; its receipt hash is
  `f8812d9403dd9fd94b63209c6e9d1cdcfaaadfa63c459c63903581107f5a16d6`.

These are offline source-candidate checks, not a repaired natural cohort or
biological validation. Geometry is a coarse C-alpha measurement, not all-atom
physical validity, affinity, experimental efficacy or a cross-model ranking.
Missing coordinate positions are not invented. New source deployment and a new
ordinary-client acceptance remain separate gates.
