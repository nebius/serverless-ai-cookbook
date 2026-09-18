# Expanded natural-browser campaign — live evidence ledger

Checkpoint: 2026-09-18 22:01 UTC. This is an **incomplete qualification**, not a
customer-readiness declaration. The parent twelve-hour campaign started at
18:04 UTC and has a 2026-09-19 06:04 UTC review checkpoint. API-scale cohorts are
tracked separately; do not count their requests as natural browser interactions.

## Topology and evidence boundaries

Ten test scientists have distinct login identities and platform API keys across
three collaborating lab tenants. Every preview uses its assigned tenant bucket.
The topology is ten dedicated workbench instances, not ten users on one shared
root-execution instance. Shared-instance attribution, execution isolation and
chat-database persistence across replacement remain outside demonstrated
coverage. Existing preview endpoints and original chats are retained.

Each key permits one active platform model operation. Ownership is handed off
between the API and browser lanes only after existing operations terminate.
Limits, context budgets and tool-round budgets were not increased. GPU capacity
unavailability is recorded separately from software and agent failures.

Raw chats, tool arguments, API responses and files are private under
`/home/tux/secure-handoff/scientific-qualification-20260918/browser-evidence`.
They may include short-lived signed download URLs; do not copy them into Git.
Public fixture provenance is in the frozen dataset manifests. A successful HTTP
response, inference result or hash check does not establish scientific validity.

## Current browser studies

| Scientist | Study | Evidence and remaining work |
|---|---|---|
| 01 | Public structure prediction and experimental comparison | Parent owns the v19 final replay and independent verification. Do not infer its outcome from this lane's older failed baselines. |
| 02 | Complex prediction with actual MSA searches | Parent owns final verification of the v19 files. Continuation was required; this is not an untouched one-turn success. |
| 03 | PD-L1 Proteina-Complexa / BoltzGen design | Both models completed; v4 Proteina report downloaded and56 metric values/eight sequence hashes independently verified. Eight designs are expected `num_samples=4 × best_of_n.replicas=2`, established by pinned-source review. Original target error, raw-gzip artifact rejection, wrong count interpretation and operator repairs remain failures/interventions. |
| 04 | Mosaic / BindCraft / RFdiffusion → bounded sequence-design/refold funnel | All five original design/sequence/refold operations completed. Agent's strict sequence alignment of a poly-glycine backbone was scientifically inappropriate; explicit provenance-bound residue mapping is implemented and a v23 read-only report repair is running. Independent76-position C-alpha fit RMSD8.03548 Å shows poor design/refold self-consistency, despite mean pLDDT82.465. |
| 05 | DiffDock redocking of public 1A52/3PTB plus MolMIM/GenMol chemistry checks | Four original requests terminated. Both docking results exist; agent inverted RDKit atom mapping and materially misreported3PTB accuracy. Verified reusable helper fixes correspondence without ligand fitting. GenMol16/16 valid/unique; mask is not a heavy-atom bound. MolMIM generation exhaustion7/8 remains a search shortfall, not silently retried. v23 read-only report recovery pending. |
| 06 | Public plant-genome continuation and capability limits | Inputs/provenance staged. Parent diagnosed the earlier API operation as a shared-memory deadlock, not a normal capacity wait; browser identity remains held until known operation terminal. Generation must not be presented as paper-level variant-effect reproduction. |
| 07 | NHANES PhenoAge and public AltumAge feature-order checks | Actual row-level files and corrected report downloaded. All32 PhenoAge predictions exactly match the declared rounded coefficient version. The agent's alternative coefficients caused its apparent offset. One unsolicited invalid probe after a no-new-inference instruction is preserved as a real agent failure. AltumAge check covers17 predictions but only one matched reordered sample, not population accuracy. |
| 08 | Full English PriMock57 across three ASR Apps; German MultiMed; evidence-linked report draft | Four actual ASR outputs independently downloaded. Initial WER included human annotation tags as words; corrected policy/results below. Agent replaced full1,366-word transcript with reconstructed278-word clinical input: original draft is rejected. v23 exact-file/hash-lineage repair awaits one explicitly authorized corrected draft, without repeating ASR. |
| 09 | Six untouched MindEval consultations: two profiles × three clinicians | All six completed. v19 chat transport truncated exported transcripts; v22 repaired export without new inference. Six complete21-message records and six transcript files independently downloaded/hash-verified; every original message appears in its export. Report interpretation required correction. |
| 10 | Recorded ALOHA video augmentation and LeRobot dataset | Native video failed after GPU snapshot restore; LeRobot separately hit a malformed semantic role and misleading backend error. All failed receipts/report preserved. Parent/dataset lane exclusively owns one exact native diagnostic replay. No valid augmented dataset claimed. |

## Independently retrieved deliverables

- Scientist03 source-qualified Proteina `outcome-addendum-v4.md`:9,146 bytes,
  SHA256 `7d7ea0aea8f8b285375d61b51f4fcb1f064414836a82bb59ac96390cf518d75f`.
  JSON9,452 bytes, SHA256
  `85ba7b1dcc3c51dcd6e19730c9e0484d85f5d4c3f19e01793b1390bf1a07a71b`.
  All56 numerical table entries and all8 sequence hashes match actual CSV.
  The4×2 explanation comes from source54058860d43444c7289873f77d3e50b5b02348cd,
  `binder_generate.yaml` and `best_of_n_search.py`, not from guessing CSV rows.
  Filter-stage completion alone is not a per-design pass claim; no binding
  efficacy is established. Earlier incorrect reports remain intact.
- Scientist03 recovered BoltzGen `REPORT.md`:5,807 bytes,
  SHA256 `db7718d8bfe0ab6bd154d7b778988d15637a4484c585229e69105bfa7af54e0a`.
  Ranking CSV7,262 bytes and mmCIF142,145 bytes also downloaded. One67-aa
  candidate; iPTM0.40243, pTM0.81826, minimum interface PAE6.58212 and filter
  RMSD0.96202 are model metrics, not binding efficacy. Operator continuation was
  needed after the agent deleted/recreated a directory on the object-store mount.
- Scientist07 original `REPORT.md`:8,126 bytes,
  SHA256 `809081ed0df1c2ed938c854400dd9a06bbddb97ffbacdddcbf45fc4bb62f97da`.
  Corrected version `REPORT-v1-with-appendix-A.md`:12,801 bytes,
  SHA256 `32315d533d14a4191d41cc8c6a6bd661e172d57379602ca5a7edf0d036bccac9`.
  All32 runtime values match `levine-2018-supplement-rounded-v1` exactly; the
  alternate-reference discrepancy is fully explained by intercept/ALP choices.
  A correction attempt exposed another unsupported append operation on S3 FUSE;
  the agent finally wrote a new version, leaving the original intact.
- Scientist09 corrected `REPORT-v2-CORRECTED.md`:9,582 bytes,
  SHA256 `a63b524054bc2c1b689021527988bf9497ca080ca150e4aa712206c3e1cfc26d`.
  `recovery-verification.json`:3,734 bytes,
  SHA256 `8996f9e8301ca2097f52aea5907cdda3ae8a2bac7d37f68860c14d7d6689cb2f`.
  Six authoritative JSON records range91,893–173,436 bytes; transcript exports
  range12,072–55,401 bytes. Independent download verifies exact hashes/sizes
  and all126 original message contents. The original score CSV was also checked
  against the actual judgments. The unsupported sub0.5 significance threshold
  was removed. Remaining minor prose defect: pooled-axis count says12, while
  saved analysis correctly has10; those axes are explicitly not independent
  replicates. Two profiles cannot justify an efficacy/ranking claim.

## New scientific-analysis and source-lineage failures

- DiffDock: the first analysis used reference-to-prediction RDKit mappings in
  reverse. Independent exact-graph/stereochemistry, symmetry-aware no-fit RMSD
  gives1A52 top/best12.92235/6.70404 Å and3PTB1.120181/0.262053 Å. The latter
  changes the original negative conclusion. The old report is preserved and
  the corrected installed helper still needs live customer report recovery.
- GenMol: `[*{10-20}]` is a SAFE-mask token heuristic using a minimum15,
  not a10–20 heavy-atom contract. Actual heavy-atom counts remain useful
  descriptive data, not evidence of API noncompliance. All16 are valid/unique.
- Speech: original human reference tags were incorrectly counted as words.
  Corrected policy removes annotation tags first, retains uncertain inner
  words, then applies the same NFC/lowercase/punctuation normalization to
  reference and hypothesis. English referenceN=1415; unchanged output WERs
  are18.374558%,22.120141%,24.240283% for English Nemotron, multilingual
  Nemotron and Parakeet respectively. German remains12% over25 words. One
  recording/short clip does not establish clinical suitability or a ranking.
- Clinical: old job `cf4a3826d4e9a936b1e7f21a49ddf4ab` consumed1432 bytes,
  278 reconstructed words, SHA256
  `f56118c7eb3784176b8e74bfcfc53f70b6aae6404bd385e1a7bc3b9a55931eea`.
  Actual English ASR text is6817 bytes/1366 words, SHA256
  `e511be3353a9cdad1d2d2f10e7000ec7b9f2986e01ed3785f10723d99e3ffbee`.
  The shortened input is neither equal to nor a substring of the source.
  All seven original clinical files are independently downloaded; that draft
  is rejected as a full-recording report, not rescued by its successful status.
  v23 introduces server-read existing-file input and exact byte/hash provenance;
  one explicitly authorized corrected draft remains a live acceptance gate.

## Workbench repairs exercised in this campaign

### 22:32 UTC: verified outcomes and a repeated fresh-study failure

- v24 source `64705e4a826a2ce9b5737f342fd32fc764a903c9`, image
  `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:r0918-v24-64705e4`, digest
  `sha256:1bf5a7cef18e147fc1c6e9604b8b208d5243a86fe279ea1f43e46ae424975a21`
  is deployed to dedicated scientist05/08 previews. It fixes the actual seeded
  clinical tool omission and tests seed/tool-definition parity.
- Scientist06 completed12 Evo2 continuations (six256-base public chloroplast
  prefixes × seeds1/7, each64 new bases). Independent downloaded-byte checks
  against frozen154,478-base NC_000932.1 verify every request, output and metric.
  Six suffixes match the reference exactly; training overlap remains unknown.
  Model-reported total34.309s, summed service intervals107.253s and workflow
  wall390.58s are separate measurements, not interchangeable GPU accounting.
  Report v1 mislabeled milliseconds as seconds; v2 required correction and was
  downloaded7252B, SHA256 `9d1d099d683944495b5725acbf579d87d62b9a3f58f27dd28749e61b490f3137`.
  Original scripts/report and the unit error remain. No active06 operation;
  key explicitly returned to parent.
- Scientist08's one corrected clinical job
  `9ced4689b0dcf7160faa403375c144aa` verified the223,161-byte original ASR JSON
  and completed in41.4s. All seven actual clinical files downloaded. Transcript
 6817B SHA256 `e511be3353a9cdad1d2d2f10e7000ec7b9f2986e01ed3785f10723d99e3ffbee`
  exactly matches the full ASR text; no re-transcription. Final speech report
 6962B SHA256 `791b101ed006298a5b224ff916514b715a7d92bb3271b6bddee8cef3b7323ba0`
  required a continuation after treating a dictionary as a list. Its exact
  WERv3 table is independently consistent. This is still an unvalidated draft:
  the automated reviewer approved a standardized drug spelling not literally
  in the source and excluded a stool-test statement with an incomplete quote.
  The latter exposed one-shot citation relocation running only for unsupported,
  not unclear verdicts; the narrow repair retains re-review and all rejections.
- Fresh05 v24 ran four DiffDock requests (two complexes × two seeds, four poses)
  and one GenMol request, all succeeding with stable distinct receipts. The
  new report is **not accepted**: the agent ignored the installed helper and
  again reversed RDKit's mapping direction, disabled chirality and mislabeled
  operation wall time as GPU run time. Correct independent top/best RMSDÅ:
 1A52seed7 18.67284/18.67284; seed11 29.48248/29.48248;
 3PTBseed7 1.12041/1.12041; seed11 1.13322/0.53360. Original16 pose outputs and
  both incorrect/correct calculations retained. GenMol returned16 valid unique
  molecules, but `unique=false` deviated from the explicit request;8 molecules
  have fewer than20 heavy atoms, not the narrative's6. SAFE masking is not a
  heavy-atom or upper token-count bound. No replacement generation is used to
  conceal these instruction/reporting defects.
- New typed workbench analysis adapters call the same tested docking/structure
  helpers with workspace files, retain input/output hashes and method identity,
  and return actual deterministic metrics. No new scientific algorithm or model
  inference. The candidate passes22 Node service/adapter tests,20 underlying
  structure/docking tests,21 seed/build tests and4 clinical citation tests.
  Live fresh-context read-only analysis remains a gate before acceptance.

Private evidence is under the existing qualification directory's
`browser-evidence/scientist-{05,06,08}-v{23,24}-*`; raw conversations may contain
signed URLs and must not be published. This checkpoint does not erase prior
failures or establish two clean final-release cohorts.

- Caller-scoped durable Runs history; explicit upload operations instead of
  labeling pending uploads as GPU work.
- Compact results with verified workspace-file pointers; native structure
  artifact resolution and reusable structure-analysis helper.
- Object-store-safe verified direct writes and immutable receipt journals;
  recovery preserves original idempotency and operation identity.
- Fixed upstream false context accounting: large strings were counted as UTF8
  bytes. Captured tool definitions were falsely estimated at210,850 tokens;
  full reference tokenization was59,869, bounded accounting62,819. No budget
  increase. Original context-overflow failures remain in evidence.
- Visible incomplete/blank agent turns, provider finish diagnostics, bounded
  observation and sequential active-operation handling. An unfinished native
  or batch observation now exits75, not success.
- Native pre-admission validation evidence and explicit read-only recovery;
  published scientific artifact-role/schema validation before upload.
- Remaining-round guidance prioritizes actual saved deliverables, not extra
  searches/polls. Agent errors still occur; guidance alone is not acceptance.
- v22 full workshop records retained as content-addressed S3 workspace files,
  with compact metadata returned to chat. Live six-record recovery passed.

## Release pins and limitations

- v21 source `17a6a82`, image digest
  `sha256:74b85a24379e3f14e99ed97f0b3d78438fdd4b579f3a2e1d8464eafd96342029`.
  Forty-two focused Python tests and pinned-runtime patch/tool-token checks pass.
- v22 source `454da05`, image digest
  `sha256:5afd48bd101860f311a079614125f81a3d36a3dbded382e8641191a8e706ad8a`.
  Fourteen focused service/MCP tests pass; live S3 full-record recovery verified.
- v23 source `3e1733b`, image digest
  `sha256:df76112ed4c5770f920036a1325093dea3a0d47394abe4a61801e4c26703ed8f`.
 44 native/batch/workflow/receipt,12 structure,8 docking,19 service/Run-display
  and5 pinned-runtime/tool tests pass. Isolated previews are provisioning;
  offline tests do not close the live recovery gates above. Initial provider
  Internal create errors were retained and exact names reconciled before retry.
- GLM5.3 low-reasoning is used for ongoing previews with the original8,192 output
  budget. Kimi3 exploratory comparison on07 was confounded by explicit versus
  implicit context reserves; do not call it a controlled A/B or a global winner.
- Earlier images remain in some active resumed studies. Their successful
  continuation does not establish a single final release passed every journey.
- Runs503 responses were observed while login/messages still worked. Initial
  harness aborted before saving response bodies; that missing evidence is
  acknowledged. The capture helper now retains per-endpoint failures and keeps
  downloading available workspace evidence. A sibling lane diagnoses the cause.
- Actual clinical correctness, physical fidelity, binding efficacy and paper
  reproduction remain separate from service and artifact acceptance.
