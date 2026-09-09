---
name: parabricks-serverless
description: Run and inspect bounded NVIDIA Parabricks DeepVariant workflows through the Nebius Serverless REST and MCP endpoint. Use for capability discovery, public or mounted genomic inputs, run monitoring, VCF artifacts, and provenance-aware research reporting.
license: Apache-2.0
---

# Parabricks DeepVariant on Nebius Serverless

Use the configured Parabricks MCP server whose Streamable HTTP URL ends in
`/mcp`. The MCP client supplies the endpoint bearer token. Never request, print,
copy, or put that token or an NGC key in tool arguments or this skill.

Call `get_capabilities` before submission and after a reconnect, version change,
or validation error. Its live schema, public example, limits, runtime identity,
and GPU count win over this skill.

## Prepare inputs

Prefer finalized caller-owned files mounted below
`/mnt/hcls/parabricks-deepvariant/fixtures`. Never invent genomic records,
reference assemblies, indexes, sample identifiers, intervals, or checksums.
Confirm that reference/index and reads/index pairs match and that intervals use
the reference's contig naming.

Public HTTPS inputs require an explicit filename and exact SHA-256. Do not copy
signed URLs, access credentials, patient data, or private genomic content into
chat. Use the included chr20 example only for infrastructure acceptance; it is
not a production validation dataset.

## Submit and monitor

1. Select the exact live example or construct a request from verified mounted
   or public inputs within the advertised limits.
2. Set `research_use_acknowledgement: true` only for a user-approved research run.
3. Submit once with a stable `client_request_id`; reuse it only after an
   uncertain transport failure with identical input.
4. Save `run_id` and poll `get_run`. Treat `queued` and `running` as progress.
   Terminal states are `succeeded`, `failed`, and `cancelled`.
5. After success, call `list_run_artifacts`. Download paths are authenticated
   REST paths on the same host and use the same endpoint token.

The endpoint executes one run at a time. On 429, inspect and wait for existing
runs. `cancel_run` cancels queued work only; do not repeatedly cancel a running
Parabricks process.

## Validate and report

Check that the expected compressed VCF and index are nonempty, retain the input
hashes, and verify downloaded artifact SHA-256 values. Report run ID, terminal
state, sample, reference, mode, intervals, Parabricks version, NVIDIA runtime
tag/digest, GPU count/type, wall time, variant-record count, output paths, and
hashes. A successful process or nonempty VCF does not establish clinical or
scientific validity. Describe outputs as research variant calls requiring
independent validation, never as diagnoses.

Artifacts persist under `/mnt/hcls/parabricks-deepvariant/runs/<run-id>` only
when Object Storage or Shared Filesystem is mounted at `/mnt/hcls`.
