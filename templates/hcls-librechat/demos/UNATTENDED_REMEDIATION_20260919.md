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

In progress. No deployment or readiness claim for the successor yet. Existing
services, user data and rollback identities are retained.
