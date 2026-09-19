# v49 chemistry and aging: independent final-artifact checks

Recorded 2026-09-19, through 15:55 UTC. This is two bounded natural studies,
not another full campaign or a platform-wide readiness verdict. Each scientist
retained a dedicated instance and its existing tenant bucket.

Client source `4bd45eaafb6112ec2cae5df253c2403d07d792c3`, OCI index
`sha256:202b76200becd455cbed9a402e3b9b12d6d03f8da692f787e5a12d0471c3824f`.
Backend release189 used source `bbcec4d515d7d53cabc10d185d48adb4ddb6435e`,
index `sha256:2e72e6d90e76acdd051e6148a0bb562720cedb8e57744e60d88402a75df71a19`.
The frozen prompts differ from the preceding bounded acceptance only in their
fresh `unattended-20260919-r3` output root. The release owner submitted them;
this independent verification lane submitted no prompts or model requests.

## Measured results

| Study | Terminal model work | Independent checks | Actual Runs → Workspace downloads |
|---|---|---|---|
| 05 chemistry | Four DiffDock requests, two complexes × seeds7/11 × four poses; one GenMol request | All16 pose chemistry/RMSD/confidence rows and16 generated molecule rows verified | 14/14 files,662,134 bytes, exact published hashes |
| 07 aging | Two16-row PhenoAge batches; one complete and one reversed-feature AltumAge batch | All32 source NHANES rows and17 AltumAge predictions verified | 13/13 files,78,481 bytes, exact published hashes |

Chemistry study `d8095aba-309b-50ef-871b-672d34280e62` retained all poor poses.
Unfitted, symmetry-aware heavy-atom RMSDs range from0.237372 to40.357847 Å.
The staged receptor text and ligand identity are unchanged; experimental ligand
coordinates remain evaluation-only. A separate atom-map/NumPy calculation
reproduces every CSV/JSON value without ligand-only fitting. Top-ranked and
best-of-sample results remain distinct, and highest confidence did not identify
the lowest RMSD in these four runs. No arbitrary threshold was supplied or
invented. Seed settings alone do not establish cross-replica reproducibility.

All16 GenMol molecules parse, are canonically unique and have independently
recomputed QED values matching the saved results. Heavy-atom counts are9–24,
mean QED0.6688193736201358. The20–30 mask is not a heavy-atom bound. No MolMIM
request was added. This checks chemistry/property arithmetic, not binding,
affinity, synthesizability or drug efficacy.

Aging study `047c2eef-0220-500a-9a7d-341f5d70a889` preserves the original32
NHANES identifiers and values exactly once, in two source-order16-row batches.
The exact declared `levine-2018-supplement-rounded-v1` reference reproduces all
PhenoAge results, maximum absolute difference3.0198e-14 years. No nearby
coefficient version or unit conversion was substituted.

AltumAge uses the pinned original Keras H5 and original robust scaler, with
named20,318-CpG mapping and float64 NumPy inference. The17 predictions agree
within1.5531e-5 years. Only `GSM765897` is shared between the1-row complete and
16-row reversed examples: identical mapped features, prediction difference
−5.3644e-7 years. All four negative predicted values remain in the report.
Seventeen predictions are not17 matched pairs; this is one-sample feature-order
evidence, not held-out population accuracy, mortality calibration or clinical
validation. The verification reuses the same published Decimal/NumPy reference
functions as the bundled analysis, not the hosted PyTorch implementation;
it independently checks downloaded source/result/CSV/manifest consistency.

## Delivery, provenance and limitations

The closed whole-study manifests bind23 chemistry and19 aging input/output
entries. Every listed size/hash matches downloaded bytes. Both report-helper
completion manifests also verify all nine closed helper artifacts. Five report
sections per study preserve their original source hashes and row counts.

Actual browser tests clicked every final-artifact link in the completed study's
Runs card, then clicked **Download selected file**. All27 downloads match both
the manifest and the independent Object Storage snapshot. Separate authenticated
HTTP readback also verified chemistry; it was not counted as browser evidence.

Aging's original browser was closed at15:37:30.933 UTC, while PhenoAge batch1
was running and only the split step had completed. The whole study later
published its final report without another chat prompt. Chemistry's original
disconnect watcher did not retain a completed close witness; do not use its
successful whole plan or downloads as proof of that distinct interruption path.

Observer-authentication effects are separate from product/scientific outcomes.
The harness refresh consumed chemistry's browser cookie; the release owner
approved restoring only that exact endpoint/user's refreshed cookies, retaining
their metadata. No password login was needed for chemistry. Aging's stale saved
refresh returned401 once; no automatic retry or password fallback followed.
The release owner then authorized one normal existing-account browser login,
which returned200, before its13 UI downloads. No further API refresh occurred
during either browser flow. These are disclosed harness/session interventions,
not scientific corrections or a clean unaided reconnect claim.

The first offline verifier mistakenly treated the native operation-name string
as a nested operation object. That harness failure remains in `numerical-r1`;
the corrected `numerical-r2` reread the same immutable outputs, without inference.
RDKit's four dimensional-header warnings were isolated to the two unchanged
experimental reference SDFs, each reused for two seeds. Both omit a3D marker but
contain nonzero Z coordinates; all16 generated SDFs explicitly declare3D and
parse without those warnings. No source or predicted coordinates were changed.

## Evidence index

Protected root `U=/home/tux/secure-handoff/scientific-unattended-20260919`:

- Exact inputs/prompt hashes and release binding: `acceptance-v49/`.
- Uncoached launch and aging close witness: `natural-v49/scientist-{05,07}/`;
  aging `disconnect-gate-02/{accepted,detail,browser-close}.json`.
- Immutable file snapshots: `independent-v49/scientist-05-s3-20260919T154210565435Z/`
  and `scientist-07-s3-20260919T154208596988Z/`.
- Chemistry numerical receipt `independent-v49/numerical-r2/chemistry.json`,
  SHA256 `d6952e7abaed253c174c10a78c13a2732ef64074645181f65f526bee61b0ec6e`.
- Aging numerical receipt `independent-v49/numerical-r2/aging.json`,
  SHA256 `211a057252dfe5ea7fd0e6f824c1bf9e21a5983915bbb41e489150754333b622`.
- Chemistry UI receipt `independent-v49/scientist-05-browser-r1/download-hashes.json`,
  SHA256 `7de8b7c2c85a2cdffd1d8e05e76ce03007db118b394852fe9ee861c918e17761`.
- Aging UI receipt `independent-v49/scientist-07-browser-r1/download-hashes.json`,
  SHA256 `aced547dcbc627bd643bf83568a3493d7f2cf34d5bfd8ca88afdf6dfe6067181`.
- Reference-only warning receipt `independent-v49/numerical-r2/sdf-header-warning-reassessment.json`,
  SHA256 `495015c489b084b5c5261872b463a08be8449f0ec02b6d498a514092fa44dbec`.

Reports: chemistry SHA256 `e43f727302396e35122d3e38979490cb843beba14a2b1775fd5ffde8f5371323`;
aging SHA256 `d9b603980afa938009103b86fe87089b13361a46260722915d7f7a2d1623089f`.
Raw inputs, outputs, credentials and browser state remain outside Git. No model,
endpoint, configuration, quota or capacity mutation was performed by this lane.
