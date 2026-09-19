# Release177: bounded admin detail and observer acceptance

This records Q59/Q60 operator checks, not combined customer readiness, a latency
SLO, long-duration leak qualification, or proof of every workload's GPU identity.
Raw responses, Kubernetes snapshots and earlier failures remain in the protected
campaign evidence; no payloads or credentials are included here.

## Exact deployed identity

- Helm revision177: `deployed`; recorded deployment timestamp
  `2026-09-19T02:31:48.610081754Z`.
- Backend source `55fa9d930399d4c0646fdf11644528bf7294042e`, tree
  `605e628fedf21c38cbae143c1b27689ac899440f`.
- Platform control-plane/observer image index
  `sha256:625f221155f24d538efc894debb224fbc8ecda9b12cc26b9c4507322d1fd800c`;
  Linux image manifest
  `sha256:a48d04d11297196ea9e83739fb87431e7f9ae11fcbc776dd1b8ca2e0f57c2356`.
- Existing cluster/service and model configuration retained by the release owner.
  No memory, CPU, concurrency, quota or admin deadline increase.

## Q59: scientific run detail

The original terminal Proteina and BoltzGen reads returned503. Retained failures
include `02:02:07.777Z` (request ID unavailable), and `02:05:47.414097Z` /
`02:05:49.606688Z` (request IDs `92aaeb81-3019-49ad-8c1f-db7996a10bf3` and
`415bb583-5e8c-47c8-80c6-dec25b2c209b`). These were admin reads, not failed model
inference. They are not rewritten as passing.

Source fix `c48a567074cf39acce2480409a52186341b2b4e7` uses the existing latest-rollup
index for only the selected scientific subjects, preserving tie ordering and
missing-rollup semantics. The retained SQL plan measured1235.476ms before versus
0.896ms after over24575 rollups; these are SQL plan times, not public API latency.
The existing service's two-second per-source deadline remains unchanged.

Release177 live readback made six sequential rounds across four retained runs:

- `3ddb929d-52c8-461e-b7e2-da3eedd0c1b0`
- `567c2d79-1757-46e5-b228-f2a7cc95f49b`
- `5d8fdda5-3eb0-4d54-9179-345208829b38`
- `77706ee3-5b96-4f89-8f63-3079db871729`

All24 requests returnedHTTP200 between `02:40:58.674909Z` and
`02:41:33.298705Z`; median0.414967s, maximum1.284191s. Full private response
envelopes were retained. The original helper did not capture response-header
request IDs, and the recorded body IDs were null; no IDs are backfilled.
These are authenticated admin reads of four existing runs, not concurrent-load,
browser, all-run-size or arbitrary-history qualification.

The committed [benchmark helper](../../../scripts/qualification/benchmark_admin_detail.py)
adds offline-tested retention of JSON/non-JSON errors, header request IDs,
transport-error types, malformed200 envelopes and protected evidence files.
It never retries or raises on an HTTP status before saving the receipt, and
refuses to overwrite existing evidence. These changes were made **after** the
live24 reads; no second live benchmark is claimed. The original live helper's
SHA256 was `6f32d3228769cbf8ac231ada0f1386f0bcff772a95be68e39a7709804391dabb`.
Thirteen focused tests pass; the backend fix separately passed37 tests including
actual PostgreSQL16, Ruff and mypy.

## Q60: GPU allocation observer memory

The original observer suffered OOMKilled/exit137 at `02:16:28Z` on a healthy
node, with11 restarts; other observers measured121–122MiB. This was retained as
a process-memory defect, distinct from earlier unavailable-node rollouts.
Source `55fa9d930` separates observer startup from gateway/API/MCP imports;
43 focused tests, Ruff and mypy passed. Actual-image startup peak RSS was37936KiB.

The release177 snapshot has15/15 desired/updated/ready/available observer Pods,
all on the new image, each with zero restarts. Their start times span
`02:33:21Z`–`02:35:10Z`. The snapshot summary file was captured around02:41UTC
(its filesystem timestamp is not a Prometheus sample timestamp).

Resources are unchanged: requests10m CPU/32Mi memory; limits100m CPU/128Mi memory.
The real-node canary, started02:28:22Z, measured RSS50092KiB and high-water
RSS51520KiB; cgroup OOM/kill counters were zero. These are **canary** measurements,
not measured memory for every fleet Pod. Cgroup and process accounting are
different measures and must not be summed.

The release owner retained a final zero-restart snapshot and normally deleted
only the task-owned canary at `02:47:39.978693Z`, without force. No production
observer, model Pod, node or VM was removed for this check. At 02:50:25.457520Z,
the release owner's retained proof shows three fresh GPU workload Pods, created
at 02:47:02–04Z, carrying actual GPU UUID and observer-time annotations while
Running. They span the academic/model namespaces and include BindCraft and
Mosaic. This closes bounded annotation functionality, not all-campaign
attribution, billing, preemption recovery, long soak or automatic cleanup.

## Protected receipt index

Paths are relative to the protected `scientific-qualification-20260918` campaign
root. Hashes bind the original bytes, not newly generated passing summaries.

| Receipt | SHA256 |
| --- | --- |
| `admin-detail-r177-live/summary.json` | `9eca30733b345813470bc416036af5af9071f9913c4a08760669cb4fd1554104` |
| `admin-detail-r177-live/observations.json` | `de7074e60ae221c16923bb746b54b52ce0ac6725c9c8370a4bd915f3d87c49e5` |
| `observer-memory-r177/summary.json` | `433af0ae6d5d6958f9d967353587ba3828c9635cb40d197c2eb12fbd3cb55b26` |
| `observer-memory-r177/canary-cleanup.json` | `2c776049c886a91198fed16356f4eaa587e5901f3e8d45c6f504081f2c4ae2cc` |
| `observer-memory-r177/post-rollout-gpu-attribution-proof.json` | `d2b95c2b26790b46e8e1d20ce356f8fd39b48cb0bd87e1f74aff0426eceb6f11` |

Retained release identity: `observer-admin-release177/after-status.json`,
`backend-baseline177/capture-receipt.json`, and
`control-plane-observer-light-build.json`. Original SQL evidence remains in
`admin-detail-read-diagnosis-20260919/queries.json`. Original OOM, image and
rollout history are not replaced by the new observer snapshots.
