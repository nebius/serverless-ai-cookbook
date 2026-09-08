# syntax=docker/dockerfile:1.7
ARG LIBRECHAT_BASE=cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/ba:librechat-0.2.7-20260908@sha256:1eaa9a5e7dc7e7a141d6f452f46e5547646a7c6113e610348511f801e7b185d1
FROM ${LIBRECHAT_BASE}

ARG HCLS_IMAGE_REVISION=unknown
LABEL org.opencontainers.image.title="Nebius HCLS LibreChat Workbench" \
      org.opencontainers.image.source="https://github.com/nebius/serverless-ai-cookbook" \
      org.opencontainers.image.revision="${HCLS_IMAGE_REVISION}" \
      org.opencontainers.image.licenses="MIT"

USER root
COPY templates/hcls-librechat/render-config.mjs /opt/hcls-librechat/render-config.mjs
COPY templates/hcls-librechat/seed-workbench.js /app/seed-hcls-workbench.js
COPY templates/hcls-librechat/entrypoint.sh /usr/local/bin/hcls-librechat-entrypoint
RUN chmod 0755 /usr/local/bin/hcls-librechat-entrypoint \
 && mkdir -p /data/db /data/hcls-librechat /app/uploads /app/logs \
 && chown -R node:node /data /app/uploads /app/logs \
 && chmod 0700 /data/hcls-librechat \
 && rm -f /usr/local/bin/npm /usr/local/bin/npx \
 && rm -rf /usr/local/lib/node_modules/npm

ENV HOST=0.0.0.0 \
    PORT=3080 \
    NODE_ENV=production \
    MONGO_URI=mongodb://127.0.0.1:27017/LibreChat \
    CONFIG_PATH=/data/hcls-librechat/librechat.yaml \
    ALLOW_REGISTRATION=true \
    ALLOW_EMAIL_LOGIN=true \
    ALLOW_UNVERIFIED_EMAIL_LOGIN=true \
    ALLOW_PASSWORD_RESET=false \
    LOG_TO_FILE=false \
    SEARCH=false \
    SCHEDULES_SINGLE_PROCESS=true \
    ENDPOINTS=agents,custom \
    GROMACS_MCP_URL=https://port8000-c2k6fvd25z9max9.tunnel.applications.eu-north1.nebius.cloud/mcp

EXPOSE 3080
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=5 \
  CMD ["wget", "--no-verbose", "--tries=1", "--spider", "http://127.0.0.1:3080/health"]
USER node
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/hcls-librechat-entrypoint"]
