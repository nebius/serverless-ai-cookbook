# HCLS API v1 contract

The HCLS endpoint templates share a small asynchronous HTTP contract while keeping
engine-specific scientific inputs and scores separate.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/healthz` | Engine, accelerator, and storage readiness |
| `GET` | `/v1/capabilities` | Workload identity, limits, examples, and result semantics |
| `POST` | `/v1/runs` | Submit a bounded run; returns HTTP 202 |
| `GET` | `/v1/runs/{run_id}` | Poll queued, running, succeeded, failed, or cancelled state |
| `POST` | `/v1/runs/{run_id}/cancel` | Cancel only work that has not started |
| `GET` | `/v1/runs/{run_id}/artifacts/{name}` | Download an artifact from its manifest path |
| `POST` | `/mcp` | MCP Streamable HTTP transport backed by the same run manager |

Submission envelope:

```json
{
  "input": {},
  "client_request_id": "my-idempotency-key",
  "research_use_acknowledgement": true
}
```

The runtime uses one engine worker and a bounded queue (eight by default), hashes
every downloadable artifact, rejects path traversal, and restores completed run
records from the configured run volume. A non-terminal record restored after a
worker restart becomes a failed `InterruptedRun`; it is never silently reported as
successful.

Nebius endpoint authentication belongs at the managed HTTPS edge. Send its token as
`Authorization: Bearer …`. The token is not part of an input payload, URL, image, or
artifact. The same token protects REST and MCP; the MCP tools are
`get_capabilities`, `submit_run`, `get_run`, and `list_run_artifacts`. A run submitted
through either interface is visible through both. All templates are research-only
and reject submission without an explicit acknowledgement.

Run the common tests from the repository root:

```bash
PYTHONPATH=templates/hcls-common pytest -q templates/hcls-common/tests
```

The reusable smoke client checks negative authentication, REST execution, MCP
execution, cross-interface run visibility, and artifact hashes:

```bash
python3 -m venv .venv-hcls-client
.venv-hcls-client/bin/pip install -r templates/hcls-common/requirements-client.txt
export HCLS_ENDPOINT_TOKEN='<Serverless token>'
.venv-hcls-client/bin/python templates/hcls-common/scripts/test_endpoint.py \
  'https://<managed-endpoint>' --payload '<engine-specific JSON object>'
```
