# Expanded natural-browser campaign — live evidence ledger

Checkpoint: 2026-09-19 01:01 UTC. This is an **incomplete qualification**, not a
customer-readiness declaration. The parent twelve-hour campaign started at
18:04 UTC and has a 2026-09-19 06:04 UTC review checkpoint. API-scale cohorts are
tracked separately; do not count their requests as natural browser interactions.

## Topology and evidence boundaries

### v32 matched planner comparison and report mechanism

Exact v32 image sourcef043caf/digest29b0404c ran two fresh read-only natural
recovery conversations on byte-identical copies of112 original study files
(1,446,809 bytes), excluding prior corrections. GLM5.3-low and KimiK3 used the
same29-tool seed and37,692-character instructions,8192 output-token budget,
131072 context ceiling, existing round policy and scientist06 identity. Prompts
were identical apart from input/output prefixes; Kimi native reasoning versus
GLM low is an explicit remaining comparison difference.

Both produced16 exact pose rows,4 exact per-run rows and16 exact molecule rows;
all CSV/Markdown widths and numerical values match the independently verified
source. GLM took129.644s/14 tool calls with one self-recovered failed shell exit
and an unsupported S3 in-place edit that damaged newly generated scripts before
repair. Kimi took61.092s/13 calls with no failed exits. Neither used the available
assembler. Both still use unsupported pass/fail language; GLM falsely attributes
reproducible report generation to a retained script that only loads JSON, while
Kimi invents truncation of the original file from an incomplete tool window.
Neither report is accepted; one paired case does not justify a planner switch.
Protected machine-readable evidence: `planner-ab-v32-independent-verification.json`,
`planner-ab-v32-controls.json`, frozen input receipt and complete conversations.

An explicit separate browser call to `workbench_assemble_report` did qualify
the mechanism on actual Object Storage:6,537-byte report SHA256
`3b9834699a1768e28c9052a580618ad92cdee4609c212dd83d4b3a1c4b0b2bc4`
exactly equals an independent local assembly, preserving16 molecule rows and
the deterministic docking report, with no inference. This is not natural adoption.

The preceding initial v32 recovery report retained literal template placeholders
and a false seed comparison. An initial inspector claim that its Markdown
delimiter widths were inconsistent was **wrong**: programmatic parsing verifies
consistent6/9/11 columns. That allegation is withdrawn; original report and
other failures remain retained.

v33 candidate removes contradictory Python-report-rendering guidance and adds
authenticated Workspace deep-links to exact retained files. It changes no model,
compute, context or token policy. The capture helper also stops storing its
failed direct status/tool probes as evidence; actual persisted messages and
workspace bytes remain authoritative. Published source7978d1e image digest
`sha256:50474c6b9d06b24c5fabc8b4aecf9fd9f9a523a3470b4012200de4a48f77c046`
is live on isolated06 endpoint `aiendpoint-e00p1hrfp1pnem3v6b` with32 Apps and
the verified original bucket. Actual browser deep-link→selected-file download
returns the same6,537 bytes/hash above. Anonymous file API requests return401;
a missing selected file shows a clear not-found state without starting download.
This qualifies existing dedicated-deployment file access, not shared-user
isolation or scientific narrative. Natural read-only recovery conversation
`5ba784c0-965a-58db-b43a-bdd9d0bb14fd` is in progress using unchanged original
inputs and a new output directory; no new model inference requested.

### Latest release gate: v31 raw results correct, combined report malformed

Fresh scientist06 v31 used typed sequential admission and multi-run analysis
naturally. Five operations completed in99.387085 seconds from first admission
to last completion; all16 pose values, mappings,16 molecule rows and exact
requests/hashes independently verify. Four bounded observations returned
without MCP timeouts. One read-only continuation was still required.

The final combined report is **not accepted**: its four summary rows contain
seven cells under eight headers, shifting values into wrong columns. The
original7,996-byte report hash is
`5ace12999d384d2c81c40ce296161a428f8663a89d221ad181fcd1009282893c`.
A self-recovered rank_facts KeyError exposed our compact-versus-saved schema
inconsistency; a separate f-string syntax error and incorrect interim count
remain preserved. Independent evidence is in protected
`scientist-06-chemistry-v31-independent-verification.json` and full chat/files.

v32 candidate keeps compact/saved rank-facts layout identical, allows analysis
output_directory, and assembles existing Markdown/CSV files without regenerating
numbers. It preserves Markdown bytes and CSV numeric strings, rejects shifted
CSV widths, records UTF-8 byte/hash lineage, and explicitly does not validate
scientific narrative.16 Python,27 Node and21 seed/config tests pass. A preview
and read-only natural recovery of the saved study remain pending. No new
DiffDock inference is planned until the parent's independently diagnosed
seed-propagation runtime fix is qualified. No limits were raised.

### Latest release gate: v29 narrative failure, v30 observation repair, v31 candidate

Scientist06 v29 completed five distinct sequential operations in89.088641s
from first admission to last completion. All16 pose metrics and16 molecular
rows, exact request settings and source hashes independently verify. Its final
report still fails: it claims three of four top-ranked3PTB selections although
only two3PTB runs exist, understates the confidence range of good poses, and
calls8,611 Unicode characters bytes (actual8,785 UTF-8 bytes; hash correct).
One self-recovered `NameError: metrics` was incorrectly called a truncated
heredoc. One continuation was needed. Original report SHA256
`8b1eee4bd43d56c1140cbc526876f2460b4f7ad79cd060d7eaca06daee1fffe3`
and complete raw evidence remain under the protected v29 capture folders.

v29 also exposed two execution-observation MCP timeouts at the unchanged30s
transport boundary. v30 source75452e9 reserves5s: requested30 becomes effective25
with explicit metadata and early terminal return.59 tests include an actual
30s stdio deadline and same-job reconnect. Image digest
`sha256:76866b573cc304f65c9b19f8f907a56eb0bd516bd71b13acb476b5fb70ce1f70`
is live on isolated06/07 previews.07's provider Internal create failure was
retained; two exact-name inventories showed no resource before one retry.
No timeout, model budget, tool-round budget or key concurrency was raised.

The source-only v31 candidate extends the existing docking helper with typed
multi-run inputs and deterministic grouped reports: runs, all poses and
top-ranked poses have separate explicit denominators, confidence ranges,
threshold counts and provenance. It does not change the RMSD algorithm or
invent thresholds.14 Python and9 Node adapter tests pass, including ties,
partial comparability, missing confidence, exact UTF-8 bytes and grouped counts.
Actual natural-browser qualification of this candidate is still pending.

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

## Browser study inventory at22:01 (later release-specific updates below)

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

### 23:59 UTC — live observation deadline regression retained and repaired

v29 source `2efd02dc27a2e169a18a54a516173b17ff956844`, image
`cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:r0918-v29-2efd02d`, digest
`sha256:06daf70ec18e907a288d01227562dbd47d5e6d25271583fb9a34ba6de4d2faaa`
is deployed in isolated06/07 previews. Fresh06 conversation
`5a901941-da62-595c-ae87-8f97effa8943` naturally prepared and launched all five
same-protocol requests through the typed sequential runner. No preflight errors
occurred, but two actual `read_execution(wait_seconds=30)` calls timed out:
the existing MCP transport itself has a30000ms deadline. Both original durable
jobs/receipts remained available; all five model operations completed once.
The first turn still ended interim, and one ordinary continuation is performing
the analysis. This is a **client regression**, not a capacity or model failure.

The next fix reserves five seconds *inside* the unchanged MCP deadline:
requested wait≤30s, effective wait≤25s, actual metadata returned. Terminal or
interrupted jobs return early. No transport timeout, command deadline or agent
budget is raised. A real26-second shell job is observed pending within25s under
an explicit30-second stdio call timeout, then completed through the same job
after reconnecting.59 execution/workflow/config tests pass, including mocked
deadline and actual configured transport-boundary checks. Parent07's fresh
study is held for this candidate to avoid the now-known regression.

### 23:49 UTC — fresh chemistry tables verify; narrative still fails

Scientist06 v28 completed all five authorized calls without duplicate admission,
strictly sequential by actual operation timestamps. Admission-to-final-completion
was84.47635 seconds. All16 pose values/atom mappings, requested seed-only input
changes, input/output hashes and all16 GenMol property rows independently match.
GenMol returned16 valid/unique molecules,8–21 heavy atoms (mean17.375).

The customer journey is **not a correctness pass**. It needed one continuation
after two self-repaired preflight errors. It repeated an already-completed
execution observation five times and recovered two analysis execution errors.
The final report `1f67e3587969cec3ea941294af4c91545a26317b63411138f3e4cced187b467c`
incorrectly calls1A52 seed23 rank3 the lowest-confidence pose (rank4 is lower),
overgeneralizes an inverse ranking, and claims all seven positive-confidence
poses below1.2Å although only six meet that strict threshold. Actual report size
is6383 UTF-8 bytes, not the6339 stated in chat. Original files/chats are retained;
proof: `browser-evidence/scientist-06-chemistry-v28-independent-verification.json`.

Parent07's typed aging tools returned correct numerical analysis, but its agent
again failed the optional combined report due to `row_count` existing only in
the tool summary, not the saved metrics. Candidate now makes that schema
consistent and directs reuse of the already-complete deterministic reports.

The combined next candidate aligns execution observations with the existing
30-second model-status bound, returns early on terminal/interrupted state, and
preserves the same execution/operation receipts. No execution deadline, model
concurrency, output budget or tool-round count changes. File preflight reports
all missing/invalid inputs together. Existing docking analysis now additionally
renders CSV/methods report from exact tied extrema and optional explicit strict
threshold counts; it does not add a scientific cutoff or correlation claim.
58 execution/workflow/config,11 docking,4 aging and24 Node tests pass. Actual
retained06 inputs reproduce the corrected facts with no new model calls.
Fresh deployed qualification is still required; no default client promotion.

### 23:38 UTC — aging preview live; fresh complete chemistry study running

v28 source `8674bd8b88309347c26cb73df4b6fef4cf279b20`, full image
`cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:r0918-v28-8674bd8`, index
`sha256:4317e180df260bbfd0b31f0472c2855488028a97bccd6fde2f0dc98d9e80909a`
is live in isolated previews07 and06, with their original scoped keys and
verified bucket mounts. Parent owns07's natural aging recovery. Scientist06
conversation `e23cc87e-6aad-59e9-ad6e-02fd973fa7f0` is a fresh public1A52/3PTB
DiffDock study with seeds19/23, four poses each, plus16 GenMol molecules. The
natural prompt asks for reference-frame pose evaluation, explicit best/worst/
top-ranked comparisons, measured chemical properties and auditable reports,
without naming helper tools. It naturally chose the typed sequential workflow
launcher, but first repaired missing/relative input paths. No operator prompt
or duplicate admission was needed; this recovered preparation error is retained.
The study is in progress and no report-correctness pass is claimed.

A deeper audit of the prior v27 genomic one-turn completion found one internal
analysis execution `KeyError: model_revision`: an `exec` reused a local variable.
The agent repaired it in the same turn, with no new model inference or operator
intervention. Its final verified report remains correct, but this is **not a
zero-error run**. Evidence is retained with the independent verification.

Source-only follow-up removes a residual mandatory per-operation tracking
sentence in the shared instructions and emphasizes the typed sequential runner
in the primary agent.21 seed/config tests pass. These edits are not retroactively
attributed to the frozen v28 image or its live study.

### 23:28 UTC — one-turn genome replay; independent aging helper candidate

Fresh05 v27 conversation `2aa5a7f4-1f69-5b17-932f-cf70bedd24a8` completed the
same four frozen Evo2 inputs and saved report in one turn without intervention.
Downloaded raw requests/results and all GC, reference identity, lengths,
timestamps and report values independently verify. Report SHA256
`8c9433331bf7ef733b737e070568b135fce0a1bd1cc88c5ee19913dc1663cf6e`.
Its47.224s workflow value is explicitly first admission→last completion, not
the execution-job interval used in the earlier comparison. The agent chose
the existing valid CLI workflow, so this does not prove typed-step adoption.
One small genomic workflow does not establish general readiness.

Parent07 v26 completed four aging calls but failed twice to produce correct
analysis: PhenoAge field-name mistakes and an invented H5 architecture caused
an apparent~262-year AltumAge error. The new typed `workbench_analyze_aging`
candidate imports the existing independent qualification functions unchanged:
60-digit published rounded PhenoAge equations, and original checksum-pinned H5
model_config layer order/SELU/BatchNormalization with original robust scaler.
Build-only trusted preprocessing becomes plain JSON; runtime reads no pickles.
It saves complete per-sample metrics, CSV, methods report and hash lineage,
matches samples explicitly, and never submits inference.

Read-only verification of the actual downloaded07 results finds32 PhenoAge
rows within3.02e-14 years of declared rounded-v1 and17 AltumAge rows within
1.553e-5 years of the independent H5 reference. There is exactly one matching
reordered sample, difference−5.364418e-7 years, not16 pairs. The hosted models
are numerically consistent; the agent-generated reference was wrong. Original
failure/incorrect files are retained. Evidence:
`browser-evidence/scientist-07-v26-independent-aging-v28`.

Four helper tests cover published formula/version, exact IDs/raw CRP, actual
H5 execution order/SELU, and33 real pinned complete/reordered/missingness rows.
23 Node service/tool tests and21 seed tests pass. Candidate guidance removes
obsolete per-operation tracking calls because Runs already auto-discovers
caller history. Typed aging live browser qualification remains pending.

### 23:12 UTC — matched timing independently verified; canonical steps published

Independent downloaded-byte/reference/receipt checks confirm the same four
inputs, model revision, Pod and GPU identities across the v25/v26 experiment.
Execution wall121.7745s→63.6795s is a47.707% measured reduction. Model-reported
generation totals11.6089s→11.5980s and service admission-to-completion totals
17.9138s→17.8425s barely changed. All64-base outputs, GC, reference-suffix
identity, report values and hashes verify. This is one paired cohort, not a
statistical guarantee or whole-conversation improvement. Both conversations
needed continuation and repaired malformed plans. Protected evidence:
`browser-evidence/scientist-05-polling-v25-v26-independent-verification.json`.

The canonical typed-step candidate is source
`b3736e65435b2a7434f8185e61c2e1435927d76d`, image
`cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:r0918-v27-b3736e6`, digest
`sha256:ab24b961691040286dcbde5ffb329c2b37f0ca85d5680ebe11afa606af4c0e00`.
73 focused tests plus9 batch-client tests pass;05/07 previews are provisioning.
Fresh natural browser completion is still required. No changed budgets, limits,
model settings or automatic retry of ambiguous admissions.

### 23:06 UTC — live typed launch and matched timing replicate

v26 `0fbe1f8`, digest
`sha256:50c3576dd6a227289c044566340464358d1f1465b46cc59f51ee76076b67f2b0`,
is live in isolated05/07 previews; both32-App catalogs and correct S3 mounts
were verified. Parent owns07.05 ran identical four frozen Evo2 inputs through
v25 and v26, sequentially with unchanged key/model settings. Both completed
all four model operations. Recorded execution-job intervals are121.7745s and
63.679s respectively; exact file/revision comparison is being independently
checked before attributing a speedup. Both natural conversations made the same
plan-shape error and required one read-only continuation to finish analysis.
The second used the typed launcher naturally; its successful model execution
is not a clean one-turn customer-report pass.

The next candidate exposes the **actual typed native/batch step fields** on
that same launcher: input_file for native, source_file/parameters_file plus
published contract roles for batch. It builds the canonical runner plan itself;
the existing plan-file mode remains for recovery. No additional transport or
scientific algorithm. A model-facing file-path error now names the exact step
and field instead of leaking a generic Python TypeError. Observation uses the
existing10-second execution wait ceiling; no limit was increased. Same-prompt
live studies remain required after deployment, not inferred from unit tests.

### 22:49 UTC — typed analysis verified, report interpretation still imperfect

v25 source `64857f9e58f4ac92ce75767468f516644f4600b5`, image
`lc:r0918-v25-64857f9`, digest
`sha256:f5790fc21e4a4b6bd9ea9330634be6bf588c1b33e84e12cb7854a7b20b1572c0`
ran a fresh-context, analysis-only scientist05 conversation
`a22a3907-a3de-5d6e-8723-61acdb2b51f1`. All four typed docking tools were
used naturally, and all16 downloaded pose metrics and mappings match the
independent helper exactly. Reference/result hashes agree; the original
incorrect v24 report remains byte-identical. GenMol counts now agree with the
independent check and durations are correctly labelled service intervals.
This is **not a clean final-report pass**: prose reverses which1A52 pose is
farthest, misstates the mask as an approximate bounded token range, and one
manually copied table number differs at an immaterial2e-10Å. The report hash
is `ed97818e44c2e475a0614fa1cbf51afb1a7ec0bd861c1d2471677c513bec8172`.
Private verification: `browser-evidence/scientist-05-v25-independent-verification.json`.

Parent's fresh07 v24 study spent its turn preparing34 unnecessary AltumAge
feature/value uploads and did not yet admit inference. The reported workspace
permission failure was specifically `open(..., 'a')` after a whole-file write,
not a failed direct-write receipt helper. The native schema accepts complete
arrays, and the packaged native file client already reads/sends them outside
LLM context. Reusable instructions/aging guidance now explicitly distinguish
file-backed API arrays from chat-inline bytes and require complete-file writes
instead of append on the S3 mount. Original uploads, partial report and failed
journey remain evidence; a fresh unchanged study is still required.

The next candidate keeps short native observations in one MCP session, bounded
by30 seconds and the remaining workflow observation deadline; it removes the
second full outer sleep. A recognizable transport disconnect can reconnect
read-only at most three times only when the original operation ID is persisted.
Ambiguous admissions, application failures and hash mismatches still stop. No
model concurrency, request size, context or output-token limit changed. Tests
cover a20,318-feature×16-row file transport with no artifact uploads, exact
receipt recovery, no next admission after deadline and no duplicate wait.
Live same-workload timing comparison remains pending; no speedup claimed yet.

The candidate also adds the seeded typed `run_scientific_workflow` entry point
on the existing execution MCP. It checks every source/input/parameter file
before any model admission, freezes the prepared plan, delegates to the existing
native/batch workflow runner, and returns the original execution job on repeats.
Interrupted jobs need explicit resume; this does not add a second transport or
make fixture values into capability limits.71 focused tests pass, including
actual stdio job reuse, missing-source rejection before launch, every-agent tool
seeding and the native/receipt regressions. Root retains fresh02/07 baseline
failures (malformed CLI path and unnecessary uploads); typed-tool live
acceptance remains pending.

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
