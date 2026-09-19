# Unattended-use remediation

User approval: 19 September 2026. This implements the remaining actionable
findings from the twelve-hour campaign; it does not alter its historical results.

## Architecture and scope

One LibreChat instance per user is a deliberate product requirement. Two users
in one tenant may mount the same tenant bucket but retain distinct credentials,
chat state and execution ownership. Do not implement a shared-instance multiuser
gateway or make that a readiness condition. Shared hosted Apps remain unchanged.

Approved implementation tracks:

1. Deterministic schema-bound scientific and clinical report analysis.
2. Durable whole-study preparation, inference, wait, analysis and publication,
   with tested scientific dependencies and no mechanical continuation prompts.
3. Automatic bounded recovery under test-owned worker loss.
4. Measured scheduling envelopes, actual fit restrictions and intelligible waits.
5. Truthful durable lifecycle timing and GPU-occupation accounting.
6. Exact-runtime snapshot correctness, startup measurements and fallback.
7. Integrated public-client qualification on an unchanged final release.

No quota, per-key concurrency, output/context/tool-round, retry or rollout timeout
increases. No unrelated security or audit project. Do not silently switch models,
scientific constraints, seeds or protocols to manufacture completion. Failed or
negative scientific results remain valid findings when reported honestly.

## Source ownership and deployment

- Workbench baseline: `94f331d744713405a7308d9de9a6a6feae951183`, existing branch
  `agent/scientific-ai-workbench-v2-20260918` in the cookbook fork.
- Backend baseline: `8e747def5f31b82014d9daeba97d4711b960adca`, existing branch
  `agent/fs2-cosmos-stockholm-remediation-r20260917` in the solutions-library fork.
- Verified 12:59 UTC: backend Helm182 remains deployed, gateway three ready
  replicas and model controller two ready replicas.
- Separate owning agents implement reports, durable workbench and backend
  accounting. Root integrates exact commits, images and deployments and owns
  fault tests/snapshot qualification. No parallel writers to shared files.
- Parent Task Deck: `fs2-unattended-remediation-r20260919`; its child cards retain
  implementation evidence and outstanding criteria. No work is done merely
  because a card exists or a helper test passes.

## Acceptance

Use the existing backend `CUSTOMER_RELEASE_POLICY.md`: exact candidate identities,
ordinary customer grants/limits, real public client, terminal results and useful
artifacts, repeatable analysis, disconnect/restart, bounded recovery, concurrency,
queueing and accurate usage. Capacity shortage is not a model defect; misleading
status, lost accepted work or starvation are. Preserve unchanged-release clean
cohorts and do not inherit final-release coverage from older campaign builds.

Clinical outputs remain drafts and computational predictions are not experimental
efficacy. The platform must faithfully expose these limits without inventing
analysis or requiring an operator to repair its arithmetic and workflow state.

## Implementation status

In progress. This is not a final readiness claim.

### 19:49 UTC — all five v56 replacements deployed; delivery defects isolated

All five affected test users now have separate, configured v56 instances with
the exact published image and verified tenant bucket. Provider Internal errors
were reconciled against exact-name inventory before bounded explicit retries;
their cause is not proven. The five replaced v54 endpoints are confirmed absent.
Archives and buckets remain; endpoint IDs and local databases are not recoverable.
The other five v54 test instances and Rene's original instance remain unchanged.

The current v56 results are deliberately separated from model-call success:

| Scientist | Current evidence | Remaining issue |
| --- | --- | --- |
|02 structures|All four model calls and four independently recomputed structure analyses succeeded; 21 retained partial files downloaded in UI|Final publication promised a nonexistent native `input.json`; the Study failed|
|03 design|Proteina succeeded; BoltzGen was still running at the latest observation|Terminal design analysis and downloads pending|
|06 genomics|Complete 14-phase Study, 12 exact Evo2 cases, independently verified arithmetic, five actual UI downloads, completion after browser close|Passed this exact release/workflow only|
|08 clinical|All five phases completed; exact WER/source-selection checks; eight final and 20 separately navigated phase downloads verified|Final downloads omitted drafts/transcripts/review files and outcome summaries lacked measured coverage|
|10 robotics|Saved old cancellation automatically reconciled, queue unblocked, no new cancellation/model requests|The new r8 Study failed with an ExceptionGroup before recorded steps; diagnosis pending|

The genomics Study took403.874 seconds accepted-to-finished, not a cold-start
measurement. Clinical literal source selection is not evidence of medical
completeness or validated clinical adequacy. Poor structure agreement is retained,
including approximately17 Å Protenix global RMSD and no recovered reference
contacts in these two cases.

The clinical source fix is committed as `d28ecd3`: measured outcomes and an
explicit verified customer-artifact registration contract. Shared publication,
known native/batch output contracts, and confidence/request provenance are being
combined in one successor; none is counted as deployed yet. The robotics
failure remains unchanged for diagnosis. Its initial launcher failed before any
submission because an observer refreshed a cached browser cookie; after fresh
state loading, exactly one original prompt was sent. No disconnect proof is
claimed for that already-terminal Study.

Four expired disposable test keys were replaced through the supported API with
unchanged identity, grants, concurrency and budgets, completing a separate
ten-user successor credential manifest. Old identities/history remain distinct.
All five successful v54 archives are now prepared; four require explicitly
operator-only original-key ledger/local-owner evidence because the expired
upstream key also blocks their Study/workshop read APIs. This is not a customer
history or transparent key-rotation pass. No customer credentials changed.

One combined successor and its unchanged-release ten-user customer cohorts are
next. No additional v56 instances will be launched for the other five users.
Rene's cloud migration remains held until the final candidate qualifies; local
migration evidence alone does not authorize a customer-ready claim.

### 19:14 UTC — combined v56 tested; replacement creation errors

The complete v54/r7 cohort is terminal:01,04,05,07,09 delivered independently
verified artifacts through the actual UI.02,03,06,08,10 did not finish complete
studies. Successful inference alone was not counted as successful delivery:
02 completed four inferences before Protenix analysis failed;06 completed twelve
Evo2 calls before a generated script failed;10 generated a valid Cosmos MP4 but
the native client incorrectly tried to parse it as JSON.03 admitted no Study;
08's explicitly expected short-source no-report outcome blocked its final report.

Combined successor v56 is frozen at
`cba6304ec772a70cc7fccf44743145b0a7e3a479`, published as
`lc:r0919-v56-cba6304`, index
`sha256:7b5b3b46713b61fd5fafc8085fa29fd8fc54f631a993c1aa28c4aa7d9e842c3c`.
It includes strict JSON-text plan support, actual Protenix provenance, typed
Evo2/robotics analysis, explicitly permitted clinical no-report outcomes, verified
binary native artifacts, and cancellation parsing/identity fixes. v55 was
published but never deployed. Scientific prompts, seeds and limits are unchanged.

Exact installed-image qualification passed18 runtime hashes,11 SDK cases,
10 receipt-lock tests and61 domain tests, including dependent report publication,
binary media and cancellation after replacement. The source and runtime files
were not overlaid during testing. A separate real-Mongo replay preserved Rene's
49 collections,81 documents,334 index definitions, two state files, password and
original chat across login/restart. It used retained state, not a fresh live
cutover archive. See [installed-image and migration evidence](evidence/20260919-installed-v56/README.md).

Only archived test instances02/03/06/10 were deleted, with final NotFound checks;
their endpoint/local databases cannot be restored, but archives and tenant buckets
remain.08 is stopped: its delete command and one reconciled retry both returned
provider Internal. All three initial v56 creates also returned Internal and the
exact-name inventory contained no created resources. A single reconciled02
creation retry is being checked. No quota or resource-policy increase was made.

Scientist10's original one cancellation POST remains retained. It exposed a flat
native-status parser defect; no repeated POST or manual receipt repair was used.
Its same-owner/key successor must reconcile the saved intent and visibly unblock
the queue before new work. The original MP4 has been recovered and hash/codec
verified read-only, not relabelled a successful original study.

Backend190 remains deployed with three ready gateways and two controllers.
Rene's original endpoint is unchanged and its login page returns HTTP200.
The five affected natural reruns, unchanged-release integrated cohorts, actual
successor cancellation recovery and Rene's cloud migration remain outstanding.

### 18:22 UTC — four delivered workflows; remaining six continue

Four v54/r7 studies completed after witnessed browser closure and delivered
independently checked reports through actual UI downloads:

| Scientist | Outcome | Accepted to finished | UI downloads |
| --- | --- | --- | --- |
| 01 OpenFold2 | New prediction; 76-residue fit/confidence independently recomputed | 38.740 s | 8 |
| 05 chemistry | Four docking calls/16 poses and GenMol/16 unique valid molecules; poor results retained | 165.909 s | 8 |
| 07 aging | 32 PhenoAge and 17 AltumAge outputs; exactly one matched-sample overlap | 145.991 s | 7 |
| 09 retained MindEval | Six full records, 126 messages and 30 scores; no new consultations or judging | 4.836 s | 22 |

These are complete-study timings, **not cold-start benchmarks**. The09 disconnect
witness is only0.676 s; the other witnesses were35.929/160.611/140.694 s before
completion. Source reports: [OpenFold2](evidence/20260919-openfold2-natural-v54/README.md),
[chemistry and aging](evidence/20260919-chemistry-aging-natural-v54/README.md),
[retained MindEval](evidence/20260919-mindeval-natural-v54/README.md).

The aging interim chat incorrectly called its inputs the same sample. Its final
deterministic report correctly describes1 versus16 samples and one overlap;
retain this wording defect rather than claiming error-free conversation.

The temporary credentials expired at18:13 UTC after these four studies finished.
Asking the user to approve routine disposable-test credential maintenance was
unnecessary; that question was withdrawn and corrected in the same Slack thread.
Existing API policy rejects expiry updates/rotation after expiration. Six new
test keys were therefore issued through the supported API for02/03/04/06/08/10,
with exactly the same tenant/principal, grants, concurrency1 and other budgets,
expiring at the previous expiry plus24 h. No customer key or quota was changed.
The original private manifest and four completed clients remain unchanged; the
separate successor manifest is retained under
`remaining-scientist-key-renewal/scientists-private.json` in the protected run root.

A new key has a different backend history identity and Study fingerprint.
Installed-v54 verification confirms that fresh same-user instances can execute
new r7 studies while old receipts remain unchanged and excluded; it does **not**
claim transparent key rotation/history continuity. Settings PUT alone does not
reload environment-bound MCP/worker credentials. This limitation is documented,
not bypassed by database edits or widened operation access. New dedicated clients
02/03/04/08 are provisioning;06/10 follow. Remaining natural qualification and
Rene's state-preserving upgrade are still outstanding.

### 18:00 UTC — preview address reuse and credential boundary

Stopping v52 previews did not release public addresses. Four v54 create attempts
were rejected by the existing IPv4 quota, with no matching resource created.
The ten exact archived/stopped v52 endpoints were then deleted and confirmed
NotFound, without a quota increase. Their local instances cannot be recovered;
captured transcripts/configuration/output evidence and persistent buckets remain.
Two v54 successors are provisioning; two additional provider-Internal rejections
were reconciled absent before a single explicit operator retry. No natural v54
study has been admitted at this checkpoint.

The unchanged r7 fixture/observer preparation passed25 offline tests. Eight
additional02/03 verification regressions reject missing case pairs and the old
empty protein-design report. These are not live customer passes. Rene's v54
migration helper is prepared only, with six binding tests; his existing client
has not been changed. The test-key renewal decision is outstanding; one blocker
DM was sent to Rene at17:57UTC. Keys/permissions/limits remain unchanged.

### 17:55 UTC — recovery deployed; exact client candidate verified

Backend Helm190 is deployed from `c154d77654a16b5cfdf732f505467ac981b6479f`
with three ready gateways and two ready controllers. A fresh, separately labelled
RFdiffusion48-residue/seed1 operation survived an exact owned-worker eviction:
the durable Job retained `DisruptionTarget`, attempt2 completed within the existing
two-attempt policy, reservations were released, and result hashes plus48-residue
structure integrity passed independent checks. This qualifies maintenance-worker
eviction, not whole-node loss, actual provider preemption or the complete failed
v52 RF→ProteinMPNN→ESMFold study. The earlier failed study remains failed.
See the solutions-library `acceptance/worker-disruption-20260919/README.md`.

The ten v52 test clients are archived and **stopped, not deleted**. Separate
per-user successors are deploying. Rene's existing client, other customers and
tenant buckets are unchanged. No request, quota, retry, execution or token limits
were increased.

Client v53 passed installed tests but was never deployed. Its successor v54,
source `12fb896b4dd6c3b856b4b07da903bad08546a0ec`, additionally synchronizes
same-user receipt publication/observation with a short local reader/writer lock.
It does not fall back to stale receipts or hide a partial journal after a crash.
The source race was reproduced; the original live503's exact cause is still
unproven because its underlying exception was not retained.

Published v54 index:
`sha256:c5d01a265447b6d89c155c6266acdad18e158b78eba8888fa2586b41234d421a`.
Exact installed tests passed ten runtime hash checks, eleven SDK cases, five CPU
Studies with30 nonempty independently verified final files, and ten receipt
publication/crash regressions. Tests used no network/model calls or replacement
runtime files. Receipt SHA256:
`c0907518eb8e8637fbd778c1c2fd79cea751895f24920705a94b0087b2a38db2`.
These tests do not replace the unchanged natural scientist cohort or a qualified
Rene migration. Temporary test keys expire around18:13UTC; a24-hour extension
was requested from the user and has **not** been applied. Do not admit known long
studies across that expiry while authorization is unresolved.

### 17:30 UTC — v52 outcomes and observed-defect repairs

All ten dedicated v52 instances received one unchanged scientific prompt, with
only fresh r6 output roots. No follow-up instruction repaired a failed study.
07 aging and09 reuse-only MindEval passed numerical verification and actual UI
downloads.09's witnessed browser close preceded completion by only0.134seconds,
not a long-disconnect proof. The remaining results were:

| Scientist | Actual outcome | Repair or next evidence |
| --- | --- | --- |
|01|OpenFold2 and comparison finished; final publication referenced a nonexistent CSV|Known helper-output preflight|
|02|Both Boltz2 calls succeeded; malformed Protenix parameters rejected before inference|Validate exact parameter schema before uploads; expose actionable error|
|03|Proteina and BoltzGen succeeded; report contained empty tables because generic artifact filenames were guessed|Manifest/hash-aware deterministic design analysis|
|04|Controlled RF worker eviction became a non-retried application failure|Retain disruption reason on Job; existing two-attempt policy unchanged|
|05|Four DiffDock calls plus GenMol succeeded; generated Python misread the bindings-file ABI|Exact ABI guidance and deterministic GenMol helper|
|06|No Study; references pointed at not-yet-existing output directories|Explicit typed future-file references/preflight|
|08|No Study; normal final response stopped after preparation|Provider finish reason remains unknown; enable existing response-metadata diagnostic on next candidate|
|10|No Study; write-json used a Markdown filename|Typed JSON-basename validation|

v53 candidate source `77994a39a9d0da6b78c9eb882bee66710bffe7a1` combines the
client fixes and is building. Backend190 candidate
`c154d77654a16b5cfdf732f505467ac981b6479f` passed142 focused tests and the target
API-server policy dry-run; image-only rollout and new RF recovery are pending.
No token, concurrency, retry, resource, quota or deadline limits were raised.
Per-user endpoints remain separate. Rene's original client is unchanged.

### 16:53 UTC — candidate cohort deployment

Backend189 remains live: gateway three ready replicas, controller two, and the
qualified contention/accounting/fit changes are intact. The new client candidate
is source `e4005cea9e8dd4429064104a53861e8a877016a9`, immutable image index
`sha256:0c2a60ea79d3a2ff27c3927964ad5ddb95b02c7f21d94a86990b40200a29f182`.
Its installed baseline eleven SDK cases and semantic preflight/381-character
report-title regression passed. Removing an arbitrary report-heading cap does
not increase any inference, context, execution or request budget.

Ten separate user instances are being deployed for the unchanged scientific
acceptance prompts (only their output root changes to `unattended-20260919-r6`).
The explicitly selected planner candidate is `moonshotai/Kimi-K3`, low reasoning,
131072 context and the unchanged 8192 output budget. This is not yet a qualified
production default. Prior Qwen, Kimi and GLM comparisons remain failed evidence;
provider token exhaustion is not inferred where finish reasons were absent.

All ten v49 previews and the v50 report-comparison preview were archived,
terminal-checked and deleted with final NotFound receipts. Together with the
earlier twelve, this reclaims twenty-three disposable endpoints without raising
the public-IP quota. Their endpoint IDs/local databases are not recoverable;
protected transcripts/configuration/artifacts and all tenant buckets remain.
Rene's existing client is still unchanged. The final cohort must finish before
its state-preserving replacement is promoted.

### Latest v49/189 customer-path results

All ten separate v49 instances were deployed without a quota increase and received
one uncoached frozen prompt each (only output roots changed). Three studies
completed through saved preparation, inference, analysis and final publication:
ubiquitin/OpenFold2, chemistry/DiffDock+GenMol, and aging/PhenoAge+AltumAge.
Independent numerical recomputation passed. Actual Runs→Workspace browser
downloads passed for all eight, fourteen and thirteen declared files respectively.
The aging study completed after its browser closed while a PhenoAge step ran.
The other two closures were after completion or not witnessed before completion;
do not count them as cloud-disconnect proofs. The initial observer also missed
legitimate nested output directories, now corrected in the private test harness.

Seven other v49 conversations failed before admitting a study. The complex
comparison ended normally but asked for continuation; the clinical and retained
MindEval tasks have explicit truncated tool-argument errors. The remaining four
ended without a usable final answer. The detailed PD-L1 trace proves reasoning-only
normal graph termination, not an observed client abort or hard tool-step limit;
the provider finish reason/main-generation token usage is unavailable. No output
limit, timeout or scientific parameter is being changed to label these successful.

v50 (`6e1ef68`, index `c8c3e411599a42afe6d00dcc4be573f8d72322616f09a86c0e881fb2fb2ef3dd`)
adds a generic incremental typed plan composer over the same validator/runner.
All eleven installed LibreChat/SDK cases passed, including grouped composition,
disconnect/reconnect and worker completion. Local Rene import/seed/login checks
also passed, but no customer cutover occurred.

Two separately labelled Qwen planner tests **failed**. On v49 it admitted compact
MindEval records that the report worker correctly rejected. On v50 it bypassed
the study path, copied earlier files and claimed completion after report-tool
errors. Independent checks verified the copied 126 transcript messages and 30
scores, but not new analysis, full native records, new provenance or durable
completion. See [v49 comparison](evidence/20260919-planner-qwen-diagnostic-v49/README.md)
and [v50 failure](evidence/20260919-mindeval-qwen-v50/README.md).

v51 source `1fbbaf09f710692dd63f818cfeebde1e6bdfd1fc` moves the existing full-record
validator into shared preflight, so invalid inputs are returned to the planner
before admission. It also rejects known directory outputs as file deliverables.
All 222 source tests pass; eighteen scientific outputs from full retained records
are byte-identical. Image index `a48f373b30db574d76f96646e308ceb03ad330f100a0af89e2899402dd7a9803`
is published; installed-image and natural-client gates are pending. Two additional
report-only planner comparisons are running on v50 with unchanged scientific
inputs and limits. No successful planner/default decision is implied.

The archived failed v49 previews are being retired to reuse existing public-IP
capacity, not raise quotas. Some provider stop/delete requests returned Internal
errors; exact-state reconciliation and bounded operator actions are retained.
Buckets and verified results remain. Rene's original endpoint is unchanged.

Backend189 is deployed. Its corrected app-bound concurrency test passed six
overlapping metrics reads and two public history reads, including a history read
on the metrics-loaded gateway. Earlier public404/Pod-proxy-timeout harness failures
remain recorded separately. Retained accounting, node-fit and model-discovery
assertions passed. Source evidence is in the solutions-library
`k8s-inference/acceptance/reporting-contention-20260919/README.md`.
Successful report evidence is in
[chemistry and aging v49](evidence/20260919-unattended-chemistry-aging-v49/README.md).

Latest integration update (the dated evidence below remains historical):

- Combined backend188 restored the accounting/fit changes while retaining the
  separate Cellpose/scVI onboarding. Two retained-history reads still returned
  503 during slow overlapping metrics reads. Candidate189, source
  `bbcec4d515d7d53cabc10d185d48adb4ddb6435e`, coalesces only concurrent identical
  metrics collections and adds request-correlated history phase diagnostics.
  It does not cache old metrics or increase pools/timeouts. Its immutable index
  is `sha256:2e72e6d90e76acdd051e6148a0bb562720cedb8e57744e60d88402a75df71a19`;
  rollout and bounded live contention regression are in progress.
- The v48 installed helper tests passed, but the two attempted natural
  conversations did not admit durable studies. The first fell back to a
  process-bound OpenFold2 job, which completed; that is not unattended-study
  acceptance. The other eight natural prompts were not submitted. Investigation
  found that the actual MCP child omitted owner/clinical environment bindings
  and used the system Python rather than the packaged scientific interpreter.
  The second conversation ended before attempting admission; that failure must
  be retested rather than assumed explained by this fix.
- Candidate v49, source `4bd45eaafb6112ec2cae5df253c2403d07d792c3`, repairs that
  exact process boundary. Immutable image index
  `sha256:202b76200becd455cbed9a402e3b9b12d6d03f8da692f787e5a12d0471c3824f`
  passed ten installed LibreChat environment-substitution/SDK transport cases.
  Two CPU studies completed after disconnect and their eight final files were
  independently read back. This does not replace the fresh browser cohort,
  whose dedicated per-user instances are now being deployed.
- A public IPv4 quota blocked six v48 endpoint creations. No quota was raised.
  Twelve superseded test previews were archived, checked for terminal work, then
  deleted to reclaim addresses. Their endpoint IDs/local test databases cannot
  be restored; configuration, conversation evidence and output files are retained,
  and tenant buckets/customer endpoints were untouched. No v48 owner remains
  active. Rene's original client is still unchanged pending final qualification.

- Backend Helm184 is deployed from `3dccbdc878225fb7b26fa79fd5295f5c646d71a8`:
  gateway/controller image index `sha256:be36dc7cf85618de274a50b08ff890261c70596e0b531d7681c8e368c1f5d089`,
  admin index `sha256:72581f9f4035742e8c0b52a197c9b9a702f17fe8a6a837990dd2f7bf42ce4ae4`.
  Lifecycle partitions, missing-sample distinctions, per-node upper-bound fit
  and bounded durable GPU activity summaries passed live acceptance. Helm185
  (`a2b6f5885`) then corrected CPU capacity-pool selector aliases. A separate
  visual-model onboarding deployment at 14:39 replaced this image with an older
  source line and temporarily removed these fixes. The publishers are coordinating
  one combined release; do not deploy either incomplete branch over the other.
- Live maintenance-eviction recovery passes on Helm183: operation
  `59cc8d6a-0791-4df6-8695-2d460077366c` retained one workload, exactly two attempts,
  released both reservations, and produced independently verified artifacts.
  The identical eviction on baseline182 failed. This is not a whole-node outage test.
- The first integrated client candidate was source `92047e435c9484efba58be32755ccaddde73b150`,
  image `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:r0919-v47-92047e4`,
  immutable index `sha256:950b924fd117f4bd64f4592d9ffd6d659f240968bad858c095259724336f630e`.
  Its installed-image gate passed 49 tests plus two actual Markdown-renderer
  tests. A killed/restarted container resumed a saved recorded-data study and
  delivered seven files; all four numeric formats reopened with exactly the
  original 128 rows, nine fields and 6,144 values. No hosted model/network calls
  were made by that local test, so it does not replace live customer acceptance.
- [Ten frozen natural studies](unattended-acceptance-20260919/README.md) were
  submitted once through ten separate ordinary-user browser clients. Read-only
  source preflight passed all ten input sets and historical
  hashes. Matching-sample and old-index ambiguities are retained for the natural
  agent to resolve, not silently repaired or coached away. **None of the ten
  v47 conversations admitted a durable study.** Full caller operation histories
  confirm zero new hosted operations; these are planning/delivery failures, not
  ten failed model inferences. Some answers asked for continuation; others ended
  incomplete, and the robotics tool arguments were truncated. The three textual
  claims of an exhausted tool budget were not hard-limit terminations: retained
  normal FINAL events and installed controller behavior establish the distinction.
  Provider finish reasons remain unknown where not retained.
- Candidate v48, source `6c9d0ecd03181cbf4f6df26351d74680708b5923`, repairs concise
  typed workflow discovery, the misleading file-backed v2 plan description,
  deterministic MindEval record analysis and explicit sole-protein-chain selection.
  Source tests pass; the image is being built. Fresh natural tests will change
  only output directories, preserving the failed cohort rather than coaching it
  to completion. No limits were raised.
- [Snapshot comparisons](evidence/20260919-scientific-snapshot-comparison/README.md)
  completed 24 operations across four models. Actual restore, mixed restore and
  normal-loading fallback are reported separately. Driver-mismatch fallbacks,
  nondeterministic Protenix variation and absent end-to-end speedup remain explicit.
  All temporary model policies were restored; no unsupported snapshot is called qualified.

Existing services, customer data and rollback identities are retained. Rene's
existing chat database/private configuration has a protected logical backup;
his replacement is not yet deployed. A network-isolated, exact-v47 migration test
preserved Mongo BSON documents/indexes, existing login and chat history across
restart; cloud migration remains gated on the final client acceptance. No
shared-user LibreChat instance was introduced.
