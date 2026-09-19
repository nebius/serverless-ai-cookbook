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

### 16:53 UTC — final-candidate cohort deployment

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
