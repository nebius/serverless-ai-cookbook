# syntax=docker/dockerfile:1.7
ARG LIBRECHAT_BASE=cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/ba:librechat-0.2.7-20260908@sha256:1eaa9a5e7dc7e7a141d6f452f46e5547646a7c6113e610348511f801e7b185d1
FROM ${LIBRECHAT_BASE} AS scientific-client
USER root
COPY templates/hcls-librechat/ScientificLanding.tsx /app/client/src/components/Chat/Landing.tsx
COPY templates/hcls-librechat/PoweredByFooter.tsx /app/client/src/components/Chat/Footer.tsx
COPY templates/hcls-librechat/WorkspaceInlineCode.tsx /app/client/src/components/WorkspaceInlineCode.tsx
COPY templates/hcls-librechat/patch-client.mjs /tmp/patch-client.mjs
RUN node /tmp/patch-client.mjs
COPY templates/hcls-librechat/demos/Demos.tsx /app/client/src/components/ScientificDemos.tsx
COPY templates/hcls-librechat/demos/comparison.ts /app/client/src/components/scientific-comparison.ts
COPY templates/hcls-librechat/demos/run-display.ts /app/client/src/components/scientific-run-display.ts
COPY templates/hcls-librechat/demos/patch.mjs /tmp/patch-demos.mjs
RUN node /tmp/patch-demos.mjs client
WORKDIR /app/client
RUN NODE_ENV=production NODE_OPTIONS=--max-old-space-size=8192 /app/node_modules/.bin/vite build

FROM ${LIBRECHAT_BASE} AS aging-reference
USER root
COPY templates/hcls-librechat/prepare-aging-reference.py /tmp/prepare-aging-reference.py
RUN python3 -m venv /tmp/aging-reference-builder \
 && /tmp/aging-reference-builder/bin/pip install --no-cache-dir numpy==2.2.6 pandas==2.2.3 scikit-learn==1.7.2 \
 && /tmp/aging-reference-builder/bin/python /tmp/prepare-aging-reference.py --output /opt/aging-reference

FROM ${LIBRECHAT_BASE}

ARG HCLS_IMAGE_REVISION=unknown
LABEL org.opencontainers.image.title="Nebius Scientific AI Agent" \
      org.opencontainers.image.source="https://github.com/nebius/serverless-ai-cookbook" \
      org.opencontainers.image.revision="${HCLS_IMAGE_REVISION}" \
      org.opencontainers.image.licenses="MIT"

USER root
COPY --from=scientific-client /app/client/dist /app/client/dist
# zstd is the published scientific/LeRobot archive transport, not an optional
# notebook-only dependency. Keep it available after a fresh deployment.
RUN apt-get update && apt-get install -y --no-install-recommends zstd \
 && zstd --version \
 && rm -rf /var/lib/apt/lists/*
COPY templates/hcls-librechat/render-config.mjs /opt/hcls-librechat/render-config.mjs
COPY templates/hcls-librechat/scientific-tool-options.cjs /opt/hcls-librechat/scientific-tool-options.cjs
COPY templates/hcls-librechat/scientific-completion.cjs /opt/hcls-librechat/scientific-completion.cjs
COPY templates/hcls-librechat/scientific-workflow.py /opt/bionemo/scientific-workflow.py
COPY templates/hcls-librechat/scientific-context-audit.cjs /opt/hcls-librechat/scientific-context-audit.cjs
COPY templates/hcls-librechat/scientific-token-count.cjs /opt/hcls-librechat/scientific-token-count.cjs
COPY templates/hcls-librechat/patch-server.mjs /opt/hcls-librechat/patch-server.mjs
COPY templates/hcls-librechat/demos/service.cjs \
     templates/hcls-librechat/demos/analysis.cjs \
     templates/hcls-librechat/demos/worker.cjs \
     templates/hcls-librechat/demos/mcp.cjs \
     templates/hcls-librechat/demos/seed.cjs \
     templates/hcls-librechat/demos/patch.mjs \
     templates/hcls-librechat/demos/workshop-example.json /opt/hcls-librechat/demos/
COPY templates/hcls-librechat/demos/router.cjs /app/api/server/routes/scientific-demos.js
COPY templates/hcls-librechat/tavily-mcp.mjs /opt/bionemo/tavily-mcp.mjs
COPY templates/hcls-librechat/structure-mcp.py /opt/bionemo/structure-mcp.py
COPY templates/hcls-librechat/execution-mcp.py /opt/bionemo/execution-mcp.py
COPY templates/hcls-librechat/invoke-native.py /opt/bionemo/invoke-native.py
COPY templates/hcls-librechat/scientific_receipts.py /opt/bionemo/scientific_receipts.py
COPY templates/hcls-librechat/upload-artifact.py /opt/bionemo/upload-artifact.py
COPY templates/hcls-librechat/scripts/scientific-batch-acceptance.py /opt/bionemo/invoke-scientific-batch.py
COPY templates/hcls-librechat/structure-analysis.py /opt/bionemo/structure-analysis.py
COPY templates/hcls-librechat/molecule-analysis.py /opt/bionemo/molecule-analysis.py
COPY templates/hcls-librechat/report-assembly.py /opt/bionemo/report-assembly.py
COPY templates/hcls-librechat/aging-analysis.py /opt/bionemo/aging-analysis.py
COPY templates/hcls-librechat/scientific_study.py templates/hcls-librechat/scientific_study_schema.py templates/hcls-librechat/scientific_preparation.py templates/hcls-librechat/scientific_protein_preparation.py templates/hcls-librechat/scientific_clinical.py templates/hcls-librechat/scientific-study-worker.py /opt/bionemo/
COPY templates/hcls-librechat/scripts/qualification/evaluators.py /opt/bionemo/qualification_evaluators.py
COPY --from=aging-reference /opt/aging-reference /opt/bionemo/aging-reference
RUN python3 -m venv /opt/scientific-client \
 && /opt/scientific-client/bin/pip install --no-cache-dir mcp==2.2.0 httpx2==2.12.0 httpx==0.28.1 jsonschema==4.26.0 numpy==2.2.6 biopython==1.85 rdkit==2025.3.6 h5py==3.13.0 pyarrow==21.0.0 pandas==2.2.3
COPY life-science/bionemo-librechat/viewer-mcp.py /opt/bionemo/viewer-mcp.py
COPY life-science/bionemo-librechat/3dmol.js /opt/bionemo/3dmol.js
RUN node /opt/hcls-librechat/patch-server.mjs
RUN node /opt/hcls-librechat/demos/patch.mjs server \
 && command -v flock \
 && python3 -m venv /opt/clinical-client \
 && /opt/clinical-client/bin/pip install --no-cache-dir httpx==0.28.1
COPY templates/hcls-librechat/seed-workbench.js /app/seed-hcls-workbench.js
COPY life-science/bionemo-librechat/scientific-agent-instructions.md /app/scientific-agent-instructions.md
COPY templates/hcls-librechat/entrypoint.sh /usr/local/bin/hcls-librechat-entrypoint
COPY templates/hcls-librechat/brand-client.mjs /opt/hcls-librechat/brand-client.mjs
COPY templates/hcls-librechat/seed-user.js /app/seed-user.js
# Overlay the typed-contract skills maintained in the workbench directory and
# drop the stale pre-adaptation skill directories from the base image.
COPY life-science/bionemo-librechat/skills/ /app/skill/
COPY templates/hcls-librechat/skills/ /app/skill/
# Prepared from the pinned official repository; private source stays out of Git.
COPY templates/hcls-librechat/vendor/nebius-skills/ /app/skill/
RUN cd /app/skill && rm -rf boltz2-nim openfold2-nim openfold3-nim diffdock-nim \
      genmol-nim molmim-nim msa-search-nim evo2-nim proteinmpnn-nim \
      rfdiffusion-nim bionemo-workbench-tutorials
COPY templates/hcls-librechat/assets/nebius-logo.svg /app/client/dist/assets/logo.svg
COPY templates/hcls-librechat/assets/token-factory.svg /app/client/dist/assets/token-factory.svg
RUN chmod 0755 /usr/local/bin/hcls-librechat-entrypoint \
 && node /opt/hcls-librechat/brand-client.mjs /app/client/dist \
 && mkdir -p /data/db /data/hcls-librechat /app/uploads /app/logs \
 && chown -R node:node /data /app/uploads /app/logs \
 && chmod 0700 /data/hcls-librechat \
 && mkdir -p /workspace /data/hcls-execution

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
# The operator explicitly enables root command execution in this environment.
USER root
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/hcls-librechat-entrypoint"]
