# Known output filenames and future references — successor source gate

Live v52 remains unchanged and its failures remain retained. Scientist 01
completed prediction, structural comparison and report assembly, but final
publication failed because the plan requested `compare/residue-map.csv`. The
structure helper actually published `residue-mapping.json`; its existing
discovery already named that file correctly. This was a missing enforcement
step, not a scientific calculation failure or missing model output.

Scientist 06 supplied a predicted future worker `steps` directory as a literal
Python-analysis input. The existing validator correctly rejected it before
admission, but did not explain the required per-file dependency references.
No live plan, script, operation or result is repaired by this source change.

## Narrow repair

- Reuse shared discovery metadata for exhaustive structure/protein-preparation
  output names. Validate exact names in dependent inputs and final deliverables
  before admission and composer finalization. Structure's two possible
  coordinate formats remain explicitly conditional, not both guaranteed.
- Derive exact `write-json`, saved Python-script and requested export-format
  filenames from their existing typed arguments. No filename is guessed,
  substituted, added to a script or silently renamed.
- Leave dynamic native/batch/clinical and manifest-driven helper output sets
  deferred; an incomplete filename list is not treated as an exhaustive one.
- Explain missing literal paths with a compact `{step,file}` example and one
  named Python input per required file. Never predict a worker path or bind an
  output directory. Corrections use immutable composer revisions, not edits to
  already admitted plans.

No executor, scientific algorithm, admission identity, limits, retry policy,
model settings or live deployment changes.

## Evidence

161 focused tests pass in 7.69 seconds, including 24 new filename/dependency
cases, a real structural comparison and corrected-draft completion, original
failed-revision preservation, unchanged normal plans, explicit conditional
formats, caller-declared Python outputs, and deferred dynamic contracts. Ruff
and whitespace checks pass.

The source suite ran in the v52 scientific Python environment with network
disabled and candidate source mounted read-only. It is successor **source**
evidence, not an installed successor-image claim. Pytest-only modules were
mounted separately. Initial host attempts lacked scientific dependencies; the
first Docker source run used pytest as PID 1, so the existing orphan-process
guard correctly terminated helper children. Original failing JUnit/reproduction
receipts remain retained. Adding Docker's normal init process to the test
harness produced the passing run without a runtime change.

Protected evidence:

- `U/output-preflight-successor.yprh5I/junit-final.xml`, SHA256
  `0faad4897fa47735209124e01ac4895263855d6cb2b47d08a140bdf3ed13b1ad`.
- Original 01 failure: `U/natural-v52/scientist-01/readback-r1/study.json`, SHA256
  `fac4130e4f1ad39f09f42c1d0902cea1431b435fd9d7ac8360ad17ab8a6c3c30`.
- Original 06 messages: `U/natural-observations-v52/20260919T170253800918Z/scientist-06/messages-140a7c7f-ab7d-5534-a0c9-f0b24f0bd329.json`, SHA256
  `5684889fbc7c3b0e630b2bb0669a1e09b0d3540f3334937e2f8f49d966e4867e`.

Root owns any combined image, installed successor gate and fresh natural
qualification. These retained failed journeys do not inherit a pass.
