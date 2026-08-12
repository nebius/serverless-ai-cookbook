ARG OPENCLAW_IMAGE="ghcr.io/openclaw/openclaw:2026.7.1-2@sha256:8789721d2e9b24b780a1504b56deb4c6bd5c7dbf96a1dd117e7c45c2ed72c8ac"
FROM ${OPENCLAW_IMAGE}

ARG CLOUDFLARED_VERSION="2026.7.3"
ARG CLOUDFLARED_SHA256="9d71c677db00134c1bd4144b7783486b654ad281b1ea62b4972098d19f770f17"
ARG BIONEMO_TOOLKIT_COMMIT="23d483511e0b42221bdafd7259ff43c05220ee86"
ARG CODEX_VERSION="0.147.0"
ARG CLAUDE_CODE_VERSION="2.1.228"
ARG THREEDMOL_VERSION="2.5.5"

LABEL org.opencontainers.image.title="Nebius BioNeMo Agent Workbench" \
      org.opencontainers.image.description="Authenticated BioNeMo browser agent plus unauthenticated Codex and Claude Code CLIs with NVIDIA BioNeMo skills and MCP" \
      org.opencontainers.image.source="https://github.com/nebius/serverless-ai-cookbook/tree/main/life-science/bionemo-agent" \
      org.opencontainers.image.version="3.1.0" \
      org.opencontainers.image.licenses="Apache-2.0 AND CC-BY-4.0 AND BSD-3-Clause" \
      io.nebius.bionemo.toolkit.commit="${BIONEMO_TOOLKIT_COMMIT}" \
      io.nebius.openclaw.version="2026.7.1-2" \
      io.nebius.cloudflared.version="${CLOUDFLARED_VERSION}" \
      io.nebius.codex.version="${CODEX_VERSION}" \
      io.nebius.claude-code.version="${CLAUDE_CODE_VERSION}" \
      io.nebius.3dmol.version="${THREEDMOL_VERSION}"

USER root
RUN apt-get update \
    && apt-get install --only-upgrade --yes --no-install-recommends \
      libgnutls30=3.7.9-2+deb12u7 \
    && npm install --global --omit=dev \
      "@openai/codex@${CODEX_VERSION}" \
      "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
      "3dmol@${THREEDMOL_VERSION}" \
    && install -d -o node -g node -m 0700 /opt/bionemo/assets /opt/bionemo/licenses \
    && install -o node -g node -m 0400 /usr/local/lib/node_modules/3dmol/build/3Dmol-min.js /opt/bionemo/assets/3Dmol-min.js \
    && install -o node -g node -m 0400 /usr/local/lib/node_modules/3dmol/LICENSE /opt/bionemo/licenses/3dmol-LICENSE \
    && rm -rf /var/lib/apt/lists/* \
      /root/.npm \
      /usr/local/lib/node_modules/npm \
      /usr/local/lib/node_modules/3dmol \
      /usr/local/share/corepack \
      /app/node_modules/@vitest \
      /app/node_modules/vitest
ADD --chmod=0755 --checksum=sha256:${CLOUDFLARED_SHA256} \
  https://github.com/cloudflare/cloudflared/releases/download/${CLOUDFLARED_VERSION}/cloudflared-linux-amd64 \
  /usr/local/bin/cloudflared

COPY --chown=node:node openclaw-plugin /opt/bionemo/openclaw-plugin
COPY --chown=node:node config /opt/bionemo/config
COPY --chown=node:node runtime /opt/bionemo/runtime
COPY --chmod=0755 runtime/bionemo-agent /usr/local/bin/bionemo-agent
COPY --chown=node:node workspace /workspace/agent
COPY --chown=node:node vendor /opt/bionemo/vendor

RUN install -d -o node -g node -m 0700 \
      /workspace/agent/artifacts /workspace/state /home/node/.claude/skills \
    && install -d -o root -g root -m 0755 /etc/codex/skills \
    && cp -a /opt/bionemo/vendor/bionemo-agent-toolkit/plugins/bionemo-agent-toolkit/skills/. /etc/codex/skills/ \
    && cp -a /opt/bionemo/vendor/bionemo-agent-toolkit/plugins/bionemo-agent-toolkit/skills/. /home/node/.claude/skills/ \
    && chown -R node:node /home/node/.claude \
    && chmod -R a-w /etc/codex/skills /home/node/.claude/skills \
    && chmod -R go-rwx /opt/bionemo /workspace/agent

ENV PORT=18789 \
    OPENCLAW_GATEWAY_PORT=18789 \
    OPENCLAW_STATE_DIR=/workspace/state \
    OPENCLAW_CONFIG_PATH=/workspace/state/openclaw.json \
    BIONEMO_CONFIG_TEMPLATE=/opt/bionemo/config/openclaw.template.json \
    BIONEMO_ARTIFACT_ROOT=/workspace/agent/artifacts \
    BIONEMO_3DMOL_PATH=/opt/bionemo/assets/3Dmol-min.js \
    BIONEMO_VENDOR_ROOT=/opt/bionemo/vendor/bionemo-agent-toolkit \
    BIONEMO_MCP_URL=https://api.cerebrium.ai/v4/p-12ff482a/clawbio-models-mcp-public/mcp \
    BIONEMO_ENABLE_HTTPS_TUNNEL=true \
    BIONEMO_REQUIRE_DEVICE_PAIRING=false \
    DISABLE_UPDATES=1 \
    DISABLE_AUTOUPDATER=1 \
    NODE_ENV=production

WORKDIR /workspace/agent
USER node
EXPOSE 18789
HEALTHCHECK --interval=15s --timeout=5s --start-period=45s --retries=4 CMD ["node", "/opt/bionemo/runtime/healthcheck.mjs"]
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/bionemo-agent"]
CMD ["openclaw"]
