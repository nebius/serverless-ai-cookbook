# syntax=docker/dockerfile:1.7
FROM bionemo-librechat-base:20260907-3f27726
USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl wget unzip zip jq procps file && rm -rf /var/lib/apt/lists/*
COPY life-science/bionemo-librechat/librechat.yaml /app/librechat.yaml
COPY life-science/bionemo-librechat/MCPUIResource.tsx /app/client/src/components/MCPUIResource/MCPUIResource.tsx
COPY life-science/bionemo-librechat/admin-mcp.py /opt/bionemo/admin-mcp.py
COPY life-science/bionemo-librechat/viewer-mcp.py /opt/bionemo/viewer-mcp.py
COPY life-science/bionemo-librechat/artifact-mcp.py /opt/bionemo/artifact-mcp.py
COPY life-science/bionemo-librechat/3dmol.js /opt/bionemo/3dmol.js
COPY life-science/bionemo-librechat/tavily-mcp.mjs /opt/bionemo/tavily-mcp.mjs
COPY life-science/bionemo-librechat/tutorials.md /opt/bionemo/tutorials.md
COPY life-science/bionemo-librechat/seed-workbench.js /app/seed-workbench.js
COPY skills/scientific-ai/ /app/skill
COPY life-science/bionemo-librechat/entrypoint.sh /usr/local/bin/bionemo-librechat-entrypoint
RUN chmod 0755 /usr/local/bin/bionemo-librechat-entrypoint /opt/bionemo/*.py /opt/bionemo/*.mjs \
 && mkdir -p /workspace/shared/bionemo-artifacts /data/db /app/uploads /app/logs \
 && printf '%s\n' 'The default BioNeMo Workbench landing page contains grouped tutorial cards that start tool-enabled chats.' > /app/README-BIONEMO.txt
RUN npm run build:client
ENV HOST=0.0.0.0 PORT=3080 NODE_ENV=production MONGO_URI=mongodb://127.0.0.1:27017/LibreChat CONFIG_PATH=/app/librechat.yaml DEPLOYMENT_SKILLS_DIR=/app/skill ALLOW_REGISTRATION=true ALLOW_EMAIL_LOGIN=true ENDPOINTS=agents,custom BIONEMO_WORKSPACE_ROOT=/workspace/shared BIONEMO_ARTIFACT_ROOT=/workspace/shared/bionemo-artifacts
EXPOSE 3080
ENTRYPOINT ["/usr/local/bin/bionemo-librechat-entrypoint"]
