# syntax=docker/dockerfile:1.7
ARG LIBRECHAT_BASE=cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/ba:librechat-0.2.7-20260908@sha256:1eaa9a5e7dc7e7a141d6f452f46e5547646a7c6113e610348511f801e7b185d1
FROM ${LIBRECHAT_BASE} AS scientific-client
USER root
COPY templates/hcls-librechat/ScientificLanding.tsx /app/client/src/components/Chat/Landing.tsx
COPY templates/hcls-librechat/PoweredByFooter.tsx /app/client/src/components/Chat/Footer.tsx
COPY templates/hcls-librechat/patch-client.mjs /tmp/patch-client.mjs
RUN node /tmp/patch-client.mjs
WORKDIR /app/client
RUN NODE_ENV=production NODE_OPTIONS=--max-old-space-size=8192 /app/node_modules/.bin/vite build

FROM ${LIBRECHAT_BASE}

ARG HCLS_IMAGE_REVISION=unknown
LABEL org.opencontainers.image.title="Nebius Scientific AI Agent" \
      org.opencontainers.image.source="https://github.com/nebius/serverless-ai-cookbook" \
      org.opencontainers.image.revision="${HCLS_IMAGE_REVISION}" \
      org.opencontainers.image.licenses="MIT"

USER root
COPY --from=scientific-client /app/client/dist /app/client/dist
COPY templates/hcls-librechat/render-config.mjs /opt/hcls-librechat/render-config.mjs
COPY templates/hcls-librechat/scientific-tool-options.cjs /opt/hcls-librechat/scientific-tool-options.cjs
COPY templates/hcls-librechat/patch-server.mjs /opt/hcls-librechat/patch-server.mjs
COPY templates/hcls-librechat/tavily-mcp.mjs /opt/bionemo/tavily-mcp.mjs
RUN node /opt/hcls-librechat/patch-server.mjs
COPY templates/hcls-librechat/seed-workbench.js /app/seed-hcls-workbench.js
COPY life-science/bionemo-librechat/scientific-agent-instructions.md /app/scientific-agent-instructions.md
COPY templates/hcls-librechat/entrypoint.sh /usr/local/bin/hcls-librechat-entrypoint
COPY templates/hcls-librechat/brand-client.mjs /opt/hcls-librechat/brand-client.mjs
COPY templates/hcls-librechat/seed-user.js /app/seed-user.js
# Overlay the typed-contract skills maintained in the workbench directory and
# drop the stale pre-adaptation skill directories from the base image.
COPY life-science/bionemo-librechat/skills/ /app/skill/
RUN cd /app/skill && rm -rf boltz2-nim openfold2-nim openfold3-nim diffdock-nim \
      genmol-nim molmim-nim msa-search-nim evo2-nim proteinmpnn-nim \
      rfdiffusion-nim bionemo-workbench-tutorials
COPY templates/hcls-librechat/assets/nebius-logo.svg /app/client/dist/assets/logo.svg
RUN chmod 0755 /usr/local/bin/hcls-librechat-entrypoint \
 && node /opt/hcls-librechat/brand-client.mjs /app/client/dist \
 && mkdir -p /data/db /data/hcls-librechat /app/uploads /app/logs \
 && chown -R node:node /data /app/uploads /app/logs \
 && chmod 0700 /data/hcls-librechat \
 && rm -f /usr/local/bin/npm /usr/local/bin/npx \
 && rm -rf /usr/local/lib/node_modules/npm

ENV HOST=0.0.0.0 \
    PORT=3080 \
    NODE_ENV=production \
    APP_TITLE="Nebius Scientific AI Agent" \
    MONGO_URI=mongodb://127.0.0.1:27017/LibreChat \
    CONFIG_PATH=/data/hcls-librechat/librechat.yaml \
    ALLOW_REGISTRATION=true \
    ALLOW_EMAIL_LOGIN=true \
    ALLOW_UNVERIFIED_EMAIL_LOGIN=true \
    ALLOW_PASSWORD_RESET=false \
    LOG_TO_FILE=false \
    SEARCH=false \
    SCHEDULES_SINGLE_PROCESS=true \
    ENDPOINTS=agents,custom,openAI,anthropic \
    OPENAI_API_KEY=user_provided \
    ANTHROPIC_API_KEY=user_provided \
    SCIENTIFIC_MODELS_API_BASE_URL=https://89.169.99.188/v1 \
    SCIENTIFIC_MODELS_MCP_URL=https://89.169.99.188/mcp

EXPOSE 3080
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=5 \
  CMD ["wget", "--no-verbose", "--tries=1", "--spider", "http://127.0.0.1:3080/health"]
USER node
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/hcls-librechat-entrypoint"]
