# Scientific qualification checkpoint — 19 September, 04:04 UTC

The agreed twelve-hour test/fix campaign continues until06:04 UTC. This is not a
customer-readiness certificate. Original failures and operator interventions are
retained; no quotas, worker limits, model budgets or rollout timeouts increased.

## Executed work and denominator

The03:56:21 aggregation contains2,002 distinct top-level model operations:
1,666 serving and336 scientific batch. It separately records12 child operations.
There are1,816 terminal service successes,65 success receipts not independently
joined to an operation observation,111 failures, and10 ongoing/cancelled records.
Independent checks are1,722 pass,59 fail,1 mixed and220 unlinked. These are
historical mixed-release campaign counts, **not a final-release pass rate**.

MindEval provider completions are a separate population:494 observed at this
checkpoint, including368 responses in the new60-consultation public batch.
Planned turns are not completed calls; no judgment in that batch had completed.
The batch uses its existing one-worker policy and round-robin turn scheduling.

Protected reproducible reports:
`Q/campaign-reports/interim-20260919T0356Z` and
`Q/campaign-reports/latency-interim-20260919T0356Z`, where
`Q=/home/tux/secure-handoff/scientific-qualification-20260918`.
The latter has575 Ready-before-admission witnesses and1,427 unknown thermal
states. Neither generic `cold_start_seconds` nor batch `started_at` isolates
weight loading or GPU compute. Unknown values are not zero.

## Exact deployed backend

Helm179 settled on source`be9f21218c5f236a760d4b93e0b76fcd467331e0`.
Control-plane index:
`sha256:1515a260e039a208ba40362874ac504b2fa26b0b9be2828a019a7d24c20f68ca`.
Deployment/baseline receipts are`Q/backend-release179` and`Q/backend-baseline179`.

- Compact schema discovery is live: Cosmos full canonical JSON55,820B,
  transfer-only9,022B and summary795B; selected contracts are unchanged.
  LeRobot summary185B versus complete15,232B. This avoids importing unrelated
  schemas; it does not raise a context budget.
- DiffDock keeps the same wrapper-only image`0c717984…`, now with the exact
  required model-revision annotation. The first new public operation has verified
  Pod/node/GPU identity. The full frozen12-case repeatability/attribution cohort
  is running; numerical variation remains a separate unresolved finding.
- LeRobot preservation coordinator`69fe161d…` is deployed. Its published4CPU
  fixture replay fell from492.993s to73.227s with bounded BLAS threads, preserving
  untouched video bytes and numeric data. This is not whole-workflow GPU latency.
  A fresh public full-sequence workflow is next; physical motion/action alignment
  remains a separate quality question.

## Customer-shaped outcomes and remaining blockers

- Clinical scientist08 completed four fresh ASRs plus one draft through three
  ordinary chat turns. Seven report files and the index were browser-downloaded
  and byte-verified. All33 accepted facts/40 phrases have exact source spans and
  adjacent context; the former invented medication brand is absent on the same
  transcript.18/20 source segments are represented, not proof of completeness.
  The planner overclaimed completeness from keyword checks; its saved WER scorer
  also differs from emitted English counts by one standalone`--` token. These
  negatives are retained and a deterministic reporting helper is being repaired.
- Three new Proteina four-design requests completed with verified artifacts at
 431.285/440.857/524.087s end to end. No experimental binding claim follows.
- The held-out BindCraft/Mosaic/RFdiffusion batch has one ongoing BindCraft
  search. Logs confirm active candidate evaluation, not a hung worker. Its
  initial18-minute queue interval is measured separately from execution.
- Robotics clientv39 failed to complete the natural workflow before admission.
  v41 fixes exact-tool discovery and bounded streaming artifact downloads; its
  immutable image passes installed-helper tests, but two Serverless Create calls
  returned Internal. Exact-name reconciliation found no created endpoint.
  The working preview and Rene's production client are untouched. One blocker
  DM was sent with request/trace IDs; no blind retries or unsupported updates.
- A small Runs display correction is source-tested, not deployed: scientific
  orchestration says “Workflow active” rather than implying GPU admission, and
  the legacy timing label explicitly includes queue time. Backend phase evidence
  and original receipts remain unchanged.

Two unchanged clean final cohorts for the complete platform have **not** been
achieved. API service success, natural workflow delivery, scientific validity,
clinical completeness and robotics-policy suitability remain distinct gates.
