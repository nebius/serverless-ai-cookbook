---
title: AutoDock Vina REST + MCP
category: life-sciences
type: endpoint
runtime: cpu-d3
frameworks: [autodock-vina, fastapi, mcp]
keywords: [molecular-docking, virtual-screening, cpu, rest, mcp, agent]
difficulty: intermediate
---

# AutoDock Vina REST + MCP

<!-- markdownlint-disable MD013 MD033 -->

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fcb23%40sha256%3Af80ba1d50f7bbbd6192f9695a71691bdd37390d3bfc0e6152d9cb0a80ef2f171&amp;targetPort=8000&amp;platform=cpu-d3&amp;preset=4vcpu-16gb&amp;diskSize=100GiB&amp;preemptible=false&amp;auth=true"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Run low-cost AutoDock Vina redocking and small docking workloads through REST or MCP. The endpoint uses CPU intentionally, exposes a bounded asynchronous API, and persists results to Object Storage or Shared Filesystem.

**License:** [Apache-2.0](https://github.com/ccsb-scripps/AutoDock-Vina/blob/develop/LICENSE) · **Engine:** [AutoDock Vina 1.2.7](https://github.com/ccsb-scripps/AutoDock-Vina)

<!-- /factory:intro -->


## What you get

- A bounded asynchronous Vina API on port 8000 with `/docs`.
- A Streamable HTTP MCP server at `/mcp`.
- Shared REST/MCP queue, run IDs, state, and artifact hashes.
- A bundled public 1IEP/STI redocking smoke and custom PDBQT inputs.
- Runs under `/mnt/hcls/autodock-vina/runs/<run-id>`; persistent only with an attached volume.

This template intentionally uses `cpu-d3`: AutoDock Vina is multithreaded CPU
software and is distinct from AutoDock-GPU, which implements AutoDock4 scoring.
Their numerical scores are not interchangeable.

The image pins Vina 1.2.7 and bundles official example assets from upstream
commit `8eb40404f4f45608acb3b01427587ac049f27c1f`. No NGC key or model-download
credential is required.

## Create the endpoint

The button does not attach storage. Manually attach Object Storage or Shared
Filesystem read-write at `/mnt/hcls` in the create form for persistent results.
Without that attachment, `/mnt/hcls` is on ephemeral disk and results can be lost
when the endpoint is replaced or deleted.

Click **Create Endpoint**, select your project, then:

1. Keep **Token authentication** enabled and copy the generated token. The same
   token protects REST and MCP; it is not an environment variable.
2. Attach either Object Storage or Shared Filesystem read-write at `/mnt/hcls`.
3. Keep the CPU shape for the intended low-cost interactive workflow. Increase
   CPU only after measuring your receptor, box, exhaustiveness, and batch size.

There are no required application environment variables or external image-pull
secrets. The one-click URL includes every safe default and contains no credential.

## Storage

Vina runs on endpoint-local scratch, then publishes receptor, ligand, poses,
scores, summary, logs, and hashes to `/mnt/hcls/autodock-vina/runs/<run-id>`.
Attach Object Storage or Shared Filesystem at `/mnt/hcls`; credentials for an
Object Storage mount belong to the Serverless volume controls, not the API.
Without a mount, results can disappear when the worker is replaced.

## Test REST and MCP

```bash
export BASE_URL='https://port8000-<id>.tunnel.applications.<region>.nebius.cloud'
export TOKEN='<endpoint-token-generated-during-create>'
```

Verify that unauthenticated traffic is rejected, then submit the public redocking
smoke:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE_URL/v1/health/ready"
curl -sS -H "Authorization: Bearer $TOKEN" "$BASE_URL/v1/health/ready" \
  | python3 -m json.tool

RUN_ID="$({
  curl -sS -X POST "$BASE_URL/v1/runs" \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d '{
      "input": {
        "center": [15.19, 53.903, 16.917],
        "size": [20.0, 20.0, 20.0],
        "exhaustiveness": 8,
        "n_poses": 9,
        "seed": 17
      },
      "client_request_id": "vina-first-run",
      "research_use_acknowledgement": true
    }'
} | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"
```

Use the included client for one real run through each protocol plus cross-protocol
artifact verification. It requires a local clone of this repository; run it from
the Vina template directory:

```bash
git clone --depth 1 https://github.com/nebius/serverless-ai-cookbook.git
cd serverless-ai-cookbook/templates/endpoint-autodock-vina
python3 -m venv .venv
.venv/bin/pip install -r requirements-client.txt
export HCLS_ENDPOINT_TOKEN="$TOKEN"
.venv/bin/python scripts/test_endpoint.py "$BASE_URL" \
  --payload '{"center":[15.19,53.903,16.917],"size":[20,20,20],"exhaustiveness":8,"n_poses":9,"seed":17}'
```

Configure an MCP-capable agent with the managed URL plus `/mcp`, Streamable HTTP
transport, and the same bearer token. Available tools are `get_capabilities`,
`submit_run`, `get_run`, `list_runs`, `cancel_run`, and `list_run_artifacts`.
Install the included
[`autodock-vina-serverless` Agent Skill](./skills/autodock-vina-serverless/SKILL.md)
for box, input, submission, score, and artifact guidance. Credentials stay in the
MCP client configuration, never in the skill.

## Custom inputs

Supply one or both custom structures as PDBQT text. A custom structure requires
an explicit three-number `center` and `size`; the endpoint does not infer a
binding site or prepare PDB, SDF, MOL2, or SMILES files.

| Input field | Required | Description |
| --- | --- | --- |
| `receptor_pdbqt` | custom receptor | Receptor PDBQT text, up to 2,000,000 characters. |
| `ligand_pdbqt` | custom ligand | Ligand PDBQT text, up to 2,000,000 characters. |
| `center` | custom input | `[x, y, z]` center of the docking box. |
| `size` | custom input | `[x, y, z]` box dimensions; each value is 1 to 60 Å. |
| `exhaustiveness` | no | Search effort: default 8, maximum 64. |
| `n_poses` | no | Number of poses: default 9, maximum 20. |
| `cpu` | no | CPU threads: default automatic, maximum 32. |
| `seed` | no | Random seed: default 17. |

The following example builds `request.json` from local PDBQT files, then sends
it through the REST API:

```bash
python3 - <<'PY' > request.json
import json
from pathlib import Path

print(json.dumps({
    "input": {
        "receptor_pdbqt": Path("receptor.pdbqt").read_text(),
        "ligand_pdbqt": Path("ligand.pdbqt").read_text(),
        "center": [30.103, 6.152, 15.584],
        "size": [20.0, 20.0, 20.0],
        "exhaustiveness": 8,
        "n_poses": 20,
        "seed": 17,
    },
    "client_request_id": "custom-vina-run-001",
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

## Expected output

A successful run produces ranked `poses.pdbqt`, `scores.csv`, a docking summary,
input copies, and SHA-256 metadata. Results report Vina version, box, search
parameters, and energy components in kcal/mol. See [validation results](./VALIDATION.md) for the current image and live REST/MCP tests.

Docking scores and poses are research heuristics. They require independent
chemical preparation, protonation, search-space, and experimental validation.

## Build the image

```bash
cd templates/endpoint-autodock-vina
docker build --platform linux/amd64 \
  --build-arg HCLS_IMAGE_REVISION="$(git rev-parse HEAD)" \
  -t <your-registry>/autodock-vina-rest-mcp:1 .
```

<!-- factory:cli -->

## CLI alternative

The tested image is `cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/cb23@sha256:f80ba1d50f7bbbd6192f9695a71691bdd37390d3bfc0e6152d9cb0a80ef2f171`.
The qualification used Nebius CLI 0.12.206, which rejects endpoint image references
longer than 64 characters when creating a VM label. For that CLI, use the short
alias below and verify its digest with [crane](https://github.com/google/go-containerregistry/tree/main/cmd/crane)
before creating the endpoint. Do not use an alias whose digest differs.

```bash
export IMAGE='cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/cb23:r0918'
test "$(crane digest "$IMAGE")" = 'sha256:f80ba1d50f7bbbd6192f9695a71691bdd37390d3bfc0e6152d9cb0a80ef2f171' || exit 1
```

```bash
export NEBIUS_PROJECT_ID='project-...'
export NEBIUS_SUBNET_ID='vpcsubnet-...'
export VINA_VOLUME='computefilesystem-<id>:/mnt/hcls:rw'
# Or: s3://<bucket>:/mnt/hcls:rw:<aws-profile>@<secret-selector>

nebius ai endpoint create \
  --parent-id "$NEBIUS_PROJECT_ID" \
  --name autodock-vina-rest-mcp \
  --image "$IMAGE" \
  --public \
  --platform cpu-d3 \
  --preset 4vcpu-16gb \
  --container-port 8000 \
  --disk-size 100Gi \
  --subnet-id "$NEBIUS_SUBNET_ID" \
  --auth token \
  --volume "$VINA_VOLUME"
```

<!-- /factory:cli -->

## Cost and cleanup

The regular four-vCPU default is intended for a retained low-cost API. Use
preemptible capacity for disposable testing if interruption is acceptable. Stop
or delete the endpoint when it is no longer needed; compute, disk, and attached
storage continue to accrue charges while provisioned.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| Custom input is rejected | Supply valid bounded PDBQT text plus explicit `center` and `size`. |
| Docking is slow | Reduce box size, exhaustiveness, poses, or batch size; then measure before increasing CPU. |
| Score differs from AutoDock-GPU | The engines use different scoring semantics; do not compare raw scores directly. |
| Results disappear after restart | Attach Object Storage or Shared Filesystem at `/mnt/hcls`. |
| REST works but MCP returns 401 | Use the same Serverless endpoint token for `/mcp`. |
