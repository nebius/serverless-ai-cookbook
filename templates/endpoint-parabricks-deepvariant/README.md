# NVIDIA Parabricks DeepVariant REST + MCP

<!-- markdownlint-disable MD013 MD033 -->

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fhcls%2Fparabricks-deepvariant-api%3A20260908-dynamic-v3&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=false&amp;auth=true&amp;env=NGC_API_KEY&amp;env=PARABRICKS_VERSION%3Dlatest&amp;env=PARABRICKS_GPU_COUNT%3D1&amp;volumeMountPath=%2Fmnt%2Fhcls&amp;volumeSize=32"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Run bounded NVIDIA Parabricks DeepVariant workflows through REST or MCP. A lean API image pulls the selected official Parabricks runtime at endpoint startup and persists inputs and results to Object Storage or Shared Filesystem.

**Product:** [NVIDIA Parabricks](https://docs.nvidia.com/clara/parabricks/latest/) · **Runtime:** [`nvcr.io/nvidia/clara/clara-parabricks`](https://catalog.ngc.nvidia.com/orgs/nvidia/teams/clara/containers/clara-parabricks)

<!-- /factory:intro -->

---

title: NVIDIA Parabricks DeepVariant REST + MCP
category: life-sciences
type: endpoint
runtime: gpu-h100-sxm
frameworks: [parabricks, deepvariant, fastapi, mcp]
keywords: [genomics, variant-calling, nvidia-ngc, rest, mcp, agent]
difficulty: advanced

---

## What you get

- A bounded asynchronous DeepVariant API on port 8000 with `/docs`.
- A Streamable HTTP MCP server at `/mcp` for agent/tool integrations.
- Shared REST/MCP queue, run IDs, state, and authenticated artifacts.
- `PARABRICKS_VERSION=latest` or an exact official NVIDIA runtime tag.
- A real startup probe for `pbrun`, version, and GPU visibility.
- Persistent runs under `/mnt/hcls/parabricks-deepvariant/runs/<run-id>`.
- Mounted private inputs under `/mnt/hcls/parabricks-deepvariant/fixtures`.

The wrapper does not repackage Parabricks. On fresh startup it uses
`NGC_API_KEY` to pull the chosen official image, records its digest, prepares the
GPU runtime, and starts the API only after its readiness checks pass. Restarting
an endpoint configured with `latest` lets it select a newer compatible stable
release without rebuilding the wrapper.

The wrapper tag in the button resolves to
`sha256:e76f3185a68c99bf979cecfc7be476e1debfe60c842814cbb104a00157eb19d0`.

## Create the endpoint

Click **Create Endpoint**, select your project, and review the form:

1. Paste your NVIDIA NGC API key into `NGC_API_KEY`; the launcher supplies the
   fixed `$oauthtoken` username.
2. Leave `PARABRICKS_VERSION=latest` or enter an exact tag such as `4.7.1-1`.
3. Keep `PARABRICKS_GPU_COUNT=1` for the one-H100 default. Match this value if
   you deliberately select another supported GPU count.
4. Keep **Token authentication** enabled and copy its generated token. One token
   protects both REST and MCP; it is not an application environment variable.
5. Attach Object Storage or Shared Filesystem read-write at `/mnt/hcls`.

### Environment variables

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `NGC_API_KEY` | yes | empty | Pulls the official NVIDIA runtime. |
| `PARABRICKS_VERSION` | no | `latest` | Exact tag or newest compatible stable tag. |
| `PARABRICKS_GPU_COUNT` | no | `1` | Required visible GPU count for readiness and `pbrun`. |

The URL includes every application variable without embedding a secret. Pinned
tags never silently fall back.

## Input and storage

For production-scale data, attach a persistent resource at `/mnt/hcls` and put
reference, index, reads, and reads-index files under
`/mnt/hcls/parabricks-deepvariant/fixtures`. Requests use safe basenames and
mounted paths confined to that directory.

The API can also download a public HTTPS input when the request provides its
filename, URL, and SHA-256. Redirects, resolved addresses, size, and digest are
validated. Signed URLs may be used for a single run but are redacted from
persisted results and logs. Prefer the mounted lane for private or large inputs.

Object Storage credentials are configured on the Serverless volume, not passed
to the API. Without an attached volume, inputs and results can disappear when a
worker is replaced. Use only data you are authorized to process; the included
acceptance workflow uses public nonclinical fixtures.

## Test REST and MCP

```bash
export BASE_URL='https://port8000-<id>.tunnel.applications.<region>.nebius.cloud'
export TOKEN='<endpoint-token-generated-during-create>'
```

First boot can take 15–20 minutes because the official image is large. Poll the
application readiness route rather than treating the Serverless instance state
as readiness:

```bash
until curl -sf -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/v1/health/ready" >/dev/null; do echo 'waiting for Parabricks…'; sleep 20; done
```

The live capabilities document supplies the exact public chr20 smoke input and
SHA-256 values. Test both protocols with it:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-client.txt
export HCLS_ENDPOINT_TOKEN="$TOKEN"
curl -fsS -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/v1/capabilities" > capabilities.json
PAYLOAD="$(python3 -c 'import json; d=json.load(open("capabilities.json")); print(json.dumps(next(x["input"] for x in d["examples"] if x["id"]=="deepvariant-chr20-smoke")))')"
.venv/bin/python scripts/test_endpoint.py "$BASE_URL" \
  --payload "$PAYLOAD" --timeout 1800
```

Configure an MCP-capable agent with the managed URL plus `/mcp`, Streamable HTTP
transport, and the same bearer token. Available tools are `get_capabilities`,
`submit_run`, `get_run`, `list_runs`, `cancel_run`, and `list_run_artifacts`.
Install the included
[`parabricks-serverless` Agent Skill](./skills/parabricks-serverless/SKILL.md)
for safe input, polling, provenance, and result-handling guidance. Credentials
remain in the MCP client configuration, never in the skill.

## Expected output

The bounded chr20 smoke should reach `succeeded`, report 78 variant records, and
produce an indexed compressed VCF, logs, input hashes, provenance, and artifact
hashes. Qualification was repeated on 2026-09-09 using regular H100; `latest` selected
Parabricks `4.7.1-1` at digest
`sha256:a748d86cbb850641a1e0afae6de2e7422f1375e4a0cce08a5c2cead9fa302237`.
Independent REST and MCP chr20 runs each produced 78 variants in about 12 seconds;
their artifacts were verified through REST and in the mounted bucket.

The one-H100 shape is sized for the bounded demonstration. Production genomics
throughput and disk needs depend on genome, coverage, caller mode, and input
layout; qualify a larger supported shape rather than extrapolating this smoke.
Variant calls are research outputs, not diagnostic conclusions.

## Build the wrapper

```bash
cd templates/endpoint-parabricks-deepvariant
docker build --platform linux/amd64 \
  --build-arg HCLS_IMAGE_REVISION="$(git rev-parse HEAD)" \
  -t <your-registry>/parabricks-rest-mcp:1 .
```

<!-- factory:cli -->

## CLI alternative

```bash
export NEBIUS_PROJECT_ID='project-...'
export NEBIUS_SUBNET_ID='vpcsubnet-...'
export NGC_API_KEY='<your-ngc-api-key>'
export PARABRICKS_VOLUME='computefilesystem-<id>:/mnt/hcls:rw'
# Or: s3://<bucket>:/mnt/hcls:rw:<aws-profile>@<secret-selector>

nebius ai endpoint create \
  --parent-id "$NEBIUS_PROJECT_ID" \
  --name parabricks-deepvariant-rest-mcp \
  --image cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/hcls/parabricks-deepvariant-api:20260908-dynamic-v3 \
  --public \
  --platform gpu-h100-sxm \
  --preset 1gpu-16vcpu-200gb \
  --container-port 8000 \
  --disk-size 500Gi \
  --subnet-id "$NEBIUS_SUBNET_ID" \
  --auth token \
  --env "NGC_API_KEY=$NGC_API_KEY" \
  --env 'PARABRICKS_VERSION=latest' \
  --env 'PARABRICKS_GPU_COUNT=1' \
  --volume "$PARABRICKS_VOLUME"
```

<!-- /factory:cli -->

## Cost and cleanup

The default is a retained regular H100 with a 500 GiB boot disk. GPU, disk, and
attached-storage charges accrue while provisioned. Use preemptible only for an
interruptible test, and stop or delete the endpoint when it is no longer needed.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| NGC returns 401/403 | Supply `NGC_API_KEY`, not the endpoint bearer token. |
| Endpoint returns 502 during first boot | The large runtime is still downloading/preparing; poll readiness and inspect logs. |
| Readiness reports too few GPUs | Match `PARABRICKS_GPU_COUNT` to the selected preset. |
| Mounted input is rejected | Use a safe basename below the documented fixture directory. |
| HTTPS input fails | Check public DNS, HTTPS, size, and exact SHA-256. |
| Outputs disappear after restart | Attach Object Storage or Shared Filesystem at `/mnt/hcls`. |
| REST works but MCP returns 401 | Use the same Serverless endpoint token for `/mcp`. |
