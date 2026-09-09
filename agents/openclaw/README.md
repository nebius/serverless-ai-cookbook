---
title: OpenClaw AI Gateway on Serverless Endpoint
category: agents
type: endpoint
runtime: cpu
frameworks:
  - openclaw
keywords:
  - ai-gateway
  - openai-compatible
  - tokenfactory
  - cpu-endpoint
difficulty: intermediate
---

# Running OpenClaw Gateway on Nebius Serverless

This tutorial shows how to deploy [OpenClaw](https://github.com/openclaw/openclaw) — an open-source AI gateway — as a serverless CPU endpoint on Nebius AI, connected to TokenFactory model inference.

No GPU required. You pay only when the gateway is active.

> **This is a demo setup, not production-ready.** The endpoint is created without Nebius-level authentication (`--auth`), meaning anyone with the IP can reach it. See [Security considerations](#security-considerations) below.

## How it works

```
Your Browser
    │  HTTPS (via cloudflared)
    ▼
Nebius Serverless CPU Endpoint
OpenClaw Gateway
    │  OpenAI-compatible API
    ▼
Nebius TokenFactory
(zai-org/GLM-5 or any supported model)
```

**Nebius Serverless CPU Endpoint** runs the OpenClaw gateway process inside a container. It handles routing, authentication, and serves the web UI — without any GPU resources.

**TokenFactory** provides model inference via an OpenAI-compatible API. OpenClaw forwards requests to it and returns responses.

**cloudflared** creates a temporary HTTPS tunnel to your endpoint. This is required because OpenClaw's UI uses WebCrypto, which browsers only allow in secure contexts (HTTPS or localhost).

---

## Prerequisites

- [Nebius CLI](https://docs.nebius.com/cli/) installed and configured for your project
- `jq` installed — `brew install jq` on macOS, `apt install jq` on Ubuntu
- `cloudflared` installed — `brew install cloudflared` on macOS
- A Nebius TokenFactory API key

---

## Step 1 — Set up variables

```bash
# Your TokenFactory API key from the Nebius console
export NEBIUS_API_KEY="your-tokenfactory-key"

# Generate a random token to protect your gateway
export AUTH_TOKEN=$(openssl rand -hex 32)

# Fetch your project's subnet ID automatically
export SUBNET_ID=$(nebius vpc subnet list --format jsonpath='{.items[0].metadata.id}')

# Verify
echo "AUTH_TOKEN=$AUTH_TOKEN"
echo "SUBNET_ID=$SUBNET_ID"
```

> **Save your AUTH_TOKEN** — you'll need it to connect to the UI and make API requests.

---

## Step 2 — Generate the OpenClaw config

OpenClaw reads its configuration from `~/.openclaw/openclaw.json`. Since we're running in a container, we encode the config as base64 and inject it at startup.

```bash
OPENCLAW_CONFIG=$(cat <<EOF
{
  "gateway": {
    "mode": "local",
    "bind": "lan",
    "controlUi": {
      "dangerouslyAllowHostHeaderOriginFallback": true,
      "dangerouslyDisableDeviceAuth": true
    },
    "auth": {
      "mode": "token",
      "token": "${AUTH_TOKEN}"
    },
    "http": {
      "endpoints": {
        "chatCompletions": { "enabled": true }
      }
    }
  },
  "models": {
    "providers": {
      "tokenfactory": {
        "baseUrl": "https://api.tokenfactory.us-central1.nebius.com/v1",
        "apiKey": "${NEBIUS_API_KEY}",
        "api": "openai-completions",
        "models": [
          {
            "id": "zai-org/GLM-5",
            "name": "GLM-5"
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "tokenfactory/zai-org/GLM-5"
      }
    }
  }
}
EOF
)

OPENCLAW_CONFIG_B64=$(echo "$OPENCLAW_CONFIG" | base64 -w 0)
```

A few notes on the config flags:
- `bind: lan` — makes the gateway listen on `0.0.0.0` inside the container, required for external traffic
- `dangerouslyDisableDeviceAuth` — disables the device pairing flow, which requires shell access to complete and is not possible in serverless containers
- `dangerouslyAllowHostHeaderOriginFallback` — allows the UI to work behind a reverse proxy where the Host header differs from the origin
- `chatCompletions: enabled` — exposes the `/v1/chat/completions` HTTP endpoint so you can call the gateway with `curl` or any OpenAI-compatible client
- Auth is still enforced via `AUTH_TOKEN` — anyone connecting must provide it

---

## Step 3 — Create the endpoint

```bash
nebius ai endpoint create \
  --name demo-openclaw-cpu \
  --image ghcr.io/openclaw/openclaw:latest \
  --container-command bash \
  --args "-lc 'mkdir -p /home/node/.openclaw && echo ${OPENCLAW_CONFIG_B64} | base64 -d > /home/node/.openclaw/openclaw.json && cd /app && node dist/index.js gateway run --port 18789 --bind lan --allow-unconfigured'" \
  --platform cpu-d3 \
  --preset 8vcpu-32gb \
  --public \
  --container-port 18789 \
  --subnet-id "$SUBNET_ID" \
  --env "OPENCLAW_GATEWAY_TOKEN=$AUTH_TOKEN"
```

The endpoint will take a few minutes to start while the container image is pulled.

---

## Step 4 — Wait for Running status

```bash
nebius ai endpoint get-by-name --name demo-openclaw-cpu --format json | jq '.status.state'
```

Repeat until you see `"RUNNING"`.

---

## Step 5 — Get the endpoint IP

```bash
export CPU_IP=$(nebius ai endpoint get-by-name --name demo-openclaw-cpu \
  --format json | jq -r '.status.public_endpoints[0]')
echo $CPU_IP
```

---

## Step 6 — Open an HTTPS tunnel

OpenClaw's UI requires HTTPS. Use cloudflared to get a free temporary public URL:

```bash
cloudflared tunnel --url http://$CPU_IP
```

You'll see something like:

```
https://head-longest-tomorrow-program.trycloudflare.com
```

Open that URL in your browser.

---

## Step 7 — Connect to the dashboard

In the OpenClaw UI:
1. **WebSocket URL** — should be pre-filled with the cloudflared `wss://` URL
2. **Gateway Token** — paste your `$AUTH_TOKEN`
3. Click **Connect**

You should land on the OpenClaw dashboard with GLM-5 available as the active model.

---

## Test via API

OpenClaw also exposes an OpenAI-compatible API endpoint, so you can use it directly from any OpenAI client:

```bash
curl -sS "http://$CPU_IP/v1/chat/completions" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "tokenfactory/zai-org/GLM-5",
    "messages": [{"role": "user", "content": "Hello from Nebius serverless!"}]
  }' | jq -r '.choices[0].message.content'
```

---

## Cleanup

Delete the endpoint when you're done to avoid charges:

```bash
nebius ai endpoint delete \
  $(nebius ai endpoint get-by-name --name demo-openclaw-cpu --format json | jq -r '.metadata.id')
```

---

## Connecting to an existing gateway

If someone has already deployed the gateway and wants to share access:

**They send you:**
- Gateway IP and port (e.g. `195.242.11.58:18789`)
- `AUTH_TOKEN`

**You do:**

1. Install cloudflared:
   ```bash
   # macOS
   brew install cloudflared

   # Linux
   curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared && chmod +x cloudflared
   ```

2. Open a tunnel to their gateway:
   ```bash
   cloudflared tunnel --url http://195.242.11.58:18789
   ```

3. Open the `https://xxxx.trycloudflare.com` URL in your browser, paste the token, click **Connect**.

---

## Security considerations

This tutorial creates a **public endpoint without Nebius-level authentication** (`--public` and no `--auth` flag). That means anyone who discovers the endpoint IP can send requests to it. The only protection is the OpenClaw `AUTH_TOKEN`.

For production deployments, you should add Nebius endpoint authentication by passing `--auth` when creating the endpoint. This requires callers to present a valid token before traffic even reaches the container.

**What this means in practice:**

- **Demo / personal use** — the current setup is fine. The `AUTH_TOKEN` prevents unauthorized access at the application level, and you can delete the endpoint when you're done.
- **Production** — do not expose the endpoint publicly without Nebius-level auth. Options include:
  - Add `--auth` to the `nebius ai endpoint create` command to enforce authentication at the platform level
  - Put the endpoint behind a reverse proxy or API gateway that handles authentication
  - Run the endpoint in a private subnet and access it only through a VPN or tunnel

**In any case:** keep your tokens secret. If either is compromised, rotate it immediately and redeploy.

---

## What's next

- **Add a GPU endpoint** — deploy a custom model (e.g. Qwen2.5) on a Nebius GPU endpoint and point OpenClaw at it as a second provider
- **Add more models** — extend the `models.providers.tokenfactory.models` array with any TokenFactory-supported model
- **Persistent storage** — mount a volume to preserve OpenClaw workspace and chat history across restarts
