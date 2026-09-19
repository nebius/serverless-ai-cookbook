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

In progress as of 19 September, 14:13 UTC. This is not a final readiness claim.

- Backend Helm184 is deployed from `3dccbdc878225fb7b26fa79fd5295f5c646d71a8`:
  gateway/controller image index `sha256:be36dc7cf85618de274a50b08ff890261c70596e0b531d7681c8e368c1f5d089`,
  admin index `sha256:72581f9f4035742e8c0b52a197c9b9a702f17fe8a6a837990dd2f7bf42ce4ae4`.
  Lifecycle partitions, missing-sample distinctions, per-node upper-bound fit
  and bounded durable GPU activity summaries are deployed. A CPU pool alias
  display defect found during live acceptance is being corrected separately.
- Live maintenance-eviction recovery passes on Helm183: operation
  `59cc8d6a-0791-4df6-8695-2d460077366c` retained one workload, exactly two attempts,
  released both reservations, and produced independently verified artifacts.
  The identical eviction on baseline182 failed. This is not a whole-node outage test.
- The final client candidate is source `92047e435c9484efba58be32755ccaddde73b150`,
  image `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:r0919-v47-92047e4`,
  immutable index `sha256:950b924fd117f4bd64f4592d9ffd6d659f240968bad858c095259724336f630e`.
  Its installed-image gate passed 49 tests plus two actual Markdown-renderer
  tests. A killed/restarted container resumed a saved recorded-data study and
  delivered seven files; all four numeric formats reopened with exactly the
  original 128 rows, nine fields and 6,144 values. No hosted model/network calls
  were made by that local test, so it does not replace live customer acceptance.
- [Ten frozen natural studies](unattended-acceptance-20260919/README.md) are
  prepared. Read-only source preflight passed all ten input sets and historical
  hashes. Matching-sample and old-index ambiguities are retained for the natural
  agent to resolve, not silently repaired or coached away. New separate user
  instances are being provisioned; provider create failures are reconciled by
  exact identity before any retry. No limits were raised.
- [Snapshot comparisons](evidence/20260919-scientific-snapshot-comparison/README.md)
  completed 24 operations across four models. Actual restore, mixed restore and
  normal-loading fallback are reported separately. Driver-mismatch fallbacks,
  nondeterministic Protenix variation and absent end-to-end speedup remain explicit.
  All temporary model policies were restored; no unsupported snapshot is called qualified.

Existing services, customer data and rollback identities are retained. Rene's
existing chat database/private configuration has a protected logical backup;
his replacement is not yet deployed. No shared-user LibreChat instance was introduced.
