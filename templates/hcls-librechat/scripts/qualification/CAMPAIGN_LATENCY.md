# Customer wait and latency from retained evidence

`campaign_latency.py` supplements `aggregate_campaign.py` without making model
calls, querying the platform, or changing any original evidence. Generate a fresh
aggregate first, then use a new output directory:

```bash
python3 -m unittest test_campaign_latency test_aggregate_campaign -v
python3 campaign_latency.py \
  --aggregate /home/tux/secure-handoff/scientific-qualification-20260918/campaign-reports/latency-population-r2/aggregate.json \
  --baseline /home/tux/secure-handoff/scientific-qualification-20260918/backend-baseline176/configmaps.json \
  --diagnoses cases/latency-diagnoses-20260919.json \
  --output /home/tux/secure-handoff/scientific-qualification-20260918/campaign-reports/latency-interim-r2
```

Replace both the aggregate and captured baseline at the deadline. The output
records hashes, the aggregate population cutoff, and the supplement generation
time. Source operation/stage files whose hashes have changed since aggregation
are excluded and reported; later completion must not be backdated. Original
failures and separate reassessments stay in the referenced aggregate.

## What the durations mean

| Span | Meaning and limit |
|---|---|
| accepted → activation started | Operation-worker dispatch wait, when both timestamps exist. Not every downstream capacity wait. |
| activation started → ready | Worker activation path, which can also execute on an already-hot worker. |
| ready → started | Recorded gap before execution. |
| started → completed | Server execution/result wall time, not GPU-active time. For scientific batch this includes stage scheduling, Kueue waits, image pulls and artifacts. |
| accepted → completed | End-to-end server time, including failed terminal requests. |
| receipt elapsed | Customer harness time, including polling and transport; retained separately. |

Only the first four disjoint spans can form a partition. Accepted-to-ready and
accepted-to-started are overlapping composites, never extra summands. Stage
attempt intervals are separately deduplicated and reported as sum, union and
overlap; none are added to parent latency or presented as GPU hours. Negative
durations are invalid rather than clipped to zero. Missing timestamps stay
unknown. Median and nearest-rank p95 always carry their observed sample counts.

The control plane's legacy `cold_start_seconds` is **accepted-to-ready**, including
queue/capacity waiting (`fast_start_policy.py` documents this explicitly).
`activation_started_at` also occurs for warm requests. Neither field proves a
cold start. This report deliberately labels worker-state evidence, not cache
tiers or empty-node cold-start performance.

## Runtime and worker-state provenance

A native operation's explicit runtime digest is authoritative when present.
Otherwise, join its immutable Pod UID to retained observer captures. The captures
must bracket execution start and completion and retain the same actual container
ID, image ID, restart count and container start time throughout that interval.
The directory timestamp and file-write mtime conservatively bound each capture;
undated captures cannot bracket a request. Conflicts, later restarts, absent
captures and ambiguous GPU containers stay unknown. The desired Pod image must
also agree with the actual container image ID; an unverified multi-platform
index-to-manifest relationship or an in-place update in progress is not assumed.
No deployment's newest image is assigned to earlier requests.

`ready_worker_before_acceptance` additionally requires consistent Ready and
container-start timestamps before admission. `new_worker_during_request` requires
creation during the request and readiness before completion. A newly created
Pod may use cached weights or a GPU snapshot; this is not an empty-node benchmark.
Low traffic, fast replies and a zero legacy cold-start value prove neither state.

The exact supplied baseline defines “latest.” Scientific execution identity is
compared separately from image-only native evidence. Neither establishes the
entire control-plane/client/snapshot release. JSON groups each App by operation
kind, service outcome, worker state, diagnosed cause and runtime; runtime × outcome
strata prevent failed fast OOMs being misrepresented as a speedup. Inputs differ,
so these are customer-experience distributions, not controlled A/B estimates.

## Capacity and failures

Explicit reviewed diagnoses are separate annotations with original source hashes.
A preemptible placement alone does not prove preemption. A generic HTTP error is
not assigned to capacity or software without evidence. The retained ESMFold2 node
loss is distinguished from the erroneous nonretryable classification: capacity
loss is not a model defect, but that recovery behavior was a software defect.
Its entire wall time is not apportioned between causes without phase evidence.

The report does not turn successful inference into successful scientific work.
In particular, successful ASR with a downstream source-grounding/report failure,
or a client `localmodel_not_found` error, remains a distinct customer-delivery gap.
Consult the campaign aggregate, defect ledger and exact client evidence together.
No readiness verdict is emitted.
