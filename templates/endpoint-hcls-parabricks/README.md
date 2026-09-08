# NVIDIA Parabricks DeepVariant REST + MCP API

This template exposes the official NVIDIA Parabricks runtime through the shared HCLS
asynchronous API. The small wrapper image pulls
`nvcr.io/nvidia/clara/clara-parabricks` when the endpoint starts, authenticates with
`NGC_API_KEY`, and selects either the requested tag or the highest stable tag when
`PARABRICKS_VERSION=latest`.

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fhcls%2Fparabricks-deepvariant-api%3A20260908-dynamic-v3&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=false&amp;volumeMountPath=%2Fmnt%2Fhcls&amp;volumeSize=32"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

The Console URL can prefill only image, port, compute, disk, capacity type, and mount
path. Before selecting **Create**, add every item below; none is implied by the link:

| Setting | Value |
| --- | --- |
| Plain environment variable | `PARABRICKS_VERSION=latest` (or an exact NVIDIA tag such as `4.7.1-1`) |
| Secret environment variable | `NGC_API_KEY` from a MysteryBox payload key named `NGC_API_KEY` |
| Authentication | Serverless **Token authentication**, generated or backed by a MysteryBox token secret |
| Persistent storage | Object Storage or Shared Filesystem, read-write at `/mnt/hcls` |

At qualification time, `latest` resolved to NVIDIA tag `4.7.1-1` and digest
`sha256:a748d86cbb850641a1e0afae6de2e7422f1375e4a0cce08a5c2cead9fa302237`.
The endpoint publishes its requested tag, resolved tag, digest, and GPU startup-probe
result in `/v1/health/ready` and `/v1/capabilities`. Changing `PARABRICKS_VERSION` on
a new endpoint changes the official runtime without rebuilding the API wrapper.

## Deploy from the CLI

The helper makes all otherwise-hidden inputs explicit and supports both storage lanes:

```bash
export NEBIUS_PROJECT_ID=project-...
export NEBIUS_SUBNET_ID=vpcsubnet-...
export NGC_API_KEY_SECRET_SELECTOR=mbsec-...@mbsecver-...
export HCLS_STORAGE_SOURCE=s3://customer-bucket
export S3_CREDENTIAL_SECRET_SELECTOR=mbsec-...@mbsecver-...
export S3_PROFILE=hcls
export AWS_CONFIG_FILE=/path/to/aws-config
# Or: export HCLS_STORAGE_SOURCE=computefilesystem-...

# Optional; defaults shown here.
export PARABRICKS_VERSION=latest
export AUTH_TOKEN_SECRET_SELECTOR=mbsec-...@mbsecver-...
templates/endpoint-hcls-parabricks/scripts/deploy.sh
```

The named AWS profile must be explicit as well:

```ini
[profile hcls]
region=eu-north1
endpoint_url=https://storage.eu-north1.nebius.cloud
```

If neither `AUTH_TOKEN_SECRET_SELECTOR` nor `AUTH_TOKEN` is set, the helper generates
a strong token and shows it once. The NGC key authenticates the NVIDIA image pull; it
does not authenticate API users.

## API and MCP

REST and MCP share the endpoint URL, Serverless token, run queue, and artifacts:

- REST base: `https://<managed-endpoint>/v1`
- MCP Streamable HTTP: `https://<managed-endpoint>/mcp`
- Persistent runs: `/mnt/hcls/parabricks-deepvariant/runs/<run_id>`
- Optional mounted private fixtures: `/mnt/hcls/parabricks-deepvariant/fixtures`

The guided bounded smoke uses the official public Google DeepVariant chr20 fixtures,
validates every SHA-256, and runs without private input data. Production inputs can be
copied into the fixture directory or supplied by validated public HTTPS URL plus
SHA-256. Signed URLs are accepted for a run but are not persisted in results or logs.

Test REST and MCP with the exact `input` object returned by
`GET /v1/capabilities`:

```bash
python3 -m venv .venv-hcls-client
.venv-hcls-client/bin/pip install -r templates/hcls-common/requirements-client.txt
export HCLS_ENDPOINT_TOKEN='<Serverless token>'
export ENDPOINT_URL='https://<managed-endpoint>'
curl -fsS -H "Authorization: Bearer $HCLS_ENDPOINT_TOKEN" \
  "$ENDPOINT_URL/v1/capabilities" > capabilities.json
PAYLOAD=$(jq -c '.examples[] | select(.id=="deepvariant-chr20-smoke") | .input' capabilities.json)
.venv-hcls-client/bin/python templates/hcls-common/scripts/test_endpoint.py \
  "$ENDPOINT_URL" --payload "$PAYLOAD" --timeout 1800
```

The one-H100 shape is suitable for the bounded smoke. NVIDIA recommends more CPU and
GPU capacity for production throughput; qualify the eight-H100 Serverless preset for
large customer workloads. A 500 GiB endpoint disk is the deploy-link default because
genomics intermediates can be large. Results include compressed VCF, Parabricks log,
input hashes, GPU identity, and variant count.

See [the common API](../hcls-common/README.md) and
[HCLS Workbench](../hcls-workbench/README.md). Variant calls are research outputs and
require independent validation.

**Product docs:** [NVIDIA Parabricks](https://docs.nvidia.com/clara/parabricks/latest/)
