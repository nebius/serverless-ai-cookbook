# Held-out design cohort completed

The existing `design-heldout-r177` cohort finished its last result at
**2026-09-19 05:16:50 UTC: 13/13 service/artifact checks passed**. Four existing
scientist identities submitted the frozen cases under unchanged one-active-
operation limits. This is an API cohort, not thirteen natural LibreChat journeys,
independent biological replicates, or a new run on the final control-plane release.
Original operation identities were resumed, never resubmitted when observation
windows expired. GPU capacity and scientific filters were not increased/relaxed.

| Frozen case | Operation ID | Client end-to-end seconds |
| --- | --- | ---: |
| BindCraft PD-L1, seed42, soluble | `ecacd870-407b-4754-8247-988634a4726c` | 1438.075 |
| BindCraft PD-L1, seed42, vanilla | `b50f5093-f8d9-409d-849f-aae916a56235` | 8416.080 |
| BindCraft PD-L1, seed7, soluble | `97e31d15-e11d-4e66-a695-da5d7784c8af` | 1319.502 |
| BindCraft PD-L1, seed7, vanilla | `e145aef0-b18d-4332-866c-83be1e632093` | 2881.993 |
| Mosaic ubiquitin, seed42, length40 | `b9372214-0d1d-4360-ba07-dc62da9dd649` | 334.013 |
| Mosaic ubiquitin, seed42, length64 | `50c1b4c9-9d4c-4683-8942-803e2bea72ec` | 181.354 |
| Mosaic ubiquitin, seed42, length80 | `b2260b5b-a189-4a89-9963-c939b8ff0e94` | 187.204 |
| Mosaic ubiquitin, seed7, length40 | `23023035-16a6-4acb-8dda-2425fcb05f4f` | 366.396 |
| Mosaic ubiquitin, seed7, length80 | `3fddf2dd-6a96-4d43-84a2-04e718e10901` | 273.379 |
| RFdiffusion unconditional, seed42, length128 | `6b0f3071-42f7-4fb0-b7f6-f04346b9fc9f` | 239.860 |
| RFdiffusion unconditional, seed42, length256 | `e8e8448c-d1f3-429f-93c4-44fb77174752` | 133.966 |
| RFdiffusion unconditional, seed7, length128 | `4d9bcd06-1180-4132-8bf8-f785ac70dff7` | 234.423 |
| RFdiffusion unconditional, seed7, length256 | `09779f1c-4fea-48e7-a3c3-c3c18aac2e1e` | 135.598 |

These times include queueing, initialization, execution and client result handling.
They are not GPU compute, cold-start measurements, or a cross-model speed ranking:
the requests and search protocols differ materially.

## The long BindCraft request

Accepted at02:56:41.017862, it waited approximately18 minutes for eligible
capacity, started its scientific container at03:14:53 and completed the service
operation at05:16:36.265983. Verification finished14.3 seconds later. Earlier
same-request observations are preserved; it was not replaced by an easier input.
Logs showed continuing native trajectory search/filter rejection rather than a
queue stall. The [capacity report](../20260919-capacity-wait-fairness/README.md)
retains its earlier unfinished cutoff and the exact CPU/placement restriction;
this note supplies the later terminal result.

The final evaluator found a67-residue binder and the corresponding115-residue
target/67-residue binder complex, not two independent designs. The binder chain
has finite coordinates, correct requested length, adjacent C-alpha distances
3.728–3.967 Å, and no nonlocal C-alpha pairs below2 Å. Its complex has26 C-alpha
contact pairs below8 Å and minimum interchain C-alpha distance4.570 Å. Those are
geometry checks, **not binding affinity, an all-atom clash score or experimental
efficacy**. Native filter acceptance is not independent scientific validation.
The separate [220-refold study](../20260919-design-refolding/README.md) has its
own inputs, denominators and retained poor results; do not add artifacts here as
extra refolding calls.

## Retained evidence and reproduction

Under protected campaign root
`/home/tux/secure-handoff/scientific-qualification-20260918`, the cohort directory
`cohorts/design-heldout-r177` contains frozen assignments, requests, manifests,
result bytes, semantic evaluations, operation histories and receipts. Secrets
and signed artifact URLs remain private.

| File relative to cohort | SHA256 |
| --- | --- |
| `campaign.json` | `70d1231c9000ed0e1ca06aee877eeacb6e8acacf13f47c2526eee9fc43723a0b` |
| `assignments.json` | `6a10e40d904450c44932a70873f9b6d525d7b493d4bcf01b36f62b8a77c8b2d4` |
| `summary.json` | `6d875bfc23a64dcb4cf2090853ed99fee5eaa0ad00a16965b7c7f5db3cbe3626` |
| `scientist-07/bindcraft-pdl1-s42-vanilla/receipt.json` | `c5da5ad2c163f955eff68ce8a146070b45789196626846bb14edc104d3aba0e3` |
| `scientist-07/bindcraft-pdl1-s42-vanilla/evaluation.json` | `f6f917952a1b3ac6c16b07ee07238755b979f159a7d2f87408b1e7550125bd2d` |
| `scientist-07/bindcraft-pdl1-s42-vanilla/result-envelope.json` | `f5cddd43a757b5cd0e892eca13cbc7c67c7cca6c425bc109bfba5e647a1bcf02` |

Read-only reconstruction of the table:

```bash
jq -s 'map({case_id,model_id,operation_id,state,elapsed_seconds,service_semantic_pass,finished_at})|sort_by(.case_id)' \
  /home/tux/secure-handoff/scientific-qualification-20260918/cohorts/design-heldout-r177/scientist-*/*/receipt.json
```
