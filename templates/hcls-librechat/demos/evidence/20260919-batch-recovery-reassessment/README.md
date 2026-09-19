# Retained node-loss recovery reassessment

As of 2026-09-19 05:27 UTC. This is a bounded offline reassessment of an existing repair, not another live fault test or a new backend change.

## Three separate conclusions

| Evidence | Result and boundary |
|---|---|
| Original customer incident | ESMFold2 operation `405cc84b-9a5e-4311-b8d3-8275f7a21c7f` ended `WORKLOAD_FAILED`, retryable=false after image-pull/containerd failures, NodeNotReady and a true `DisruptionTarget/DeletionByTaintManager` condition. No scientific application exit was recorded. The original failed verdict remains unchanged; the precise provider stop cause is unknown. |
| Existing deployed repair | Source `b60bdf3f5` is included in deployed release182 source `8e747def5`. Replaying the exact retained Pod status changes the historical application classification to retryable infrastructure/`DeletionByTaintManager`. Current observer/controller regressions pass with the existing attempt cap and idempotency. No additional source fix is warranted by this evidence. |
| Live automatic recovery | **Not qualified.** The separate public operation `eff0b12a-d92f-4f7e-bbab-b0ad9148f735` completed and was verified in 106.6 seconds, but a fresh manual submission is not automatic recovery of the original operation. |

The [capacity note](../20260919-capacity-wait-fairness/README.md) preserves the original timeline and its historical cutoff. Release182 Apps/UI/installed-image evidence is [separate](../20260919-admin-apps-reliability/README.md). Its exact OCI index is `sha256:f3a3d6c2d4e28b6f8693e6cc65c6d9b63ecd4e54e8e13d170059f4e85d0a60f6`.

## Replay method and result

The original full Job and Kueue objects were not retained. The private test therefore uses the **exact captured Pod status with explicitly synthetic Job, Kueue, metadata and fencing shells**, not an end-to-end replay of the original Job. Historical classifier functions are extracted from the parent of `b60bdf3f5`; the current classifier, HTTP observer and controller are exercised without changing production code.

The controller test creates a second distinct attempt for the same logical operation after the first infrastructure failure. A second failure terminates at the unchanged default `max_attempts=2`; further reconciles create no third workload. Existing negative cases retain nonretryable application exits, OOM and execution timeouts, and do not infer disruption from generic, false or unknown conditions.

**120 tests passed in 9.87 seconds:** three retained-Pod/synthetic-shell tests plus 117 existing observer/controller/production tests. The first private harness run omitted the required `phases` argument (119 passed, one failed); correcting that test fixture produced the reported pass. This was not a runtime defect. A Starlette deprecation warning and cleanup warnings for pre-existing temporary PostgreSQL socket directories were retained; no cleanup or environment changes were made.

Reproduction from the backend control-plane directory, with `Q` set to the protected campaign evidence root:

```bash
PYTHONPATH=tests .venv/bin/pytest -q -c pyproject.toml \
  "$Q/esmfold-preemption-diagnosis/current-replay/test_retained_disruption.py" \
  tests/test_scientific_node_disruption.py \
  tests/test_scientific_batch_controller.py \
  tests/test_scientific_batch_production.py
```

Protected evidence references (SHA-256; raw captures remain private):

The replay receipt is `esmfold-preemption-diagnosis/current-replay/result.json`, SHA-256 `f0d0a3b393853963ff140ae41b877bebe6cebcac42dea368868c42ca07f13df6`.

| Relative campaign path | SHA-256 |
|---|---|
| `observations/20260918T221631Z/pods.json` | `49053f4e570fa34b2ca657be70756c08c38d8987b11321f3dd8fe3bce40a3d9b` |
| `observations/20260918T221631Z/events.json` | `34bd38d9f1d18e0d55e44820244a59127aa88fc2821d616693b29be899b85645` |
| `esmfold-preemption-diagnosis/public-result.json` | `c7e6fd3283121521fbe7e4f923f842ee7bd9f0ae04001cffd6e59b6d18b9aad0` |
| `esmfold-preemption-diagnosis/current-replay/test_retained_disruption.py` | `ea43196a574756497ff059df9ebc031eabe9798f573867506fde4c40d48a09a4` |
| `cohorts/esmfold-preemption-repaired-r1/scientist-01/esmfold2-1tim-pdb70-depth64/receipt.json` | `7a2a6fa7adfc8a7a2283604dd5bfea76aa61a25e761523fae033e9a6be1324f8` |

## Remaining scoped acceptance

Reuse task `fs2-preemptible-batch-recovery-r20260918`. A future separately authorized noncustomer test should retain one logical operation/idempotency key, capture the actual disruption and first-attempt resource release, observe a distinct second attempt without duplicate admission, and validate its terminal artifacts and accounting. Preserve existing attempts, timeouts, placement and resource limits. If capacity remains unavailable, verify bounded failure rather than inventing a provider cause or silently extending retries. Shared workload/node disruption requires explicit approval; none was performed here. This pending acceptance does not require another source change merely to keep the task active.
