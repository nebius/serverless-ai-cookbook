# Retained campaign aggregation

`aggregate_campaign.py` is offline and read-only. It does not call the platform,
submit inference, modify receipts, or alter release/profile settings. Run it from
this directory with Python 3.10+:

```bash
python3 -m unittest test_aggregate_campaign -v
python3 aggregate_campaign.py \
  --root /home/tux/secure-handoff/scientific-qualification-20260918 \
  --output /home/tux/secure-handoff/scientific-qualification-20260918/campaign-reports/deadline-20260919T0604Z \
  --current-runtimes /home/tux/secure-handoff/scientific-qualification-20260918/backend-baseline175/configmaps.json \
  --annotations cases/aggregation-notes-20260919.json \
  --defect-ledger ../../demos/QUALIFICATION_DEFECTS_20260918.md
```

Use a new empty output directory each time. `--as-of` defaults to the invocation
time; an explicit timestamp is supported. Replace the captured baseline with a
newer reviewed ConfigMapList at the final checkpoint. The comparison is against
that **dated capture**, not an assertion that every operation used the latest
image. A caller-supplied `{ "source": {...}, "apps": {model_id: {...}} }` mapping
can provide `runtime_image_digest` and `execution_identity_sha256` instead.

Outputs are private `aggregate.json` and `REPORT.md`. The JSON links every
operation and verdict to original paths and SHA-256 hashes, groups by App and
workflow, and retains all observed failure/reassessment versions. It excludes
request bodies, keys, signed URLs and free-form error details. Source annotation
notes are intentionally human-reviewed; their hashes record the source version
read, not a claim that later mutable documents still have the same hash.

## Counting rules

- Admission `receipt.json` files anchor the population. A UUID is deduplicated
  globally even when downloaded repeatedly into browser workspaces.
- Discovery, artifact upload/finalization, polling, evaluation revisions and
  summaries are not model calls. Synthetic test and isolated-candidate folders
  are excluded from public-admission totals.
- Top-level serving requests, top-level scientific-batch runs, nested child
  inference and children without a start witness are separate. Unconfirmed
  children are not treated as GPU inference; a capability probe may have an
  operation UUID but no GPU execution.
- Service/check totals are split into `top_level_service_states` and
  `child_service_states` (and corresponding independent-check maps). The App
  table uses only the top-level denominator. Legacy `service_states` explicitly
  covers **all durable IDs**, including children: never divide it by the number
  of top-level requests. For the 02:16:50Z interim, 1,733 successes included 12
  children, so the correct top-level success count was 1,721 out of 1,895
  top-level requests, plus 56 receipt-only successes, 111 failures, six ongoing
  states and one cancellation. The 12 children belong to a separate population.
- Scientific stage attempts use their own immutable attempt IDs. They are not
  additional logical model submissions. Retry/stage and design/sample counts
  are distinct from top-level call volume.
- Independent evaluation pass means only the bounded named evaluator passed.
  Service completion, reference accuracy, report correctness and experimental
  efficacy are not interchangeable. Numeric distributions are descriptive
  across the retained inputs, not controlled model comparisons or benchmarks
  generalizable beyond those inputs.
- Old failed checks remain present after offline parser corrections. An
  original failure plus a separate reassessment is marked mixed rather than
  silently choosing the favorable result. The canonical `evaluation.json`
  alone contributes output and metric sample totals, once per operation.
- `generation_exhausted` is explicit finite-search exhaustion, not an unknown
  network fault. Generic `upstream_http_error` stays unknown unless separately
  sourced diagnosis establishes a cause. Historical ESMFold preemption plus
  erroneous nonretryable classification remains two different facts.

## Limits: this is not the final readiness verdict

The receipt-anchored population is a retained-evidence lower bound. It cannot
recover undownloaded browser operations, hidden internal model forwards, every
capacity wait or every manual intervention. Unsupported custom summary formats
and independent media/clinical reports may exist but are not automatically
joined as evaluation verdicts; `not_linked` means **not linked by
this parser**, not that no validation exists anywhere. Detailed client reports,
source hashes and final release qualification remain authoritative separately.

Explicit evidence timestamps are filtered. Timestamp-less records cannot be
retrospectively placed at a historical cutoff; use a fresh capture at the
deadline. Current-image matching is unavailable for many native operations;
unknown identity is never assigned from cohort names, dates or a later success.
The baseline comparison does not prove control-plane/client/snapshot identity.
The report intentionally never emits `ready`.
