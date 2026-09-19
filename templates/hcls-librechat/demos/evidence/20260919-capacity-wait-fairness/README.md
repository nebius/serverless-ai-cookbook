# Capacity, waiting and mixed-job progress

Evidence cutoff: **2026-09-19 04:41:18 UTC**. Main window: **02:56:41–04:41:18 UTC**, 105 retained approximately one-minute observer samples. A separate **22:06–22:28 UTC on September 18** incident illustrates capacity-loss handling. This is a bounded retrospective, not a new load test, fairness guarantee, or campaign-wide count/latency report. No inference or infrastructure changes were made for it.

## Result

Shorter requests continued completing while a long BindCraft job occupied one H100. Its earlier 18-minute wait has an explicit placement/quota explanation, not evidence of unexplained starvation. However, aggregate spare GPUs overstate usable capacity; queue-position/ETA and actual GPU busy/idle accounting remain unproven here. The original capacity-loss failure was poorly classified to the customer and is retained as such.

### BindCraft: queue time is not GPU execution time

Operation `b50f5093-f8d9-409d-849f-aae916a56235`, scientist07/lab-b:

| Event | UTC / observation |
|---|---|
| Submitted | 02:56:41.017862 |
| Kueue Pending | First 02:56:42; last repeated observation 03:13:43 |
| Admitted and Pod scheduled | 03:14:43 |
| Scientific container started | 03:14:53 |
| Last retained observation | Same Pod Running, zero restarts, 04:41:18; workflow not terminal |

The event timestamps span **1,081 seconds of queueing**. Kueue's own message reports **1,083 seconds**; the admin lifecycle's estimated closed-interval union is **1,081.32309 seconds**. These are different observation boundaries, not contradictory exact clocks. The controller attempt's `started_at=02:56:41` includes the queue and must not be presented as GPU-start time.

The same Pod UID `fc8db5a5-c708-4a7e-8dc5-e8138752f14f` was observed on `computeinstance-e00m0hsph76ajt9sdb` throughout the running window. At cutoff, **at least 86m25s had elapsed since its scientific container started**, while whole-workflow elapsed time was **104m37s**. This establishes reservation/container lifetime, **not GPU kernel busy time, useful design time, idle time or billable GPU hours**. The admin GPU accounting was explicitly estimated/incomplete, with zero unreconciled counters; those zeros are not utilization measurements.

Evidence: protected `heldout-bindcraft-observation-0404.json` (body generated 04:00:52, despite its filename), `observations/20260919T031552Z/{events,pods}.json`, and `observations/20260919T044118Z/pods.json`. Full hashes are in [the portable evidence index](retained-observations.json).

### Why free 1×H100 capacity could not serve that job

The exact scientific container requests **16 CPUs, 96 GiB RAM, one GPU and 32 GiB ephemeral storage**; the concurrently running artifact collector adds **0.1 CPU and 256 MiB RAM**. Its total regular-container request is therefore **16.1 CPU / 96.25 GiB / one GPU**. Init containers are smaller. The main container limits are 24 CPU / 128 GiB / one GPU; those limits are not the scheduling request.

Every observed 1×H100 node exposes only **15.9 allocatable CPUs** before other Pod reservations, so the unchanged Pod cannot fit even on an otherwise empty one. Approximately 185.62 GiB of allocatable host RAM and one H100 are individually sufficient, but CPU is not. The captured profile lists both `h100-reserved-8x` and `h100-1x`; the actual frozen Pod requires the reserved-8x pool through required affinity plus `storage.fs2.nebius/reference-data=true`. Thus this is not simply missing generic H100 model qualification. L40S nodes additionally have only approximately 57.1 GiB allocatable host RAM and the wrong permitted accelerator class.

Kueue explicitly reported the other flavors failing affinity and **one more GPU needed in the reserved-8x flavor**. At 02:57:52 both reserved nodes had all **16 GPUs reserved**, while three preemptible H100 and three L40S resource units were unreserved elsewhere. No quota or placement was changed for this analysis.

A future 1×H100 optimization needs a **new measured CPU resource envelope** that fits actual allocatable CPU after required system/sidecar reservations, or a larger host preset. It also needs end-to-end runtime, output, performance, academic-assets/reference mounts and scheduler qualification for that exact envelope. Simply removing affinity cannot make 16.1 CPUs fit 15.9; reducing a request without measurement is not evidence that the runtime remains usable.

### Overlapping completion witnesses

These selected successful receipts all fall inside the long BindCraft container's observed running interval. They are **examples, not global totals**, and the scientist labels are API principals, not claims that these were natural LibreChat journeys.

| App / principal | Operation | Client start → finished UTC | Client wall time |
|---|---|---|---:|
| Proteina-Complexa / 02, lab-a | `9bd8fefa-bf44-4578-9ec3-f2338b4b6619` | 03:34:30 → 03:41:41 | 431.3 s |
| Mosaic / 01, lab-a | `b2260b5b-a189-4a89-9963-c939b8ff0e94` | 03:45:11 → 03:48:19 | 187.2 s |
| DiffDock / 06, lab-b | `2b22c485-de02-4d81-ad29-d0e8cb59305a` | 03:59:59 → 04:00:34 | 35.5 s |
| ESMFold2-Fast / 01, lab-a | `13f20947-2e83-48b5-ac2f-dca1cfcf3b72` | 04:20:50 → 04:23:00 | 130.1 s |

These receipts distinguish durable API admission from later scheduler admission. Their wall times include client/upload/poll/result handling where applicable and are not GPU compute durations. They support **continued mixed-App progress across two tenants**, not an adversarial fairness, maximum-wait, priority-preemption or noisy-neighbor guarantee. `BestEffortFIFO` was observed; no quantitative tenant fair-share guarantee was tested.

## Capacity and queue visibility

Across the 105 main-window samples, schedulable GPU resource units ranged **28–29**, assigned nonterminal-Pod reservations **19–26**, and their residual **3–10** (median seven). Pending GPU Pods appeared in **43/105 samples**, at most three at a time. All 105 sampled `/readyz` responses were HTTP 200; this does not establish uninterrupted availability between samples or success of every App/admin query.

| At cutoff 04:41:18 | Ready GPU units | Pod-reserved | Unreserved resource units |
|---|---:|---:|---:|
| Two reserved 8×H100 nodes | 16 | 15 | 1 |
| Preemptible 1×H100 nodes | 4 | 0 | 4 |
| Regular 1×H100 | 1 | 0 | 1 |
| Regular 1×L40S nodes | 8 | 5 | 3 |
| Total | 29 | 20 | 9 |

This is **scheduler-reservation headroom, not GPU utilization, hot-model standby or guaranteed placement capacity**. CPU/RAM fit, placement rules, image/cache state, reference assets, model qualification and Kueue reservation can all restrict it. Kueue quota is also not cloud supply: for example its L40S flavor's nominal quota was 16 while only eight ready L40S GPUs were observed.

At 02:57:52 the admin capacity capture correctly showed **two pending Kueue workloads even though there were zero Pending GPU Pods**: suspended jobs had not yet created Pods. At 03:15:52 Kueue pending was zero and BindCraft was admitted; at cutoff it was again zero. Queue state/reasons were therefore observable and this queued job did receive capacity. The run's numeric queue position remained null/unavailable, so no customer ETA or precise place-in-line is established. The note does not assert that every queued request in the entire campaign finished.

## Capacity loss versus software failure

The retained 22:11 incident includes two preemptible H100 instances observed `STOPPED` by the provider at 22:16, plus node-not-ready events. The provider responses show a STOP-on-preemption policy but **do not contain a stop-cause event**; they prove loss of preemptible capacity, not its precise administrative/provider cause.

ESMFold2 operation `405cc84b-9a5e-4311-b8d3-8275f7a21c7f` triggered ordinary scale-up **4→5 within the unchanged maximum 16**, was scheduled to a different preemptible node (`computeinstance-e00srhk44n11yvn2n9`), encountered an image-pull EOF/containerd-unavailable failure, then node-not-ready and a taint-manager Pod eviction. Its original public result was generic **`WORKLOAD_FAILED`, retryable=false** after about 22 minutes. That is an actionable customer-facing classification/recovery gap, not evidence that the scientific model rejected the input. The exact provider cause for that third node is not in this retained subset.

The separate repaired replay `eff0b12a-d92f-4f7e-bbab-b0ad9148f735` later succeeded in **106.6 seconds**. It preserves the original failed verdict; it **does not prove automatic recovery of the original request or recovery under a second real node loss**. Kubernetes scheduling messages saying “preemption is not helpful” mean scheduler victim selection, not a cloud preemption event; they were not counted as provider preemptions.

## Remaining qualification limits

- One-minute node/Pod/API captures are not atomic; very short waits, restarts and availability gaps can be missed. Reservations count regular containers of assigned nonterminal Pods, not all effective init-container/overhead requirements or MIG accounting.
- The unfinished BindCraft run was executing, not stuck in the queue. Its eventual success/quality was still unknown at this cutoff. No unexplained starvation is established for the selected witnesses; absence of starvation across every workload is not proven.
- GPU busy/idle/weight-loading/cooldown occupation needs complete device/activity attribution and reconciled phase intervals. Do not derive it from reservation totals or label all container lifetime active computation.
- The campaign included manual debugging, runtime promotions, isolated candidates and resource-policy-preserving replica changes. It is not an untouched steady-state benchmark or evidence that capacity incidents recovered without intervention.
- Broader customer conclusions remain in the separate [all-App coverage overlay](../20260919-campaign-coverage/README.md) and [natural persona assessment](../20260919-persona-customer-experience/README.md).

## Reproduction

The read-only helper hashes every source it uses, preserves event timing discrepancies, and emits selected evidence only:

```bash
python3 templates/hcls-librechat/scripts/qualification/capacity_evidence.py \
  --root /home/tux/secure-handoff/scientific-qualification-20260918
```

It reads the fixed cutoff, not live APIs. [retained-observations.json](retained-observations.json) contains the 126 relative source paths, SHA-256 digests, selected events, per-pool reservations and four completion witnesses. Protected raw captures stay out of Git; no credentials or request payloads are copied into this report. Unit tests cover missing/negative measurements, unready/completed exclusions, queue timing and the non-utilization/non-placement interpretation.
