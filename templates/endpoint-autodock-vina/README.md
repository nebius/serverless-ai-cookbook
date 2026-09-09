# AutoDock Vina REST + MCP

<!-- markdownlint-disable MD013 MD033 -->

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fhcls%2Fautodock-vina-api%3A20260909-rest-mcp&amp;targetPort=8000&amp;platform=cpu-d3&amp;preset=4vcpu-16gb&amp;diskSize=100GiB&amp;preemptible=false&amp;auth=true&amp;volumeMountPath=%2Fmnt%2Fhcls&amp;volumeSize=32"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Run low-cost AutoDock Vina redocking and small docking workloads through REST or MCP. The endpoint uses CPU intentionally, exposes a bounded asynchronous API, and persists results to Object Storage or Shared Filesystem.

**License:** [Apache-2.0](https://github.com/ccsb-scripps/AutoDock-Vina/blob/develop/LICENSE) · **Engine:** [AutoDock Vina 1.2.7](https://github.com/ccsb-scripps/AutoDock-Vina)

<!-- /factory:intro -->

---

title: AutoDock Vina REST + MCP
category: life-sciences
type: endpoint
runtime: cpu-d3
frameworks: [autodock-vina, fastapi, mcp]
keywords: [molecular-docking, virtual-screening, cpu, rest, mcp, agent]
difficulty: intermediate

---

## What you get

- A bounded asynchronous Vina API on port 8000 with `/docs`.
- A Streamable HTTP MCP server at `/mcp`.
- Shared REST/MCP queue, run IDs, state, and artifact hashes.
- A bundled public 1IEP/STI redocking smoke and custom PDBQT inputs.
- Persistent runs under `/mnt/hcls/autodock-vina/runs/<run-id>`.

This template intentionally uses `cpu-d3`: AutoDock Vina is multithreaded CPU
software and is distinct from AutoDock-GPU, which implements AutoDock4 scoring.
Their numerical scores are not interchangeable.

The image pins Vina 1.2.7 and bundles official example assets from upstream
commit `8eb40404f4f45608acb3b01427587ac049f27c1f`. No NGC key or model-download
credential is required.

## Create the endpoint

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
artifact verification:

```bash
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

Supply `receptor_pdbqt` and/or `ligand_pdbqt` as bounded PDBQT text. Any custom
structure requires explicit three-number `center` and `size` fields. The endpoint
does not infer a binding site, prepare arbitrary molecular formats, accept shell
commands, or fetch URLs.

## Expected output

A successful run produces ranked `poses.pdbqt`, `scores.csv`, a docking summary,
input copies, and SHA-256 metadata. Results report Vina version, box, search
parameters, and energy components in kcal/mol. The public 1IEP/STI acceptance run
on the earlier REST image produced a best Vina affinity of approximately
`-13.263 kcal/mol`; use it as a plumbing sanity check, not a universal score.

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

```bash
export NEBIUS_PROJECT_ID='project-...'
export NEBIUS_SUBNET_ID='vpcsubnet-...'
export VINA_VOLUME='computefilesystem-<id>:/mnt/hcls:rw'
# Or: s3://<bucket>:/mnt/hcls:rw:<aws-profile>@<secret-selector>

nebius ai endpoint create \
  --parent-id "$NEBIUS_PROJECT_ID" \
  --name autodock-vina-rest-mcp \
  --image cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/hcls/autodock-vina-api:20260909-rest-mcp \
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
