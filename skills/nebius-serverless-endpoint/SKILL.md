---
name: nebius-serverless-endpoint
description: Deploy, start, stop, update, and call HTTP endpoints on Nebius Serverless AI via `nebius ai endpoint` — the surface for serving models (vLLM, TGI, Triton, custom inference). Use when the user asks to serve, deploy, host, or expose a model as an HTTP service, add auth to a model endpoint, stop/start a running endpoint, or update a deployed endpoint's image/env/config.
allowed-tools: Bash(nebius *), Bash(curl *)
---

# Nebius Serverless AI — Endpoints

An **endpoint** is a long-running HTTP service backed by a single-replica container on a GPU or CPU VM. Unlike jobs, endpoints have **no timeout** — they run until `stop` or `delete`. Billed per-second while `RUNNING`.

Best for: model serving, batch inference behind an API, internal microservices. **Not suitable for**: bursty traffic needing autoscale (single replica), scale-to-zero (no warm-standby), multi-region failover.

Companion skills: `nebius-serverless-job`, `nebius-container-registry`, `nebius-serverless-platform`, `nebius-serverless-recipes`.

## Lifecycle

```
create → PROVISIONING → STARTING → RUNNING ⇄ STOPPED → (deleted)
                                         ↘ ERROR
```

- `stop` deallocates the VM but preserves the spec + ID. Billing stops.
- `start` goes back through `PROVISIONING → STARTING → RUNNING`. Cold start can take minutes (image pull + GPU attach).
- No per-request scale-to-zero. No autoscaling.

## Critical caveat: no in-place update

**`nebius ai endpoint update` does not exist.** The proto (`EndpointService`) exposes only `Get/GetByName/List/Create/Delete/Start/Stop`. To change the image, env, platform, preset, port, or auth, you must `delete` + `create`. The endpoint ID and public IP change. Anything caching the URL must be refreshed.

`(proto-only confirmation — https://github.com/nebius/api/blob/main/nebius/ai/v1/endpoint_service.proto)`

## Creating an endpoint

```bash
nebius ai endpoint create \
  --name my-llm \
  --image cr.eu-north1.nebius.cloud/<reg>/vllm:v1 \
  --platform gpu-h100-sxm \
  --preset 1gpu-16vcpu-200gb \
  --container-port 8000 \
  --public \
  --auth token \
  --token "$(openssl rand -hex 32)" \
  --env MODEL_ID=/models/ft \
  --volume models-bucket:/models:ro \
  --subnet-id vpcsubnet-<id>
```

### Endpoint-specific flags

Full reference: https://docs.nebius.com/cli/reference/ai/endpoint/create

| Flag | Purpose | Notes |
|---|---|---|
| `--container-port` | Ports to expose | Repeatable. **Auth only works when exactly one HTTP port is exposed.** |
| `--auth {none,token}` | Auth mode | Default `none` |
| `--token <string>` | Inline bearer token | Mutually exclusive with `--token-secret` |
| `--token-secret <secret-version-id>` | Token from MysteryBox | Payload must contain `AUTH_TOKEN` |
| `--public` | Assign a public IP | Otherwise private-only (VPC-internal) |
| `--ssh-key` | Authorize SSH keys | Required at create for `endpoint ssh` |

Shared with `job create` (see `nebius-serverless-job`): `--image`, `--platform`, `--preset`, `--subnet-id`, `--env`, `--env-secret`, `--volume`, `--disk-size`, `--shm-size`, `--registry-secret`, `--preemptible`, `--container-command`, `--args`, `--working-dir`, `--dry-run`.

**Not applicable to endpoints**: `--timeout`, `--restart-policy`, `--restart-attempts`.

## Auth modes

| Mode | Who can call | How caller authenticates |
|---|---|---|
| `none` (default) | Anyone reaching the IP | No header |
| `token` | Anyone with the token | `Authorization: Bearer <token>` |
| (IAM not supported) | — | — |

IAM guards the *management plane* (who can `create`/`stop` via the CLI), **not ingress**. To gate ingress by IAM, front the endpoint with your own API gateway.

**Prefer `--token-secret` over `--token`** for production so the token never appears in command history or logs.

## Fetching the URL

Endpoints have no DNS name — use the IP directly.

```bash
IP=$(nebius ai endpoint get-by-name --name my-llm \
  --format jsonpath='{.status.public_endpoints[0]}')
curl -H "Authorization: Bearer $TOKEN" http://$IP:8000/v1/chat/completions -d @req.json
```

For private endpoints: `{.status.private_endpoints[0]}`.

## Stop / start / delete

```bash
nebius ai endpoint stop   <endpoint-id>   # deallocate, keep spec
nebius ai endpoint start  <endpoint-id>   # reprovision
nebius ai endpoint delete <endpoint-id>   # remove entirely
```

To change anything about a running endpoint, `delete` + `create` with the same `--name`.

## Logs

Same semantics as jobs — **`--since` defaults to 1 hour**. For post-hoc inspection of a stopped endpoint:

```bash
nebius ai endpoint logs <endpoint-id> --since 24h
```

For live tailing:

```bash
nebius ai endpoint logs <endpoint-id> --follow
```

## SSH

```bash
nebius ai endpoint ssh <endpoint-id>
```

Only works while `RUNNING` and only if `--ssh-key` was passed at `create`.

## Quick serving recipe (vLLM behind token auth)

```bash
TOKEN=$(openssl rand -hex 32)
SUBNET=$(nebius vpc subnet get-by-name --name default-subnet --format jsonpath='{.metadata.id}')

nebius ai endpoint create \
  --name my-llm \
  --image vllm/vllm-openai:v0.6.0 \
  --platform gpu-h100-sxm --preset 1gpu-16vcpu-200gb \
  --container-port 8000 --public --auth token --token "$TOKEN" \
  --args "--model,meta-llama/Llama-3.1-8B-Instruct" \
  --env HUGGING_FACE_HUB_TOKEN_FROM_SECRET=true \
  --env-secret HUGGING_FACE_HUB_TOKEN=<mb-secret-ver-id> \
  --subnet-id "$SUBNET"

# Wait for RUNNING:
until nebius ai endpoint get my-llm 2>/dev/null | grep -q '^  State:   RUNNING'; do sleep 15; done

IP=$(nebius ai endpoint get-by-name --name my-llm --format jsonpath='{.status.public_endpoints[0]}')
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://$IP:8000/v1/chat/completions" \
  -d '{"model":"meta-llama/Llama-3.1-8B-Instruct","messages":[{"role":"user","content":"hi"}]}'
```

## Horizontal scale / A-B testing patterns

Since endpoints don't autoscale and can't be updated in place:

- **A/B testing**: create two endpoints (`my-llm-a`, `my-llm-b`) with different images. Split traffic in your client or gateway.
- **Rolling update**: create `my-llm-v2` alongside `my-llm-v1`. Wait for `RUNNING`. Switch the caller's URL. Delete v1.
- **Horizontal scale-out**: create N endpoints, front with your own load balancer (e.g. a tiny nginx endpoint or Managed Kubernetes ingress).

If you genuinely need autoscaling or scale-to-zero, **Serverless AI is the wrong product** — use Managed Kubernetes with KServe/Knative or an ingress autoscaler.

## Common failure modes & fixes

| Symptom | Cause | Fix |
|---|---|---|
| `ERROR` state right after create | Image pull timeout (image too large) | Slim the image, move weights to a `--volume` mount |
| 401 / 403 calling the endpoint | Missing or wrong `Authorization: Bearer` | Check `--auth` mode and the token source |
| "Can't change env / image" | No in-place update | `delete` + `create` (IP changes) |
| Endpoint works in VPC but not publicly | Created without `--public` | Recreate with `--public` |
| Auth unexpectedly ignored | Multiple container ports exposed | Expose exactly one HTTP port when using `--auth token` |

## Reference

- Overview: https://docs.nebius.com/serverless/overview
- Endpoints guide: https://docs.nebius.com/serverless/endpoints
- CLI: https://docs.nebius.com/cli/reference/ai/endpoint/
- `endpoint create`: https://docs.nebius.com/cli/reference/ai/endpoint/create
- Proto: https://github.com/nebius/api/blob/main/nebius/ai/v1/endpoint_service.proto
