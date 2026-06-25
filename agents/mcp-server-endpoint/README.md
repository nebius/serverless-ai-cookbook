---
title: MCP Server on Serverless Endpoint
category: agents
type: endpoint
runtime: cpu
frameworks:
  - fastapi
  - mcp
  - uvicorn
keywords:
  - mcp
  - model-context-protocol
  - serverless
  - embeddings
  - tokenfactory
difficulty: intermediate
---

# MCP Server on Serverless Endpoint

Run an MCP tool server as a CPU endpoint on Nebius Serverless.

## What this example does

Deploys a FastAPI server that speaks the Model Context Protocol over HTTP.
It exposes an `embed` tool backed by Nebius TokenFactory (Qwen3-Embedding-8B).

A local bridge script connects any MCP client to the remote endpoint over stdio.

### Why this is useful

Your tools run in the cloud, not on your machine.
The endpoint starts in seconds and costs nothing when idle.

### Requirements

- Nebius CLI installed and configured
- A Nebius container registry and a push token
- A Nebius TokenFactory API key
- Docker (to build the image)
- Python 3.12 (for the local bridge)

### Runtime / compute

- platform: `cpu-d3`
- preset: `2vcpu-8gb`
- estimated cost: $0.14 per hour

## Run

### 1. Set variables

```bash
export NEBIUS_API_KEY="your-tokenfactory-key"
export REGISTRY="cr.eu-north1.nebius.cloud/your-registry"
export SUBNET_ID=$(nebius vpc subnet list --format jsonpath='{.items[0].metadata.id}')
```

### 2. Build and push the image

```bash
docker build -t $REGISTRY/mcp-server:latest .
docker push $REGISTRY/mcp-server:latest
```

### 3. Create the endpoint

```bash
nebius ai endpoint create \
  --name mcp-server \
  --image $REGISTRY/mcp-server:latest \
  --platform cpu-d3 \
  --preset 2vcpu-8gb \
  --public \
  --container-port 8000 \
  --subnet-id "$SUBNET_ID" \
  --env "NEBIUS_API_KEY=$NEBIUS_API_KEY"
```

### 4. Get the endpoint URL

```bash
export MCP_URL=$(nebius ai endpoint get-by-name --name mcp-server \
  --format json | jq -r '.status.public_endpoints[0]')
echo $MCP_URL
```

### 5. Run the local bridge

```bash
pip install httpx
python src/bridge.py "http://$MCP_URL"
```

The bridge reads JSON-RPC from stdin and forwards calls to the remote endpoint.

## Expected output

Health check:

```bash
curl http://$MCP_URL/health
```

```json
{"status":"ok"}
```

Tool list:

```bash
curl http://$MCP_URL/tools
```

```json
{"tools":[{"name":"embed","description":"Return embedding vector for a text input","inputSchema":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}}]}
```

Tool call:

```bash
curl -X POST http://$MCP_URL/call \
  -H "Content-Type: application/json" \
  -d '{"name":"embed","arguments":{"text":"hello world"}}'
```

```json
{"content":[{"type":"text","text":"[0.012, -0.034, 0.008, ...] ..."}]}
```

## How to adapt

- Add more tools to `TOOLS` in `src/server.py` and add matching branches in the `/call` handler
- Point at a different TokenFactory model by changing `MODEL`
- Add platform auth with `--auth token` when creating the endpoint for production use

## Troubleshooting

- Endpoint stays in STARTING: check logs with `nebius ai logs <endpoint-id>`
- Tool call returns 401: check that `NEBIUS_API_KEY` is set correctly in the endpoint env
- Bridge gets no response: confirm `MCP_URL` does not have a trailing slash

## Cleanup

```bash
nebius ai endpoint delete \
  $(nebius ai endpoint get-by-name --name mcp-server --format json | jq -r '.metadata.id')
```
