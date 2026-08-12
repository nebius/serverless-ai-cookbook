#!/usr/bin/env bash
set -euo pipefail

: "${IMAGE:?Set IMAGE to a unique Nebius registry version tag or immutable digest reference}"
: "${AUTH_TOKEN_SECRET:?Set AUTH_TOKEN_SECRET to a MysteryBox selector whose payload contains AUTH_TOKEN}"

if [[ -n "${NVIDIA_API_KEY_SECRET:-}" && -n "${NGC_API_KEY_SECRET:-}" ]]; then
  echo "Set only one of NVIDIA_API_KEY_SECRET or NGC_API_KEY_SECRET." >&2
  exit 2
fi

if [[ "$IMAGE" != cr.*.nebius.cloud/*@sha256:* && "$IMAGE" != cr.*.nebius.cloud/*:* ]]; then
  echo "IMAGE must be a Nebius Container Registry reference with a unique version tag or digest." >&2
  exit 2
fi

ENDPOINT_NAME="${ENDPOINT_NAME:-bionemo-agent-workbench-3}"
PLATFORM="${PLATFORM:-cpu-d3}"
PRESET="${PRESET:-4vcpu-16gb}"
DISK_SIZE="${DISK_SIZE:-30Gi}"
PROFILE="${PROFILE:-sandbox}"
BIONEMO_MCP_URL="${BIONEMO_MCP_URL:-https://api.cerebrium.ai/v4/p-12ff482a/clawbio-models-mcp-public/mcp}"
HTTPS_MODE="${BIONEMO_HTTPS_MODE:-cloudflare}"
DEVICE_PAIRING="${BIONEMO_REQUIRE_DEVICE_PAIRING:-false}"

if [[ "$HTTPS_MODE" != "cloudflare" && "$HTTPS_MODE" != "nebius" ]]; then
  echo "BIONEMO_HTTPS_MODE must be cloudflare or nebius for this Serverless deployment script." >&2
  exit 2
fi
if [[ "$HTTPS_MODE" == "nebius" && "$DEVICE_PAIRING" != "false" ]]; then
  echo "Native Nebius browser mode requires BIONEMO_REQUIRE_DEVICE_PAIRING=false for token-only event login." >&2
  exit 2
fi

CREATE_CMD=(
  nebius --profile "$PROFILE" ai endpoint create
  --name "$ENDPOINT_NAME"
  --image "$IMAGE"
  --platform "$PLATFORM"
  --preset "$PRESET"
  --disk-size "$DISK_SIZE"
  --container-port 18789
  --env-secret "AUTH_TOKEN=$AUTH_TOKEN_SECRET"
  --env "AGENT_PROVIDER=${AGENT_PROVIDER:-auto}"
  --env "BIONEMO_BACKEND=${BIONEMO_BACKEND:-auto}"
  --env "BIONEMO_MCP_URL=$BIONEMO_MCP_URL"
  --env "BIONEMO_HTTPS_MODE=$HTTPS_MODE"
  --env "BIONEMO_REQUIRE_DEVICE_PAIRING=$DEVICE_PAIRING"
)

if [[ "$HTTPS_MODE" == "cloudflare" ]]; then
  CREATE_CMD+=(--public --auth token --token-secret "$AUTH_TOKEN_SECRET" --env "BIONEMO_ENABLE_HTTPS_TUNNEL=true")
else
  # The managed HTTPS URL does not require a public VM IP. Serverless auth must
  # remain disabled because normal browser navigation cannot attach its Bearer
  # header; OpenClaw still requires the separately injected AUTH_TOKEN.
  CREATE_CMD+=(--env "BIONEMO_ENABLE_HTTPS_TUNNEL=false")
fi
if [[ -n "${BIONEMO_PUBLIC_ORIGIN:-}" ]]; then CREATE_CMD+=(--env "BIONEMO_PUBLIC_ORIGIN=$BIONEMO_PUBLIC_ORIGIN"); fi

if [[ -n "${NVIDIA_API_KEY_SECRET:-}" ]]; then
  CREATE_CMD+=(--env-secret "NVIDIA_API_KEY=$NVIDIA_API_KEY_SECRET")
elif [[ -n "${NGC_API_KEY_SECRET:-}" ]]; then
  CREATE_CMD+=(--env-secret "NGC_API_KEY=$NGC_API_KEY_SECRET")
fi
if [[ -n "${NEBIUS_API_KEY_SECRET:-}" ]]; then CREATE_CMD+=(--env-secret "NEBIUS_API_KEY=$NEBIUS_API_KEY_SECRET"); fi
if [[ -n "${OPENAI_API_KEY_SECRET:-}" ]]; then CREATE_CMD+=(--env-secret "OPENAI_API_KEY=$OPENAI_API_KEY_SECRET"); fi
if [[ -n "${ANTHROPIC_API_KEY_SECRET:-}" ]]; then CREATE_CMD+=(--env-secret "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY_SECRET"); fi
if [[ -n "${BIONEMO_MCP_API_KEY_SECRET:-}" ]]; then CREATE_CMD+=(--env-secret "BIONEMO_MCP_API_KEY=$BIONEMO_MCP_API_KEY_SECRET"); fi
if [[ -n "${TAVILY_API_KEY_SECRET:-}" ]]; then CREATE_CMD+=(--env-secret "TAVILY_API_KEY=$TAVILY_API_KEY_SECRET"); fi

if [[ -n "${PARENT_ID:-}" ]]; then CREATE_CMD+=(--parent-id "$PARENT_ID"); fi
if [[ -n "${SUBNET_ID:-}" ]]; then CREATE_CMD+=(--subnet-id "$SUBNET_ID"); fi
if [[ -n "${REGISTRY_SECRET:-}" ]]; then CREATE_CMD+=(--registry-secret "$REGISTRY_SECRET"); fi

echo "Creating task-owned regular CPU Serverless Endpoint '$ENDPOINT_NAME' in $HTTPS_MODE HTTPS mode from an immutable image."
"${CREATE_CMD[@]}"

if [[ "$HTTPS_MODE" == "cloudflare" ]]; then
  cat <<EOF

The endpoint starts a supervised Cloudflare quick tunnel and prints an HTTPS URL
to its logs. The URL never contains the gateway token.

Inspect the endpoint and logs:
  nebius --profile "$PROFILE" ai endpoint get-by-name --name "$ENDPOINT_NAME" --format json
  ENDPOINT_ID=\$(nebius --profile "$PROFILE" ai endpoint get-by-name --name "$ENDPOINT_NAME" --format jsonpath='{.metadata.id}')
  nebius --profile "$PROFILE" ai endpoint logs "\$ENDPOINT_ID" --tail 200 --timestamps

Open the logged https://*.trycloudflare.com URL from a clean browser and enter
the AUTH_TOKEN value. The direct Serverless IP remains protected by the same
MysteryBox AUTH_TOKEN through Serverless endpoint authentication.
EOF
else
  cat <<EOF

The endpoint uses the Nebius-managed HTTPS URL, with no Cloudflare tunnel, no
public VM IP, and no Serverless bearer-auth layer. OpenClaw still requires the
MysteryBox AUTH_TOKEN and verifies that browser Origin.host exactly matches the
managed request Host.

Inspect the endpoint and obtain its managed browser URL:
  ENDPOINT_ID=\$(nebius --profile "$PROFILE" ai endpoint get-by-name --name "$ENDPOINT_NAME" --format jsonpath='{.metadata.id}')
  BROWSER_URL=\$(nebius --profile "$PROFILE" ai endpoint get "\$ENDPOINT_ID" --format json | jq -r '.status.public_endpoints[] | select(startswith("https://"))' | head -1)

Open BROWSER_URL from a clean browser and enter the AUTH_TOKEN value in OpenClaw.
EOF
fi
