# v54 chemistry and aging: natural durable studies

Both frozen, single-prompt studies completed after their browsers closed, with
independently reproduced numerical results and actual UI downloads. These are
two bounded workflow observations, not biological validation, two repeated
unchanged-release clean cohorts or platform-wide readiness. Earlier failures
remain unchanged. The separate [retained MindEval result](../20260919-mindeval-natural-v54/README.md)
does not qualify fresh consultations or judge execution.

## Frozen release and invocation

- Client source `12fb896b4dd6c3b856b4b07da903bad08546a0ec`; OCI index
  `sha256:c5d01a265447b6d89c155c6266acdad18e158b78eba8888fa2586b41234d421a`;
  runtime manifest `sha256:88a70502e8a56e2997286017988ab5fd09b296524d9b2dbd20b1859f435a24a5`.
- Backend190 source `c154d77654a16b5cfdf732f505467ac981b6479f`; image index
  `sha256:e4319840c1d9378c2942f2e389785917e045af4b5733f93da3b535c3f33e3dad`.
- Kimi-K3, low reasoning, unchanged 131072 context / 8192 output. Each scientist
  has a dedicated instance. Original prompts changed only the output root to
  `unattended-20260919-r7`; v53 had no natural deployment or submission.
- Exactly one actual browser prompt per scientist, no human continuation,
  corrective scientific hints or evaluator-triggered inference. Chemistry
  completed UI submission at 18:05:51.251 UTC; aging at 18:05:53.274 UTC,
  within the explicitly authorized 18:06 submission cutoff.

| Observation on 2026-09-19 UTC | Chemistry, scientist05 | Aging, scientist07 |
| --- | --- | --- |
| Endpoint | `aiendpoint-e00bvjvhq5wcxkdydx` | `aiendpoint-e00m188b8dc8mkq7wd` |
| Conversation | `17ced071-f539-5529-a3e7-713c950d108d` | `ced667ab-f6a3-55f1-a7f6-c17c59a7c947` |
| Study | `efc68860-5689-5a5e-a5b6-26dc89b69a69` | `1fc0d9f3-f2f7-583a-a838-22695b007d4d` |
| Accepted | 18:06:22.255 | 18:06:21.063 |
| Browser closed after fresh running detail | 18:06:27.552 | 18:06:26.360 |
| Completed | 18:09:08.163 | 18:08:47.054 |
| Accepted → completed | 165.909 seconds | 145.991 seconds |
| Completion after browser closure | 160.611 seconds | 140.694 seconds |
| Completed phases | 8 | 7 |
| Fresh model operations in the durable plan | 5 | 4 |
| Actual final UI downloads | 8 files / 105,997 bytes | 7 files / 58,175 bytes |

These are whole-study wall times, not GPU occupancy, queue time or inference
latency. This proves browser-disconnected continuation for these studies, not
instance-loss recovery. The observers submitted no additional work. Both chats
correctly described an ongoing study rather than a completed scientific result.

## Independent scientific checks

Chemistry preserves the frozen 1A52/estradiol and 3PTB/benzamidine receptor and
ligand preparation. Four DiffDock requests use seeds 7 and 11, four poses each;
one GenMol request asks for 16 unique molecules with `[*{20-30}]`, QED and
otherwise default settings. Experimental ligand coordinates are used only for
evaluation. No MolMIM run or scientific retry was added.

- All 16 returned poses match the reference graph/stereochemistry and have
  explicit 3D SDF headers. Independent unfitted heavy-atom RMSD enumerates exact
  stereochemistry-preserving mappings in the receptor frame, without fitting
  the ligand. All per-pose CSV/JSON values and 12 explicit unrounded threshold
  counts reproduce. Top-ranked and all-pose denominators remain distinct.
- RMSD spans **0.2373691967–40.3578466229 Å**. Poor poses are retained. Highest
  confidence does not select the lowest-RMSD pose in any of the four runs; the
  report does not turn confidence into affinity or reference accuracy.
- GenMol returns 16 sanitized, canonically unique molecules. Independent RDKit
  checks reproduce heavy-atom counts (10–35), QED and LogP. Mean QED is
  0.6786965007. The token-generation mask is explicitly not an atom-count bound;
  validity/descriptors are not proof of drug suitability or efficacy.
- The typed `genmol` analysis phase was actually selected and completed. This
  is distinct from the retained v52 ad hoc parser failure.

Aging retains 32 original NHANES rows in two batches of 16 with row identifiers
and units. Independent 60-digit Decimal evaluation of the declared rounded
Levine supplement equations agrees to at most **3.019806626980426e-14 years**.
Independent float64 NumPy evaluation of the original AltumAge Keras layer order,
SELU/BatchNormalization, robust scaler and 20,318 named CpGs agrees across 17
returned predictions to at most **1.55301247417583e-05 years**. The complete
file contains one sample and the reversed file 16: there is exactly one shared
sample, with identical aligned features and hosted delta
**−5.364418029785156e-07 years**. Four negative predictions remain visible.
The final report explicitly distinguishes numerical agreement from held-out
population accuracy and clinical validity.

## Retained defects, limits and delivery method

- Aging's first inline plan had malformed JSON and was rejected before
  admission. The model self-corrected using a plan file in the same user turn;
  one study was admitted, without operator assistance.
- Aging's **interim chat** incorrectly described the reversed input as the
  same sample. The actual input has 16 samples, and the final deterministic
  report correctly states 1-versus-16 with one overlap. The chat discrepancy
  is not erased by the correct report.
- Chemistry's first independent checker accidentally required bitwise QED
  equality, unlike the existing `verify_r3_artifacts.py:179` absolute tolerance
  of `1e-12`. It failed on two floating-point differences, maximum
  `1.1102230246251565e-16`. That failed harness and source remain intact; a
  separate r2 reassessment uses the unchanged earlier tolerance, records the
  difference and checks exact saved CSV/JSON agreement. Customer outputs and
  scientific thresholds were not changed. This is not a rerun of the model.
- Four RDKit 2D-header/3D-coordinate warnings arise from unchanged experimental
  reference SDF reads. All generated pose headers were separately checked as
  3D; these known reference warnings remain in the evidence.
- Reconnect used only the same endpoint/user's normally refreshed browser
  cookies. Each declared final artifact was opened from its actual Runs card,
  followed by **Download selected file**. All 15 browser downloads match both
  published size/hash and independently downloaded Object Storage bytes.
  API/S3 readback alone was not counted as UI delivery. Inputs and raw phase
  outputs also remain in the protected object snapshots; they were not all
  individually downloaded through the UI.

## Protected evidence

Root: `/home/tux/secure-handoff/scientific-unattended-20260919/`.
Raw chats, requests, structures, molecular outputs and authenticated browser
state stay outside Git. Stable receipt hashes below bind this scoped report.

| Receipt | SHA256 |
| --- | --- |
| `natural-v54/scientist-05/capture-r4/study.json` | `e58c423b8ce21cc0616e7834ff4e5c025bfcd1a4827ae2a85dc354dd2e6de7c3` |
| `natural-v54/scientist-07/capture-r4/study.json` | `238a9d0f06467691719c277b19ae24dba7d5ada8019761aa5e1c9a261c296e6f` |
| `natural-v54/scientist-05/disconnect-r1/receipt.json` | `962a74063fa3109bffef602f3af461d15a186f56482cfd7ad27174b29a619899` |
| `natural-v54/scientist-07/disconnect-r1/receipt.json` | `e39d24a9a12b963bbd2906da9b215ebc14c530c39b4be55644189fc222a1f15a` |
| `independent-v54/scientist-05-numerical-r1-harness-failure.json` | `84c487cd43843f67d06dd039d82164edde38279315efd73729da1c5c8c068e64` |
| `independent-v54/scientist-05-numerical-r2.json` | `730ee3a94e11200d576e6e8d4b39ddc3a580c264d8a96a1bccc6b1ce3d7ae100` |
| `independent-v54/scientist-07-numerical-r1.json` | `238b5326942c8d9ca32de3eaa6efe0bb98168d71aa7b2890f962fd41f9c6d87e` |
| `independent-v54/scientist-05-browser-r1/download-receipt.json` | `7f1254691dcce1be4ba6c858306b908b81792b54a82bb981958e7a4fd7f1e906` |
| `independent-v54/scientist-07-browser-r1/download-receipt.json` | `aade35f46094c7b8c679a352fa813ffcf2e7fdc8e5d6404158b60b7a0cf32d84` |

Independent methods: `verify_v54_chemistry.py` (retained failed exact-equality
harness), `verify_v54_chemistry_r2.py` (explicit reassessment) and
`verify_v54_aging.py`, with original `verify_r3_artifacts.py` source hashes in
the receipts. No extra inference, endpoint mutation or key maintenance was
performed by these checks. The owner retains deployment and cleanup authority.
