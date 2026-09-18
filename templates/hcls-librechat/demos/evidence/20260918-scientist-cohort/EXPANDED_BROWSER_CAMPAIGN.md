# Expanded natural-browser campaign — live evidence ledger

Checkpoint: 2026-09-18 21:29 UTC. This is an **incomplete qualification**, not a
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
| 03 | PD-L1 Proteina-Complexa / BoltzGen design | BoltzGen result and report downloaded and verified. Proteina first failed from an inferred filename instead of published task ID; subsequent valid request exposed the backend's gzip decoding/hash bug. After Helm160, exact corrected receipt/key admitted operation `2e85d8c4-fc67-418e-9d33-a83555c744ca`; generation/filter succeeded, evaluation pending at checkpoint. No duplicate BoltzGen run. |
| 04 | Mosaic / BindCraft / RFdiffusion → bounded sequence-design/refold funnel | All three original design operations completed. The sequential helper recovered the original BindCraft/RF receipts after a concurrency429 and an incorrectly backgrounded executor were preserved. At most one ProteinMPNN/refold downstream step is underway. Final scientific report still pending. |
| 05 | DiffDock redocking of public 1A52/3PTB plus MolMIM/GenMol chemistry checks | v22 natural prompt started at21:26. Held-out crystal poses are evaluation references, not inference inputs. Four bounded submissions authorized; actual outputs and report pending. |
| 06 | Public plant-genome continuation and capability limits | Inputs/provenance staged; browser waits for its API operation to terminate. Generation must not be presented as paper-level variant-effect reproduction. |
| 07 | NHANES PhenoAge and public AltumAge feature-order checks | Actual row-level files and corrected report downloaded. All32 PhenoAge predictions exactly match the declared rounded coefficient version. The agent's alternative coefficients caused its apparent offset. One unsolicited invalid probe after a no-new-inference instruction is preserved as a real agent failure. AltumAge check covers17 predictions but only one matched reordered sample, not population accuracy. |
| 08 | Full English PriMock57 across three ASR Apps; German MultiMed; evidence-linked report draft | v22 natural prompt started at21:26. Human references and source provenance staged. Four transcriptions plus one draft from an existing transcript authorized; no redundant transcription. Outputs/report/medical factual review pending. |
| 09 | Six untouched MindEval consultations: two profiles × three clinicians | All six completed. v19 chat transport truncated exported transcripts; v22 repaired export without new inference. Six complete21-message records and six transcript files independently downloaded/hash-verified; every original message appears in its export. Report interpretation required correction. |
| 10 | Recorded ALOHA video augmentation and LeRobot dataset | Native video failed after GPU snapshot restore; LeRobot separately hit a malformed semantic role and misleading backend error. All failed receipts/report preserved. Parent/dataset lane exclusively owns one exact native diagnostic replay. No valid augmented dataset claimed. |

## Independently retrieved deliverables

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

## Workbench repairs exercised in this campaign

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
