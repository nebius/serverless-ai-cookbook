# Scientific workload qualification campaign

Prepared 18 September 2026. Status: active test/fix/retest campaign since 18:04
UTC; review checkpoint 19 September 06:04 UTC. Owner: primary Scientific AI manager.

## Objective and current verdict

Emulate scientists using the deployed Scientific AI LibreChat workbench and
hosted APIs for sustained research, expose defects before customer evaluation,
fix them, and produce a reproducible, scoped readiness verdict. Existing evidence
does not establish readiness for this scope.

The previous cohort completed eight top-level scientific operations, one clinical
workflow and one short MindEval workflow. It exposed real issues but largely used
single fixtures. Some operations were submitted outside the chat agent; evidence
spanned R3 through R11. Those results are historical diagnostic evidence and do not
qualify every workflow on the final R11 release.

Use the platform's existing CUSTOMER_RELEASE_POLICY.md. This plan extends the
workload coverage; it does not replace that policy or introduce new production
audit requirements.

## Agreed execution envelope

- Ten simultaneously active scientist sessions with queued batch studies.
  Session concurrency differs from admitted model concurrency. Do not raise
  existing customer limits or run the earlier proposed thirty-session burst.
- Start 2026-09-18 18:04 UTC; user review checkpoint 2026-09-19 06:04 UTC.
  Work in a test/fix/retest loop for twelve hours. Fit sustained observation
  into this window; the earlier proposed 24-hour soak is superseded.
- Capacity or preemptible unavailability is not a software failure. Record
  capacity-deferred work, wait times and customer-visible progress separately.
  Lost jobs, starvation, broken recovery and misleading success remain defects.
- Share capacity with existing and arriving workloads. Vary inputs and include
  exploratory studies beyond these ten personas. Optimize for fast completion,
  durable batching, fairness and intelligible waits under available capacity.

Existing authorization covers implementation, deployment, scientific tests and
available project capacity. Preserve existing customer quotas and key limits.
Use task-owned disposable test identities with representative policies. Deliberate
worker termination or simulated preemption belongs on test-owned resources; do
not disrupt shared customer workloads. Identify external capacity, credential,
license or artifact blockers precisely when observed.

## Campaign structure

### 1. Inventory and prerequisites

- Resolve exact deployed backend, model, workbench and helper identities,
  settings, GPU pools and available capacity through read-only inspection.
- Enumerate every authorized App and advertised mode from the live catalog and
  schemas. The previous count of 32 Apps is a discovery seed, not current truth.
- Map each App/mode to inputs, terminal artifacts, scientific evaluator,
  lifecycle tests, customer path, evidence and owner. Missing entries stay open.
- Verify test identities, grants, storage bindings and observable attribution.
  A shared workbench backend key is not ten distinct customers. Prove the actual
  per-session identity or use explicitly separate test client instances.
- Reuse and extend existing acceptance runners. Add durable campaign manifests,
  operation-level resume and counters for submitted, admitted, completed, failed,
  cancelled, rejected and skipped work before starting volume runs.
- Research public primary datasets and papers. Freeze URLs, versions, access and
  license requirements, checksums, input preparation, selected samples and metrics
  before model execution. Record unavailable datasets instead of substituting an
  easier fixture and retaining the original reproduction claim.

### 2. Scientist studies

Each persona completes multiple sessions: formulate a question, locate public
data, import it, prepare inputs, compare models or settings, inspect outputs,
revise the experiment, export a report, disconnect and resume. Include natural
language requests from novice and experienced users. Use the real seeded agent,
installed skills, browser, Workspace and Runs. Record prompts and tool choices
without feeding the agent a pre-scripted sequence of successful calls.

| Persona | Study scope | Scientific evidence required |
| --- | --- | --- |
| Structural bioinformatician | Matched public protein set across supported folding Apps, including OpenFold2, ESMFold2 and ESMFold2-Fast | Common preprocessing, appropriate MSA/template treatment, reference alignment, TM-score/RMSD and coverage; confidence reported separately |
| Complex-structure researcher | Boltz2, Protenix v2, OpenFold3 and AlphaFold3 where the deployed contract and access support the selected public complexes | Chain/entity mapping, ligand handling where applicable, reference complex metrics, seeds, exact model/version |
| Protein-design researcher | Proteina-Complexa and BoltzGen study modes supported by their deployed APIs | Requested constraints checked in artifacts; design diversity and downstream structural evaluation |
| Binder-design researcher | mosaic, BindCraft and RFdiffusion workflows, with ProteinMPNN/refolding where available | Multi-stage artifact provenance, sequence/backbone consistency, ranking and computational validation; no experimental efficacy claim |
| Computational chemist | DiffDock and supported molecular generation Apps over public receptor/ligand cases | Input preparation, reference-pose RMSD/top-N metrics where applicable, validity and failure categories |
| Genomicist | Evo2 supported analysis on published public sequence data | Exact operation required by the study; scoring/log-likelihood access checked; generation alone does not reproduce variant-effect analysis |
| Aging researcher | AltumAge and PhenoAge over eligible public cohorts | Feature mapping, units, missingness, independent formula/implementation comparison, age-error metrics where supported |
| Medical-NLP researcher | English/German speech and transcript-to-report studies with available human reference material | WER, terminology and negation fidelity, evidence-linked report checks, omissions and unsupported statements; absent German ground truth stays explicit |
| Conversation-evaluation researcher | MindEval profiles across several clinician models, multiple seeds and full configured turn counts | Patient/judge/config fixed, family-bias handling, judgment completeness, per-criterion scores and paired uncertainty |
| Robotics researcher | Cosmos MP4-to-MP4 and LeRobot-to-LeRobot transformations | Actual model/runtime execution receipt, media readability, requested transformation, action/timestamp preservation and temporal checks |

Reconcile the remaining live Apps and modes into these studies or additional
focused cases. No advertised App silently disappears because it is hard to test.
Use moderate and near-documented-limit inputs as well as ordinary cases.
Unavailable licensed/private models remain explicit blockers for their claims.

### 3. Volume and service behavior

Provisional sizing is 1,500-3,000 top-level model operations across the campaign,
plus internal LLM calls and evaluation work. Derive the final manifest from
datasets, variants, repetitions and measured runtime/cost. Do not pad totals with
polling, discovery, retries, cheap formula rows or artificial duplicate requests.
Report samples per call, unique inputs, logical operations, execution attempts,
internal model calls and HTTP/MCP requests separately.

Exercise normal think time and realistic dependencies, then mixed interactive and
batch traffic, same-model bursts, model switching and overnight usage. Test hot,
scale-from-zero, new-node, snapshot restore and fallback conditions wherever
advertised. Capture the actual path taken; snapshot configuration is insufficient
evidence of a restore. Include long recordings, representative large artifacts,
cancel/resume, browser reload, dropped client connections and interrupted uploads.

Test ordinary invalid scientific inputs, schema-boundary cases, admission
pressure, duplicate submissions and test-owned worker interruption. Preserve the
same idempotency key when recovering the same intended operation. A client
timeout with unknown admission is not permission to submit duplicate GPU work.
Keep interactive progress observable while batch work waits for capacity.

Do not raise existing limits to make tests pass. Record practical maximum load,
queue growth, fairness, throughput, waiting time and recovery under actual policy.
Run tests within provisioned envelopes; additional preemptible capacity is an
implementation option already authorized by the user.

### 4. Independent validation and evidence

For every accepted run, follow the public operation to a terminal outcome and
download, parse and validate the promised artifacts. Use domain metrics and
independent reference implementations where possible. An LLM verdict alone is
not sufficient to establish numerical or scientific correctness.

Keep three separate verdicts: service completed correctly, scientist completed
the workflow without operator repair, and selected published result reproduced
within its predefined tolerance. Set scientific tolerances from the reference
protocol before observing results. Record deviations in data, models and
preprocessing; investigate unexpected discrepancies rather than hiding them.

Correlate tenant, principal, request, operation, attempt, App, model revision,
pod/node/GPU, lifecycle timestamps, artifacts, logs and billed/measured usage in
the actual admin surfaces. Measure queue, provisioning, image/weights/snapshot,
model initialization, inference and artifact publication separately, including
GPU occupied-but-idle time. Preserve unknown values instead of reporting zero.

Report success rates with denominators, first-attempt and eventual success,
retry count, time to result, latency distributions, throughput, GPU utilization,
CPU/memory growth and orphaned work. Use uncertainty appropriate to independent
inputs or studies; repeated calls on one sample are not independent scientific
validation. A global call count never qualifies an under-tested App.

Maintain a defect ledger with the scientist action that exposed the problem,
expected/observed behavior, release identity, reproducible fixture, severity,
fix, regression and final live evidence. Record every operator intervention and
the customer's visible behavior. Retain failed and superseded cohorts.

### 5. Fixes and final qualification

Prioritize execution correctness, missing scientific operations, data handling,
agent tool choice/result interpretation, workflow continuity, queue behavior and
observable usage. Fix in the owning repository, deploy the exact candidate and
retest affected workflows and shared boundaries. Preserve the customer demo and
unrelated work. Do not add unrelated compliance features or redesigns.

Once principal defects are fixed, freeze the integrated release and run two
consecutive clean cohorts across the complete approved coverage matrix. Include
the agreed soak. Intentionally rejected inputs pass only when the expected
error/recovery contract is met. Unexpected terminal failures, silent wrong
results, unexplained warnings, leaked resources and manual repair fail the gate.
If a release changes, evidence for affected behavior must be renewed.

Every requested App/mode must have evidence or an explicitly unresolved blocker.
An unresolved workflow prevents the combined customer-ready verdict. Finish with
a report, machine-readable receipts, reproducible runners, documented remaining
limitations, retained service URLs and cleanup of only task-owned disposable
resources. Testing provides measured evidence for this scope; it cannot prove
that every possible future customer action is free of defects.

## Work allocation

Track bounded work packages under one Task Deck parent: dataset/metric manifest,
structural/design/docking studies, genomics/aging studies, speech/conversation/
robotics studies, customer client and service behavior, and final integration
evidence. Independent dataset preparation and evaluator development can proceed
in parallel. Coordinate shared GPU demand and deployment changes centrally;
independent workers must not overwrite shared model settings or invalidate an
in-progress clean cohort.

## Known starting gaps

- Existing helpers mostly submit one bounded operation; a durable multi-study
  scheduler and study-specific evaluators still need implementation.
- Existing workbench instance uses Rene's key and has a single admitted model
  operation limit. Verify a representative multi-customer identity arrangement.
- Existing evidence records admission retries requiring operator assistance,
  manually attached Runs, missing scientific preparation/evaluation paths, and
  MindEval judge transport errors and high latency.
- Evo2 variant-effect scoring, GPU Cosmos execution evidence, snapshot paths
  and larger-scale scientific metrics were not established by the earlier cohort.
- Dataset availability, all App/mode compatibility and live capacity have not
  yet been verified for this expanded campaign.

## Source anchors

- Workbench: `rene-tech/serverless-ai-cookbook`, existing branch
  `agent/scientific-ai-workbench-v2-20260918`, planning base `fa353181`.
- Known workbench runtime source: `029d8f3`; verify live image and settings before
  reuse. Old operations cannot qualify an updated runtime automatically.
- Backend: resolve current deployment and authoritative worktree in
  `rene-tech/nebius-solutions-library` before edits.
- Earlier evidence: `evidence/20260918-scientist-cohort/README.md` alongside this
  plan; kept unchanged as a record of what was actually exercised.
