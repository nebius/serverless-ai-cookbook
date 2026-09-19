# Parameter-file preflight after the natural v52 complex-study failure

This is a source-only client correction, not a rerun or a successful four-model
study. The original terminal Study and uploaded artifacts remain unchanged.

## Observed failure

The natural complex study completed two Boltz2 predictions, then failed before
its first Protenix prediction was admitted. Its parameter file contained the
whole scientific-run request envelope. The client nested that envelope under
`parameters`, uploaded source and manifest, and only then validated the complete
request. MCP context teardown wrapped the local validation error in an
`ExceptionGroup`; the Study displayed the wrapper rather than the useful cause.
Caller operation reconciliation found the two successful predictions and two
uploads, but no Protenix prediction admission. This is not a Protenix runtime
failure or evidence that the requested scientific comparison was delivered.

## Correct input and behavior

`--parameters` is a JSON file containing **only** the model parameter object from
the exact discovered submission tool's `input_schema.properties.parameters`.
For example, the retained Protenix contract accepts this parameter-file shape:

```json
{"checkpoint":"protenix-v2","msa_mode":"none","sample_count":1,"model_seeds":[7]}
```

The outer `schema`, `operation`, `service_class`, `input_manifest`, and
`idempotency_key` fields belong to the submission envelope, which the client
constructs. It never silently unwraps or corrects a supplied envelope.

The candidate validates parameters before the first upload, retains the exact
schema/parameter hashes and actionable error, and exposes only that recognized
single-leaf local error through async teardown. Mixed errors, native failures,
transport errors and cancellation remain unchanged. Existing admitted-operation
recovery and idempotency behavior are unchanged; there is no automatic retry.
The documented uploaded-bundle placeholder remains supported: a measured,
validation-only reference checks its shape, and only the actual finalized
reference is used for final full-request validation and submission.

## Evidence and tests

- Original schema SHA-256:
  `e8efad0d038f070ce12a1f01b5cf3c3cf166a2c3a55e88ae0cf35ed2693d6eb5`.
- Original parameter-file SHA-256:
  `e3066fe7e702f7cf59000db665c9f81254ef48fc63646748503fa4c4064051c9`.
- Protected offline candidate replay receipt SHA-256:
  `19f98511de7149dac3181151979287f7ba09758b598280c6359972b67b6b8bc4`.
  It rejects the exact retained envelope and validates its inner object without
  changing live inputs or making network/model calls.
- `test_batch_parameter_preflight.py`, `test_scientific_batch_client.py`, and
  `test_scientific_workflow.py`: **66 passed**. Tests cover wrong envelope,
  required fields/bounds/types, root `$ref` resolution, source binding, no upload
  on rejection, nested async groups, mixed failures and cancellation.
- Ruff uses `--target-version py312`, matching the packaged client interpreter.

Private retained data are under the campaign's `natural-v52/scientist-02`
archive. No transcript, credential or payload archive is published here.
Deployment and a new ordinary-client acceptance remain separate gates.
