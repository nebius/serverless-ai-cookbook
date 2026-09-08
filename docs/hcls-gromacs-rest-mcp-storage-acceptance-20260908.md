# GROMACS REST, MCP, and storage-lane acceptance

Accepted on 2026-09-08 in project `project-e00z6b02t8ddk96c49`, region
`eu-north1`. Both accepted endpoints intentionally remain `RUNNING` for owner and
customer verification and continue to incur L40S Compute charges.

## Running endpoints

| Storage lane | Endpoint ID | Managed HTTPS URL | Persistent source |
| --- | --- | --- | --- |
| Object Storage | `aiendpoint-e00s589836j11j7aw5` | <https://port8000-nmzr10pnhz4mj7s.tunnel.applications.eu-north1.nebius.cloud> | `s3://parabricks-test` at `/mnt/hcls` |
| Shared Filesystem | `aiendpoint-e00j1sydy2r6z01abc` | <https://port8000-c2k6fvd25z9max9.tunnel.applications.eu-north1.nebius.cloud> | `computefilesystem-e00tyxkbqexf16q8c6` at `/mnt/hcls` |

Both use regular `gpu-l40s-a` capacity, preset `1gpu-8vcpu-32gb`, a 100 GiB
container disk, public managed HTTPS, port 8000, and Nebius token authentication.
The same endpoint token protects REST and MCP; unauthenticated requests to both
protocols returned HTTP 401.

## Accepted image

```text
cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/hcls/gromacs-md-api:20260908-2341ac7
sha256:e8e06b7657218226d19e90ccef37c72dff8197aca2f1c94314a2856eec9b7e34
```

The public image is `linux/amd64`, requires no registry credentials, and starts from
the official NVIDIA image pinned in the Dockerfile:

```text
nvcr.io/hpc/gromacs:2023.2@sha256:04d5ac4416523624bbfcb36c85a63fd8a6ac8acf7c2eeb1af89dd03c60d45daf
```

An anonymous Docker manifest lookup succeeded. The final SBOM and scan evidence is
under `/home/tux/.task-output/hcls-gromacs-storage-mcp-pilot-20260908/`:

- `sbom-2341ac7.spdx.json`
- `grype-2341ac7.json`: 0 high, 0 critical
- `trivy-2341ac7.json`: 0 high, 0 critical, 0 secrets

The remaining medium/low findings are inherited OS or language packages and are
recorded in the reports.

## Live results and restart recovery

The acceptance client submitted one real GPU run through REST and one through MCP
to each endpoint. An MCP-created run was read and its artifact was downloaded through
REST with the same token.

| Lane / protocol | Run ID | Result | `result.json` SHA-256 |
| --- | --- | --- | --- |
| Object Storage / REST | `90dea53703214b43a117980621309bc3` | succeeded; `4341.802 ns/day`; 14 artifacts | `7619d6be7d9f633dab6f51fd292f4b407d9fdf50cd4c645e6f4db04f15be0c2b` |
| Object Storage / MCP | `b81bfb68f17340e29b28f1c403f8331a` | succeeded; `4419.962 ns/day`; 14 artifacts | `293c27da16bf591636ad6e8c53f43e62176b0bdfcce7b00272592089de044e09` |
| Shared Filesystem / REST | `cb218bacffae4bd285d7c4011bc7d778` | succeeded; `4399.910 ns/day`; 14 artifacts | `308123d58d3767cbbe41423e8c9954d703e27125a564d01fc8c4697b20f64e1b` |
| Shared Filesystem / MCP | `c6df9a8d0c994e7f83c2d1086f3ba308` | succeeded; `4464.852 ns/day`; 14 artifacts | `e9802c33974780649fd3372a7ada386a12695a050588b97f2036a101ae59e93f` |

Both endpoints were stopped, started on replacement Compute instances, and queried
again by those four exact run IDs. Every record restored as `succeeded`, with 14
artifacts and the same result hash. The S3 API independently showed the two Object
Storage runs, each with three non-empty ordered status snapshots and zero temporary
objects.

## Test it

Retrieve the endpoint token from the customer-owned MysteryBox secret whose payload
key is `AUTH_TOKEN`; do not put it in a URL, image, repository, or chat message.

```bash
python3 -m venv .venv-hcls-client
.venv-hcls-client/bin/pip install \
  -r templates/endpoint-hcls-gromacs/requirements-client.txt

export HCLS_ENDPOINT_TOKEN="$(nebius mysterybox payload get-by-key \
  --secret-id <AUTH_TOKEN_SECRET_ID> \
  --key AUTH_TOKEN --format json | jq -r '.data.string_value')"

.venv-hcls-client/bin/python \
  templates/endpoint-hcls-gromacs/scripts/test_endpoint.py \
  'https://port8000-nmzr10pnhz4mj7s.tunnel.applications.eu-north1.nebius.cloud'

.venv-hcls-client/bin/python \
  templates/endpoint-hcls-gromacs/scripts/test_endpoint.py \
  'https://port8000-c2k6fvd25z9max9.tunnel.applications.eu-north1.nebius.cloud'

unset HCLS_ENDPOINT_TOKEN
```

The script creates a TPR, runs GROMACS with GPU nonbonded offload once through REST
and once through MCP, polls both runs, downloads `result.json`, and verifies its
SHA-256. It creates new billable scientific runs; opening `/docs` or connecting an
MCP client does not.

REST documentation is at `<endpoint>/docs`. An MCP client connects to
`<endpoint>/mcp` and sends the same `Authorization: Bearer <token>` header. A typical
HTTP MCP configuration is:

```json
{
  "mcpServers": {
    "gromacs": {
      "type": "http",
      "url": "https://<managed-endpoint-host>/mcp",
      "headers": {
        "Authorization": "Bearer ${HCLS_ENDPOINT_TOKEN}"
      }
    }
  }
}
```

## Customer deployment

The catalog deploy link preloads the public image, port 8000, regular L40S platform,
preset, 100 GiB container disk, `/mnt/hcls` mount path, and a 32 GiB filesystem
default:

<https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fhcls%2Fgromacs-md-api%3A20260908-2341ac7&targetPort=8000&platform=gpu-l40s-a&preset=1gpu-8vcpu-32gb&diskSize=100GiB&preemptible=false&volumeMountPath=%2Fmnt%2Fhcls&volumeSize=32>

The customer must still select their project/subnet, enable token authentication,
and attach exactly one customer-owned storage lane. No application environment
variables are required.

For Shared Filesystem, attach `computefilesystem-...:/mnt/hcls:rw`. For Object
Storage, use the explicit form below; do not use a bucket resource ID for this
template:

```text
s3://<bucket>:/mnt/hcls:rw:<local-aws-profile>@<s3-secret-selector>
```

The S3 MysteryBox version must contain `S3_ACCESS_KEY_ID` and
`S3_SECRET_ACCESS_KEY`. Nebius CLI 0.12 also resolves the profile's region and
endpoint locally, so configure the selected AWS profile with the matching credentials,
region such as `eu-north1`, and
`https://storage.eu-north1.nebius.cloud`. The credential is consumed by the
Serverless mount layer and is not injected into the application.

For a fully parameterized CLI deployment, use
`templates/endpoint-hcls-gromacs/scripts/deploy.sh`. The immutable digest is recorded
above, but the deployment uses the unique, non-overwritten release tag: a full digest
reference currently fails Serverless creation because its 136-character image value
is copied into a Compute label with a 64-character limit.

## Operations and cleanup

The pilot S3 access key expires on 2027-09-08. Rotate it before then, create a new
MysteryBox version with the two required payload keys, and recreate or update the
endpoint so its pinned secret version changes.

To stop Compute charges while retaining configuration and persistent data:

```bash
nebius ai endpoint stop --id aiendpoint-e00s589836j11j7aw5
nebius ai endpoint stop --id aiendpoint-e00j1sydy2r6z01abc
```

The Shared Filesystem continues to incur storage charges while endpoints are stopped.
Three stopped prototype endpoints, one unused service account, and one obsolete
secret version were deleted after acceptance; those control-plane resources are not
recoverable. Accepted endpoint resources and test artifacts were retained.
