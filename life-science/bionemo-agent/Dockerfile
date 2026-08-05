ARG OPENCLAW_IMAGE="ghcr.io/openclaw/openclaw:2026.7.1-2@sha256:8789721d2e9b24b780a1504b56deb4c6bd5c7dbf96a1dd117e7c45c2ed72c8ac"
FROM ${OPENCLAW_IMAGE}

ARG CLOUDFLARED_VERSION="2026.7.3"
ARG CLOUDFLARED_SHA256="9d71c677db00134c1bd4144b7783486b654ad281b1ea62b4972098d19f770f17"
ARG BIONEMO_TOOLKIT_COMMIT="38a63ada35f57770fe49e633d3461d4110746b26"

LABEL org.opencontainers.image.title="Nebius BioNeMo Research Agent" \
      org.opencontainers.image.description="Authenticated OpenClaw browser agent with bounded NVIDIA-hosted BioNeMo NIM adapters" \
      org.opencontainers.image.source="https://github.com/nebius/serverless-ai-cookbook/tree/main/life-science/bionemo-agent" \
      org.opencontainers.image.version="2.1.0" \
      org.opencontainers.image.licenses="Apache-2.0 AND CC-BY-4.0" \
      io.nebius.bionemo.toolkit.commit="${BIONEMO_TOOLKIT_COMMIT}" \
      io.nebius.openclaw.version="2026.7.1-2" \
      io.nebius.cloudflared.version="${CLOUDFLARED_VERSION}"

USER root
RUN apt-get update \
    && apt-get install --only-upgrade --yes --no-install-recommends \
      libgnutls30=3.7.9-2+deb12u7 \
    && rm -rf /var/lib/apt/lists/* \
      /usr/local/lib/node_modules/npm \
      /usr/local/share/corepack \
      /app/node_modules/@vitest \
      /app/node_modules/vitest
ADD --chmod=0755 --checksum=sha256:${CLOUDFLARED_SHA256} \
  https://github.com/cloudflare/cloudflared/releases/download/${CLOUDFLARED_VERSION}/cloudflared-linux-amd64 \
  /usr/local/bin/cloudflared

COPY --chown=node:node openclaw-plugin /opt/bionemo/openclaw-plugin
COPY --chown=node:node config /opt/bionemo/config
COPY --chown=node:node runtime /opt/bionemo/runtime
COPY --chown=node:node workspace /workspace/agent
COPY --chown=node:node vendor /opt/bionemo/vendor

RUN install -d -o node -g node -m 0700 /workspace/artifacts /workspace/state \
    && chmod -R go-rwx /opt/bionemo /workspace/agent

ENV PORT=18789 \
    OPENCLAW_GATEWAY_PORT=18789 \
    OPENCLAW_STATE_DIR=/workspace/state \
    OPENCLAW_CONFIG_PATH=/workspace/state/openclaw.json \
    BIONEMO_CONFIG_TEMPLATE=/opt/bionemo/config/openclaw.template.json \
    BIONEMO_ARTIFACT_ROOT=/workspace/artifacts \
    BIONEMO_VENDOR_ROOT=/opt/bionemo/vendor/bionemo-agent-toolkit \
    BIONEMO_ENABLE_HTTPS_TUNNEL=true \
    NODE_ENV=production

WORKDIR /workspace/agent
USER node
EXPOSE 18789
HEALTHCHECK --interval=15s --timeout=5s --start-period=45s --retries=4 CMD ["node", "/opt/bionemo/runtime/healthcheck.mjs"]
CMD ["node", "/opt/bionemo/runtime/launcher.mjs"]
