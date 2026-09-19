# Scientific AI: twelve-hour qualification checkpoint

**Draft in progress.** The agreed campaign window is 18 September 2026,
18:04 UTC to 19 September, 06:04 UTC. Final accounting below will be frozen
after the observation window closes. This is not a customer-readiness certificate.

## Outcome and scope

Substantial platform defects were found, repaired, deployed and retested with
real public data and actual customer interfaces. However, **the platform is not
yet qualified for broad unattended scientific use**. Correct model artifacts
can still be accompanied by incomplete or incorrect agent analysis, and some
workflows required substantive operator help. Those are customer failures even
when the underlying model call succeeded.

Ten scientist identities, ten isolated LibreChat workbenches and three lab
buckets were used. Dedicated instances were necessary because the existing
general-chat MCP/execution identity is deployment-scoped. This is **not** a
qualification of ten different users sharing one LibreChat instance. Existing
cluster workloads were preserved; no quota, concurrency, context, output,
tool-round, retry or rollout-timeout limits were raised.

The [ten-scientist delivery matrix](personas.md) distinguishes natural completion,
ordinary continuation, methodological coaching and manually recovered outputs.
The [all-App coverage index](../20260919-campaign-coverage/README.md) separately
covers 35 captured App instances across 33 model identities: 32 H100 campaign
models, deliberately excluded GLM-5.2 and two disabled clones. It retains its
04:37 cutoff; later evidence below does not silently rewrite that snapshot.

## Measured workload

Final deduplicated counts and source hashes: **pending the 06:04 freeze**.
Historical failures remain in the denominator. Polls, uploads, seeded greetings,
offline rescoring, unit tests and retries without independent attempt identities
are not additional model calls. Serving/scientific model requests and Token
Factory conversation completions are reported separately.

These are mixed-release diagnostic and repair cohorts, not a homogeneous
pass-rate benchmark for the final release. Service success, independently
checked artifacts, scientific validity and natural-client delivery are separate
measurements. Missing evidence is unknown, not a zero or a pass.

## What was repaired and tested

The full chronological record is the
[defect ledger](../../QUALIFICATION_DEFECTS_20260918.md), including unsuccessful
candidates, rollbacks, original failures and operator interventions.

- **Model execution and contracts:** exact-yield/error handling for molecular
  generation; unresolved-residue handling for ProteinMPNN; CT point-mode
  compatibility/dependencies; Evo2 long-input memory and health serving;
  OpenFold3/OpenBind shared-memory loading; additional Proteina and BoltzGen
  modes; typed scientific input manifests and actionable validation.
- **Result integrity and recovery:** Proteina raw/refold artifact roles and
  gzip-byte verification; durable customer run discovery; disconnect/resume;
  bounded lossless downloads; verified publication to bucket-mounted storage.
  A bucket is not a POSIX filesystem: seekable scientific outputs need explicit
  local staging before closed-file publication.
- **Cosmos/robotics:** replaced the incompatible checkpoint path, verified strict
  CUDA/CRIU restoration, repaired exact frame/dimension and untouched-camera
  preservation, and recorded actual serving replica/GPU identity. The later
  natural workflow delivered verified files but retained reporting mistakes.
- **DiffDock:** deterministic repeatability repairs and exact serving identity.
  Two release-179 public 12-case cohorts returned 24 verified results and all
  24 have replica/node/GPU attribution. Poor experimental agreement and the
  extreme pose outlier remain scientific findings, not removed test cases.
- **Backend/admin reliability:** indexed subject-scoped usage queries; narrowed
  observer imports/tolerations; exact disruption classification; status-only
  snapshot selection projection. Release 182 repaired the live strict-schema
  failure exposed by release 180; rollback 181 is retained in the evidence.
- **Client/reporting:** actual provider-catalog model selection, exact deferred
  tool discovery, token accounting, bounded waits, installed clinical metrics,
  literal source spans/context and typed no-supported-facts outcomes. These
  fixes do not make the remaining narrative clinically reliable.

### Larger scientific studies completed

- [Held-out design batch](../20260919-heldout-designs/README.md): **13/13**
  BindCraft/Mosaic/RFdiffusion requests returned verified artifacts. The longest
  request took 8,416.1 seconds through client verification; its approximately
  18-minute placement wait is separately recorded.
- [Design/refolding study](../20260919-design-refolding/README.md): **220**
  completed downstream refolds. Sequence/finite-coordinate checks and actual
  RMSD/lDDT distributions are retained, including poor self-consistency.
  Computational checks do not demonstrate affinity or experimental efficacy.
- Speech: the 119-case study retained 118 nonempty transcripts and one empty
  result. Reference WER and perturbation/reference limitations remain explicit
  in the ledger. The later [v42 clinical study](../20260919-natural-clinical-v42/README.md)
  reused four ASR outputs; it is **not** a fresh speech benchmark. Two drafts
  and one expected no-report outcome produced 24 verified browser downloads.
- [Natural robotics v42](../20260919-robotics-natural-v42/README.md): native and
  two-episode dataset outputs delivered after two ordinary continuations;
  128 rows, 6,144 non-video values and untouched wrist media independently
  preserved. Correct files do not establish physical/action alignment.

## Waiting, elasticity and snapshots

The [capacity and waiting evidence](../20260919-capacity-wait-fairness/README.md)
shows shorter requests completing while the long BindCraft job ran. Its wait
had an actual placement/quota explanation: the job requested 16.1 CPUs whereas
the 1×H100 nodes offered 15.9 allocatable CPUs, and required the reference-data
reserved pool. Merely counting spare GPUs would have been misleading.

Capacity/preemptible supply loss is not counted as model failure. Misclassifying
that loss or failing to recover is a software issue. The deployed repair has
retained-event and bounded-controller test evidence, plus a separate successful
same-payload replay. **Automatic recovery through a new live node-loss event
remains unqualified**; the replay does not prove it.

No arbitrary fair-share/noisy-neighbor guarantee follows from the observed
mixed-workload progress. GPU reservations are not utilization or billable GPU
hours. Complete GPU occupied-idle, loading and cooldown reconciliation remains
open. Accepted-to-ready timing includes dispatch/queue/activation; it must not be
marketed as pure cold-start or weight-loading time.

Strict Cosmos restore evidence applies to the exact image/checkpoint and
tested H100 configurations. Warm-host-cache restoration excludes fresh-node
provisioning and image pulls. Other Apps' historical snapshot implementations
are retained, but image/configuration changes do not inherit exact-current
qualification. The status-only release-182 projection intentionally leaves
unmeasured qualified/effective fast-start levels unavailable rather than
manufacturing measurements.

## Deployed state and access handoff

Public backend/admin/MCP remains at `https://89.169.99.188` (`/admin`, `/mcp`).
The exact backend is **Helm 182**, source
`8e747def5f31b82014d9daeba97d4711b960adca`, OCI index
`sha256:f3a3d6c2d4e28b6f8693e6cc65c6d9b63ecd4e54e8e13d170059f4e85d0a60f6`.
The frozen suite passed **2,760 tests**, with five skips and 130 deselections;
those exclusions are not passes. Live acceptance includes eight external API
reads, six per-Pod reads and 32 browser admin GETs, all HTTP 200. The 21 model
specifications and 33 generated Pod templates remained unchanged.
See [exact release verification](../20260919-admin-apps-reliability/README.md).

Client v43 is deployed to isolated scientist10 endpoint
`aiendpoint-e00s62sznpcf4h066c`; runtime source
`31ea81371b31a06cc9b7366963dcbcc9f72d7453`, image index
`sha256:6b03912b411c32c66bc22bdd1e0962f5c6e168962a5fd8077eae4f1cb0ada554`.
[Installed-image evidence](../20260919-integrated-client-v43/README.md) is
separate from its still-running natural export check. The existing Rene endpoint
`aiendpoint-e00hf15nz04eqt6b9q` was **not** silently replaced by a test build.
Preview credentials remain in protected deployment receipts, never this repo.

Latest read-only resource handoff: [live state](live-state.md), with its own
observation timestamps. Healthy previews, customer resources, buckets, completed
artifacts and any already-admitted durable work are retained for review.

## Remaining work, in priority order

1. **Trustworthy end-to-end reports.** Fix schema-bound clinical fact counting,
   omitted-source/coverage reasoning and unsupported metric interpretations.
   Eliminate remaining substantive method coaching in the design/complex
   journeys. Re-run unchanged customer-shaped tasks on one frozen client/backend.
2. **Complete artifact UX.** Close ordinary scientific export verification and
   direct clickable-download handling. Preserve the first failures; require
   byte checks through the actual browser, not only storage/API reads.
3. **Customer identity and lifecycle.** Qualify true shared-instance multiuser
   execution/bucket bindings if that is the intended deployment; separately
   qualify bounded automatic recovery with task-owned capacity-loss evidence.
   Keep all existing limits and unrelated workloads unchanged.
4. **Advertised modes and performance.** Finish exact-current per-App/mode
   coverage and snapshot/cold-state measurements. Do not replace absent timing
   with zero, or trade away output quality to claim a speedup.
5. **Scientific scope.** Physical robotic action alignment, clinical correctness,
   experimental efficacy and paper-level replication need their own suitable
   evidence. The present campaign is not a substitute for those evaluations.

The linked Task Deck cards remain open where these criteria are unmet. No
platform-wide “done”, “all models optimized” or 10/10 claim is justified.

## Resume without duplicating work

- Workbench/code/evidence: `rene-tech/serverless-ai-cookbook`, branch
  `agent/scientific-ai-workbench-v2-20260918`, local worktree
  `/home/tux/worktrees/scientific-ai-workbench-v2-20260918`.
- Backend: `rene-tech/nebius-solutions-library`, branch
  `agent/fs2-cosmos-stockholm-remediation-r20260917`, local worktree
  `/home/tux/worktrees/fs2-cosmos-stockholm-remediation-20260917`.
- Parent task: `dashboard/data/epics/nim-fast-start-platform/tasks/`
  `fs2-scientific-workload-qualification-r20260918/task.md`.
- Protected raw evidence root, abbreviated **Q**:
  `/home/tux/secure-handoff/scientific-qualification-20260918`.
  Never publish its identity manifest, raw clinical conversations, credentials
  or signed object URLs. Published summaries contain scoped findings and hashes.
- Backend rollout/baseline: `Q/backend-release182`, `Q/backend-baseline182`.
  Client deployments: `Q/workbenches-v42-deepseek0813`,
  `Q/workbenches-v42-clinical`, `Q/workbenches-v43-deepseek0813`.
- Continue existing durable operations by their recorded IDs/idempotency keys.
  Do not resubmit completed science to collect the same artifact. Read actual
  latest status before resuming observers. A process exit is not cancellation
  of server-side work.
- Task Deck main is published through the existing clean qualification worktree;
  the dashboard working tree contains unrelated changes. Preserve them and
  stage/publish exact paths only. No new branch fan-out is needed.

The twelve-hour checkpoint is a review boundary, not permission to extend a
test campaign indefinitely or to cancel live customer work. Further admissions
after the boundary require the next agreed scope; existing durable work may
finish and should remain visible.
