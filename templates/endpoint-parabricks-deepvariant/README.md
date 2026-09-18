---
title: NVIDIA Parabricks DeepVariant REST + MCP
category: life-sciences
type: endpoint
runtime: gpu-h100-sxm
frameworks: [parabricks, deepvariant, fastapi, mcp]
keywords: [genomics, variant-calling, nvidia-ngc, rest, mcp, agent]
difficulty: advanced
---

# NVIDIA Parabricks DeepVariant REST + MCP

**Use public, nonclinical research fixtures only. Do not upload protected health
information (PHI), patient data, or clinical genomes to this public token-authenticated
endpoint. Token authentication alone does not make it suitable for clinical data.**

<!-- markdownlint-disable MD013 MD033 -->

**Build first:** this template includes NVIDIA-licensed software. Follow
[Build the wrapper](#build-the-wrapper) to publish the image in your own registry.
The button contains an example image name: replace it with your built image's
digest and configure that registry's pull credentials before creating the endpoint.
No public redistributable wrapper image is assumed.

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=registry.example.org%2Fyour-team%2Fparabricks-rest-mcp%3A4.7.1-1&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=false&amp;auth=true&amp;env=PARABRICKS_GPU_COUNT%3D1"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Run bounded NVIDIA Parabricks DeepVariant workflows through REST or MCP. The wrapper is built directly on the digest-pinned NVIDIA Parabricks 4.7.1-1 image and executes its tools in place. Attach Object Storage or Shared Filesystem for persistent inputs and results.

**Product:** [NVIDIA Parabricks](https://docs.nvidia.com/clara/parabricks/latest/) · **Runtime:** [`nvcr.io/nvidia/clara/clara-parabricks`](https://catalog.ngc.nvidia.com/orgs/nvidia/teams/clara/containers/clara-parabricks)

<!-- /factory:intro -->


## What you get

- A bounded asynchronous DeepVariant API on port 8000 with `/docs`.
- A Streamable HTTP MCP server at `/mcp` for agent/tool integrations.
- Shared REST/MCP queue, run IDs, state, and authenticated artifacts.
- NVIDIA Parabricks 4.7.1-1 pinned at image build time.
- A real startup probe for `pbrun`, version, and GPU visibility.
- Runs under `/mnt/hcls/parabricks-deepvariant/runs/<run-id>`; persistent only with an attached volume.
- Mounted private inputs under `/mnt/hcls/parabricks-deepvariant/fixtures`.

The Dockerfile uses `FROM nvcr.io/nvidia/clara/clara-parabricks:4.7.1-1`
with the tested platform digest. It retains NVIDIA's runtime and license notices,
adds the Apache-2.0 cookbook API, and runs `pbrun` directly. There is no boot-time
image extraction or `chroot`. Rebuild and validate the image to change versions.

NVIDIA's [Parabricks license terms](https://docs.nvidia.com/clara/parabricks/about-parabricks/end-user-license-agreements)
apply to the runtime. Build and store the derived image in a registry you control.

## Create the endpoint

The button does not attach storage. Manually attach Object Storage or Shared
Filesystem read-write at `/mnt/hcls` in the create form for persistent results.
Without that attachment, `/mnt/hcls` is on ephemeral disk and results can be lost
when the endpoint is replaced or deleted.

Click **Create Endpoint**, select your project, and review the form:

1. Select the image built using the instructions below. For an image hosted on
   `nvcr.io`, enter `$oauthtoken` as the **registry username** and your NGC key as
   the **registry password**. For a derived image in another private registry,
   use that registry's credentials. Never put the NGC key in an environment variable.
2. Keep `PARABRICKS_GPU_COUNT=1` for the one-H100 default.
3. Keep **Token authentication** enabled and copy the generated token for REST
   and MCP.
4. Manually attach Object Storage or Shared Filesystem read-write at `/mnt/hcls`.

The only prefilled application variable is `PARABRICKS_GPU_COUNT=1`; the source
code and image use the same default. The engine version is fixed in the image.

## Input and storage

For production-scale data, attach a persistent resource at `/mnt/hcls` and put
reference, index, reads, and reads-index files under
`/mnt/hcls/parabricks-deepvariant/fixtures`. The same storage resource must be
mounted on the machine preparing the request and on the endpoint. Requests use
safe basenames and mounted paths confined to that directory.

The API can also download a public HTTPS input when the request provides its
filename, URL, and SHA-256. Redirects, resolved addresses, size, and digest are
validated. Signed URLs may be used for a single run but are redacted from
persisted results and logs. Prefer the mounted lane for private or large inputs.

### Request fields

| Field | Required | Description |
| --- | --- | --- |
| `sample_id` | yes | Sample name: letters, digits, `.`, `_`, or `-`; maximum 80 characters. |
| `reference` | yes | Reference FASTA source object. |
| `reference_index` | yes | Matching FASTA `.fai` source object. |
| `reads` | yes | Aligned reads BAM source object. |
| `reads_index` | yes | Matching BAM `.bai` source object. |
| `mode` | no | `shortread` (default), `pacbio`, or `ont`. |
| `intervals` | no | Up to 32 reference regions, for example `chr20:10000000-10010000`. |
| `use_wes_model` | no | `true` only for `shortread` whole-exome data. |

Each source object needs a safe `filename`, a SHA-256 checksum, and exactly one
input location: `path` for a basename in the mounted fixture directory, or
`url` for a public HTTPS download. Reference/index and BAM/index pairs must
match; intervals must use the reference contig names.

The following example builds `request.json` for four files already in the shared
fixture directory. Replace the filenames, sample ID, and interval with your own
validated inputs. Run it on a machine where that same storage is mounted at
`/mnt/hcls`:

```bash
python3 - <<'PY' > request.json
import hashlib
import json
from pathlib import Path

fixtures = Path("/mnt/hcls/parabricks-deepvariant/fixtures")

def sha256_file(source):
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def mounted(filename):
    source = fixtures / filename
    return {"filename": filename, "path": filename, "sha256": sha256_file(source)}

print(json.dumps({
    "input": {
        "sample_id": "HG003-chr20",
        "reference": mounted("GRCh38_no_alt.fna"),
        "reference_index": mounted("GRCh38_no_alt.fna.fai"),
        "reads": mounted("HG003.chr20.bam"),
        "reads_index": mounted("HG003.chr20.bam.bai"),
        "mode": "shortread",
        "intervals": ["chr20"],
    },
    "client_request_id": "deepvariant-custom-001",
    "research_use_acknowledgement": True,
}))
PY

RUN_ID="$(curl -sS -X POST "$BASE_URL/v1/runs" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  --data-binary @request.json \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"
echo "$RUN_ID"
```

Use `GET /v1/runs/<run-id>` to monitor the run and download its artifacts after
it succeeds.

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
SHA-256 values. Test both protocols with it. The included client requires a
local clone of this repository; run it from the DeepVariant template directory:

```bash
git clone --depth 1 https://github.com/nebius/serverless-ai-cookbook.git
cd serverless-ai-cookbook/templates/endpoint-parabricks-deepvariant
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
hashes. See [validation results](./VALIDATION.md) for the rebuilt image's H100 REST/MCP
qualification. Both runs produced 78 variants; this rerun did not attach a bucket.

The one-H100 shape is sized for the bounded demonstration. Production genomics
throughput and disk needs depend on genome, coverage, caller mode, and input
layout; qualify a larger supported shape rather than extrapolating this smoke.
Variant calls are research outputs, not diagnostic conclusions.

## Build the wrapper

Authenticate Docker to NGC before building. Supply the NGC key over stdin; it
is used only to pull the base image, not copied into the image or application.
Publish the result to your own registry and use its digest in the create form.

```bash
read -rs -p 'NGC API key: ' NGC_API_KEY; echo
printf '%s' "$NGC_API_KEY" | docker login nvcr.io -u '$oauthtoken' --password-stdin
unset NGC_API_KEY
```

```bash
cd templates/endpoint-parabricks-deepvariant
export PARABRICKS_IMAGE='registry.example.org/your-team/parabricks-rest-mcp:4.7.1-1'
# Authenticate to your destination registry using that registry's credentials.
docker build --platform linux/amd64 \
  --build-arg HCLS_IMAGE_REVISION="$(git rev-parse HEAD)" \
  -t "$PARABRICKS_IMAGE" .
docker push "$PARABRICKS_IMAGE"
docker image inspect "$PARABRICKS_IMAGE" --format '{{index .RepoDigests 0}}'
```

<!-- factory:cli -->

## CLI alternative

Set `PARABRICKS_IMAGE` to your published image reference. CLI 0.12.206 rejected
references longer than 64 characters in a VM label; for that version, use a short
versioned alias and verify it resolves to your recorded build digest before deployment.

```bash
export PARABRICKS_IMAGE='registry.example.org/your-team/parabricks-rest-mcp:4.7.1-1'
```

```bash
export NEBIUS_PROJECT_ID='project-...'
export NEBIUS_SUBNET_ID='vpcsubnet-...'
export REGISTRY_SECRET='<MysteryBox selector with REGISTRY_USERNAME and REGISTRY_PASSWORD>'
export PARABRICKS_VOLUME='computefilesystem-<id>:/mnt/hcls:rw'
# Or: s3://<bucket>:/mnt/hcls:rw:<aws-profile>@<secret-selector>

nebius ai endpoint create \
  --parent-id "$NEBIUS_PROJECT_ID" \
  --name parabricks-deepvariant-rest-mcp \
  --image "$PARABRICKS_IMAGE" \
  --public \
  --platform gpu-h100-sxm \
  --preset 1gpu-16vcpu-200gb \
  --container-port 8000 \
  --disk-size 500Gi \
  --subnet-id "$NEBIUS_SUBNET_ID" \
  --auth token \
  --registry-secret "$REGISTRY_SECRET" \
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
| Registry returns 401/403 | Configure credentials for the registry hosting the selected image; an NGC key only authenticates to NGC. |
| Endpoint returns 502 during first boot | The large runtime is still downloading/preparing; poll readiness and inspect logs. |
| Readiness reports too few GPUs | Match `PARABRICKS_GPU_COUNT` to the selected preset. |
| Mounted input is rejected | Use a safe basename below the documented fixture directory. |
| HTTPS input fails | Check public DNS, HTTPS, size, and exact SHA-256. |
| Outputs disappear after restart | Attach Object Storage or Shared Filesystem at `/mnt/hcls`. |
| REST works but MCP returns 401 | Use the same Serverless endpoint token for `/mcp`. |
