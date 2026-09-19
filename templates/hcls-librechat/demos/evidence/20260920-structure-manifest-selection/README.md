# Explicit manifest-backed structural analysis

Private v60 scientist-02 failed during local structural analysis, **after all
four Boltz2/Protenix operations succeeded**. The saved Protenix phases passed
`output-manifest.json` as `prediction`, explicitly selected `structure_index:0`,
and supplied the same manifest for confidence. The previous CLI treated that
prediction file as raw coordinates: parsing manifest JSON as PDB ended in
`StopIteration`. Neither a model failure nor the earlier bounded
`observation_expired` state explains this local failure. The worker had already
resumed observation of the same operation automatically without a new call.

The original failed study `85c487fe-f0ab-50ab-ae2b-d68e7992b6e1`, plan, raw
coordinates and diagnostics remain unchanged. Protected evidence under
`U = scientific-unattended-20260919`:

- `natural-v60-private/scientist-02/terminal-detail.json`, SHA256
  `50fd2afc64bcbb63ee0a4bdb6366bf8d5e7b9fb5e51d5ade381cffcbb99bd16a`.
- `independent-v60-private/scientist-02-s3-20260919T235010353655Z`:
  243 files / 1,679,785 bytes, receipt SHA256
  `ec8cf85d2a6ec1606932a141cb36fd6ca7fcbadc6d7c48f693755f7a6e616f64`.
- Frozen plan `workspace/scientist-02/unattended-20260919-r12/complexes/plan/revisions/581faad70c47b38fbf615c10f24df4ada2786d8f0e2ea0315426234efaaf8d4f.json`
  has the filename's SHA256. Original diagnostic is under
  `steps/struct-protenix-1acb/generation-74f13198b29f4824910effbaa10fec49/diagnostic.txt`.
- Actual saved-state Runs UI:
  `independent-v60-private/scientist-02-browser-r1/05-current-snapshot.json`.
  An earlier live S3 read raced a mutable receipt and failed If-Match; its
  incomplete snapshot is preserved separately, not counted as a complete copy.

## Narrow source repair

Structure `prediction` now accepts an exact published manifest with an explicit
coordinate `structure_index`. It reuses the existing typed coordinate reader:
selection is among declared PDB/mmCIF coordinate roles, **not** an arbitrary
artifact position. Hash, size, media/semantic type and actual byte format must
agree. The selected original artifact path, manifest hash, coordinate index,
manifest-entry index and same-manifest confidence binding are retained.
Coordinates and scientific settings are not rewritten or converted.

Future manifest references missing the explicit index fail before admission.
Already materialized manifests are checked before admission for missing,
out-of-range, ambiguous, tampered or format-inconsistent selections. Future
artifact bytes cannot be known in advance and are verified when produced.
Unrecognized noncoordinate text now gives an actionable format error rather
than `StopIteration`. Existing raw-coordinate and inline-result behavior stays.

## Evidence, not a replacement natural pass

`test_structure_manifest_prediction.py` adds 14 cases: PDB/mmCIF complete Study
publication, eight invalid materialized selections, missing future selection,
invalid coordinate text, and separate read-only local analyses of both exact
retained Protenix 1ACB/2PTC outputs. Original plan/input/output bytes remain
unchanged; these replays contain no inference or customer-chat intervention.

114 focused cases passed (all 14 new); 52 broader Study/model-output cases
passed separately. Protected JUnit files:

- `v61-structure-manifest-tests-r2.xml`, SHA256
  `b53f230837d4845bf244005d0579ba8cdbfd395fbe13c30518c111c9ad221d44`.
- `v61-study-manifest-backcompat-r1.xml`, SHA256
  `c221ed8efa2cc17d43e817ab1eb250beb74490d1f45372428f5cc69727785380`.

For installed verification, set `SCIENTIFIC_RETAINED_V60_02_SNAPSHOT` to the exact
read-only tree above and `SCIENTIFIC_RETAINED_V60_02_REFERENCES` to the protected
`acceptance-input-preflight/scientist-02/objects` tree. Run all 14 tests against
the frozen installed helper/Study modules; no runtime source overlay. Fresh
natural end-to-end report publication and actual UI delivery remain pending.
Local analysis success does not complete the failed v60 study or establish
biological/experimental correctness.
