# Batch compression binding and visible preflight errors

The original private v60 scientist03 study
`5cc904cb-341b-5c4b-91c6-93bc67afb35f` remains **failed**. Proteina completed;
the following BoltzGen step never reached inference admission. No retained plan,
input, report or operation was repaired, retried or relabelled.

## Exact cause

The retained `bg-batch` plan omitted `compression`. The existing workflow adapter
filled `none`, while the saved BoltzGen `input_artifact_contract` permitted only
`gzip`. Its original 143,393-byte input is gzip, SHA256
`39f4eac886f1e311f12a8a0b5ad275bafc3840d4ee945a4d8be0661d9f0c809b`.
The batch helper had saved tool/discovery metadata, but not the request descriptor,
source artifact, manifest artifact or operation ID.

An independent network-disabled replay of the **installed v60** pure preflight
using those unchanged bytes/plan/parameters/discovery returned the exact
`ValueError`: compression must be one of `['gzip']`, received `'none'`.
The SDK's TaskGroup hid this plain exception behind the generic group message;
the old helper unwrapped only its typed parameter-file exception. This is a local
transport-metadata contract error, not evidence of a model or network failure.

Protected replay receipt: `v61-build-preparation/diagnosis03.json`, SHA256
`6cbb7f349f58f672d8dc6e1d31152562e8815adef5cf52a221edb2e17771acce`.
It records exact input/plan/contract hashes, installed helper hash, zero upload/
inference calls and unchanged retained bytes.

## Bounded source change

- Preserve omitted compression through the workflow/CLI boundary instead of
  immediately inventing `none`.
- Bind omitted gzip/zstd only when the **selected published input role** permits
  exactly that one encoding and the actual source magic agrees. Do not derive
  from an extension, model name or media type alone. Plain inputs retain the
  existing `none` behavior; an incompatible published role still rejects them.
- Preserve every explicit compression choice. An explicit wrong `none` remains
  wrong; it is never silently corrected. Ambiguous or unmatched compressed input
  requires an explicit choice and is rejected before upload.
- No source decoding/recompression, scientific-input changes, model defaults,
  queue/resource policy, retries or limits are introduced. A matching signature
  is transport evidence, not proof of archive integrity or scientific validity.
- Save the selected transport encoding, selection reason, exact source SHA/size
  and input-contract hash before upload. Preserve source bytes and immutable plan.
- Use `SourcePreflightError` for this local rejection, saving its diagnostic
  receipt. Unwrap only that exact single typed leaf through nested TaskGroups,
  as with `ParameterPreflightError`. Mixed groups, unrelated `ValueError`,
  transport errors, cancellation and genuine workload failures remain unchanged.

## Tests and remaining gate

`test_batch_source_preflight.py` adds 23 cases: sole gzip/zstd binding, plain-input
compatibility, explicit choices, ambiguity, wrong signatures, selected role,
actual AnyIO TaskGroup teardown, zero-upload rejection, pre-upload provenance,
unchanged mixed groups, omission through the workflow, and exact retained03
read-only replay. New23 plus existing66 = **89 passed, zero skips**; Ruff and
diff checks pass. No provider/model transport is exercised.

The first 89-pass local run retained unrelated pre-existing pytest temporary
directory cleanup warnings. A fresh dedicated basetemp rerun passes cleanly;
both receipts remain protected under `v61-build-preparation/`.
Clean `batch-source-tests-r2.xml` SHA256:
`55d35d0f318fc6ccbd9b6785fd044c5298ba4f4d64d4f36baf9e1a2b5a47bb33`.
Clean `batch-source-tests-r2.log` SHA256:
`f04dc1b9a2fcba982ea7cfdc88de9c4f08a0a38f8bbfdf9eceeff4677f70d691`.

The installed successor gate must import the image's existing workflow/batch
modules, not mount candidate runtime files. Set these read-only fixture bindings
for all23 cases, with no skipped replay:

- `SCIENTIFIC_RETAINED_V60_03_SNAPSHOT`: exact retained scientist03 S3 snapshot
  `independent-v60-private/scientist-03-s3-20260919T235012504788Z`.
- `SCIENTIFIC_RETAINED_V60_03_SOURCE`: original `campaign-input.input` under
  `acceptance-input-preflight/scientist-03/supplement-r2/objects/scientist-03/study-inputs/design-inputs/boltzgen/`.

Source/runtime hashes for `scientific-workflow.py`, `invoke-scientific-batch.py`
and `scientific_study_schema.py` must match the final image. Build, installed
successor execution and natural customer-path qualification remain pending.
