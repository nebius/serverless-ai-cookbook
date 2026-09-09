---
title: "SIPA OS MLL Agent Router"
category: agents
type: endpoint
runtime: cpu
frameworks: ["fastapi", "nebius-token-factory", "openai-sdk"]
keywords: ["multi-agent", "routing", "mental-health", "adhd", "neurodivergent", "mll"]
difficulty: intermediate
---

# SIPA OS MLL Agent Router on Nebius Serverless

A multi-layer routing agent (MLL) that detects the nature of an incoming message
and forwards it to the optimal [Nebius Token Factory](https://nebius.com/prices-ai-studio)
model — all running as a CPU-only Serverless Endpoint.

Built by a neurodivergent artist-architect to demonstrate how to build
adaptive AI routing for ADHD/BPD support use-cases.

## What this example does

- Accepts chat messages via HTTP POST
- Classifies intent: **crisis** / **code** / **research** / **writing** / **general**
- Routes to the best Token Factory model for each intent type
- Returns the response with model attribution metadata
- Runs on a CPU Serverless Endpoint (no GPU quota needed)

### Routing table

| Intent      | Model                                  | Why                       |
|-------------|----------------------------------------|---------------------------|
| crisis      | `NousResearch/Hermes-4-70B`            | Empathetic, careful tone  |
| code        | `Qwen/Qwen3-32B`                       | Strong coding reasoning   |
| research    | `deepseek-ai/DeepSeek-V4-Pro`          | Deep analytical reasoning |
| writing     | `openai/gpt-oss-120b`                  | Long-form quality         |
| general     | `nvidia/Nemotron-3-Super-120b-a12b`    | Fast, balanced            |

## Requirements

- [Nebius CLI](https://docs.nebius.com/cli/) installed and configured
- Nebius Token Factory API key (from [console.nebius.com](https://console.nebius.com))
- Docker (optional, for local testing)

## Step 1 — Set environment variables

```bash
export NEBIUS_API_KEY="your-token-factory-api-key"
export SUBNET_ID=$(nebius vpc subnet list --format jsonpath='{.items[0].metadata.id}')

echo "SUBNET_ID=$SUBNET_ID"
```

## Step 2 — Deploy the endpoint

```bash
nebius ai endpoint create \
  --name sipa-mll-router \
  --image ghcr.io/soulinpsyabstract/sipa-mll-router:latest \
  --platform cpu \
  --preset 4vcpu-8gb \
  --env NEBIUS_API_KEY="${NEBIUS_API_KEY}" \
  --port 8000 \
  --subnet-id "${SUBNET_ID}"
```

Get the endpoint URL and IP:

```bash
export ENDPOINT_ID=$(nebius ai endpoint get-by-name \
  --name sipa-mll-router \
  --format jsonpath='{.metadata.id}')

nebius ai endpoint get --id "${ENDPOINT_ID}" \
  --format jsonpath='{.status.target_group_status.load_balancers[0].ingress_addresses[0].external_address_spec.address}'
```

## Step 3 — Send a message

```bash
export ENDPOINT_URL="http://<endpoint-ip>:8000"

# General query
curl -s -X POST "${ENDPOINT_URL}/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Help me focus on my tasks today", "session_id": "test-1"}' | jq .

# Crisis detection
curl -s -X POST "${ENDPOINT_URL}/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "I feel overwhelmed and cannot cope", "session_id": "test-2"}' | jq .

# Code routing
curl -s -X POST "${ENDPOINT_URL}/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Write a Python function to debounce async events", "session_id": "test-3"}' | jq .
```

## Expected output

```json
{
  "session_id": "test-1",
  "model_used": "nvidia/Nemotron-3-Super-120b-a12b",
  "intent": "general",
  "response": "Breaking your day into focused blocks can really help...",
  "tokens_used": 187
}
```

## Local testing

```bash
docker build -t sipa-mll-router ./src
docker run -p 8000:8000 \
  -e NEBIUS_API_KEY="${NEBIUS_API_KEY}" \
  sipa-mll-router

curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Explain quantum entanglement simply"}' | jq .
```

## How to adapt

- **Add models**: extend `ROUTING_TABLE` in `src/main.py`
- **Tune routing**: adjust keyword lists in `classify_intent()`
- **Add memory**: integrate Nebius Object Storage for session history
- **Add auth**: use `--auth` flag on `nebius ai endpoint create`
- **Scale to GPU**: change `--platform cpu` to `--platform gpu-l40s-a` for local inference

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `401 Unauthorized` from Token Factory | Check `NEBIUS_API_KEY` env var |
| Endpoint stuck in `PROVISIONING` | Wait 2-3 min; CPU endpoints start in ~30s |
| Wrong model selected | Lower the `CRISIS_THRESHOLD` in `classify_intent()` |
| Timeout on long responses | Increase `--timeout` in endpoint config or use streaming |

## About SIPA OS

This router is a simplified version of [SIPA OS](https://ai.sipa-os.org) — a production
multi-agent AI system built for neurodivergent users. The full system routes across
345+ models with a 10-layer MLL stack, Crisis Rail, and RAG memory.

Built by [Aelin AquaSoul](https://github.com/soulinpsyabstract) · Soul In PsyAbstract LLC

