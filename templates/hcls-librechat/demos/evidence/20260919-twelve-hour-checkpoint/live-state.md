# Final bounded live-state capture

Observed **2026-09-19 05:38:14–05:38:49 UTC**, using one read-only capture against the authorized Stockholm backend. These sequential Kubernetes, Helm and HTTP reads are not atomic or a continuous-health guarantee. No inference, cleanup, settings change, fault injection or resource increase was performed.

## Backend and operator surfaces

- **Helm182: deployed.** All three gateways and both model controllers were Ready/Available, with zero container restarts and the exact release index `sha256:f3a3d6c2d4e28b6f8693e6cc65c6d9b63ecd4e54e8e13d170059f4e85d0a60f6` (source `8e747def5`). Prior regression/live-install evidence is [separate](../20260919-admin-apps-reliability/README.md).
- **GPU observers: 15/15 Ready/Available.** Their separately pinned image remains `sha256:625f221155f24d538efc894debb224fbc8ecda9b12cc26b9c4507322d1fd800c`, not the gateway image. One observer has one historical restart: exit255/reason `Unknown` at04:28:07, running again04:28:30 and Ready at capture. This is **not** a zero-restart/long-soak claim or evidence of OOM/provider preemption.
- Public `/readyz`: **HTTP200, 0.342s**. Admin Apps: **HTTP200, 2.782s, 35 entries**. Admin Capacity: **HTTP200, 0.485s**. No request IDs were returned in these three response headers.
- The 21 ModelDeployments report **17 Ready / four Cold**. Apps project 17 Ready, four Cold, 11 scientific dispatch `open`, one `paused`, one `available` and one `unavailable`. Cold is not a failed inference. The unavailable GLM entry reports no managed ModelDeployment; the available MSA entry also has no managed ModelDeployment. The paused independent acceptance App retains its operator pause. These are inventory states, not fresh model qualification.

## GPU scheduler units

The existing observer arithmetic counts regular-container GPU requests of assigned, nonterminal Pods on Ready, schedulable nodes, excluding shutdown/unreachable/not-ready taints. It does **not** measure kernel busy time, idle time, billable time, full init-container/overhead arithmetic, CPU/RAM fit or model-specific placement eligibility.

| Pool | Observed nodes | Allocatable GPU units | Pod-reserved | Unreserved units |
|---|---:|---:|---:|---:|
| `h100-1x` | 4 | 4 | 0 | 4 |
| `h100-ondemand-1x` | 1 | 1 | 0 | 1 |
| `h100-reserved-8x` | 2 | 16 | 14 | 2 |
| `l40s-1x` | 8 | 8 | 5 | 3 |
| **Total** | **15** | **29** | **19** | **10** |

All 18 GPU-requesting nonterminal Pods were Running/Ready; one requests two GPUs. Two one-GPU L40S Pods were created September16 and explicitly carry task label `fs2-mindguard-r20260916`. That is evidence of a distinct earlier task, not authority to delete them. The other serving Pods are shared model resources; their reservations cannot be assigned to this campaign or counted as active inference from this snapshot.

Kueue's inference queue separately reported 16 admitted workloads and 17 reserved GPU units (14 H100 plus three L40S). Its smaller reservation total excludes the two earlier-task L40S Pods. Neither Kueue quota nor the ten unreserved physical resource units promises immediate placement of a particular workload; see the [capacity/wait evidence](../20260919-capacity-wait-fairness/README.md).

## Waiting work and explicit exceptions

- No Pending GPU Pod or active scientific Job was captured. All three displayed ClusterQueues reported zero pending. The 11 open scientific App rows each reported zero running/queued; the separately paused App does not publish that count in its status reason. This is not a campaign-wide durable-operation or conversation-completion query.
- The retained Kueue inventory includes two September3 reference-data workload objects with old `Evicted/PodsReadyTimeout` conditions alongside historical admission fields. They are not presented as newly running campaign jobs. One August31 infrastructure prune Job also lacks a terminal condition despite `failed=1`; it is not a current scientific inference.
- One non-GPU Cilium operator Pod is Pending with a September4 scheduling condition (host-port/taint constraints). The separate `fs2-mindeval-workshop` deployment has two September16 Running but not-Ready Pods (0/2 available); its gateway is a different deployment. No cause or current customer impact is inferred, and no remediation was attempted in this inventory.

These exceptions and the observer restart remain visible; healthy gateway probes do not establish whole-cluster health. Historical failed requests, rollback, scientific/clinical validity and incomplete natural-client delivery are not superseded by this snapshot.

## Evidence

Protected campaign-relative directory: `final-live-state-20260919/`. `final-summary.json` has SHA-256 **`e9b49f34488f07db25f9d565d24997ef2501d4d925770d6b9bce859aa4fdbae9`** and binds the timestamped Helm status, deployments, DaemonSet, nodes, Pods, Jobs, ModelDeployments, Kueue objects, Apps, Capacity and readiness receipts by hash. Raw credentials, host IDs and tenant records remain private.

The capture reuses `manage_campaign` authentication/read helpers, `observe_campaign.gpu_capacity` and `capacity_evidence.per_pool_reservations`. An offline summary corrects an initial short controller-name selector against the already retained deployment/Pod data; no additional live read was made. This is the final single inventory, not a new monitoring loop.
