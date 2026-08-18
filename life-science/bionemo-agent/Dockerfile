ARG OPENCLAW_IMAGE="ghcr.io/openclaw/openclaw:2026.7.1-2@sha256:8789721d2e9b24b780a1504b56deb4c6bd5c7dbf96a1dd117e7c45c2ed72c8ac"
ARG UV_IMAGE="ghcr.io/astral-sh/uv:0.11.7@sha256:240fb85ab0f263ef12f492d8476aa3a2e4e1e333f7d67fbdd923d00a506a516a"

FROM ${UV_IMAGE} AS clawbio-uv

FROM ${OPENCLAW_IMAGE} AS clawbio-builder

ARG CLAWBIO_COMMIT="794dd1f5aacc1af308694c9b2f7966d0e396916e"
ARG CLAWBIO_ARCHIVE_SHA256="207978ebea5d940242f8f0e2708ef768ac976bf04e161e68c6556c91f215e5a0"
ARG RDKIT_VERSION="2025.9.6"
ARG RDKIT_WHEEL_SHA256="3f4fc084890efb29b51ea4679bb07d28b276b6e73e3381e678a5ba057b4c4222"

USER root
COPY --from=clawbio-uv /uv /usr/local/bin/uv
COPY runtime/prepare-clawbio.py /tmp/prepare-clawbio.py
COPY openclaw-plugin/src/ligand-embeddability.py /tmp/ligand-embeddability.py
ADD --checksum=sha256:${CLAWBIO_ARCHIVE_SHA256} \
  https://github.com/ClawBio/ClawBio/archive/${CLAWBIO_COMMIT}.tar.gz \
  /tmp/clawbio-source.tar.gz
ADD --checksum=sha256:${RDKIT_WHEEL_SHA256} \
  https://files.pythonhosted.org/packages/4c/e4/0c4656224167261093d057d018acb8b9ddbad22f3ebe3706424e23ef7b6b/rdkit-2025.9.6-cp311-cp311-manylinux_2_28_x86_64.whl \
  /tmp/rdkit-2025.9.6-cp311-cp311-manylinux_2_28_x86_64.whl
RUN install -d /tmp/clawbio-source \
    && tar -xzf /tmp/clawbio-source.tar.gz --strip-components=1 -C /tmp/clawbio-source \
    && UV_PROJECT_ENVIRONMENT=/opt/clawbio uv sync \
      --project /tmp/clawbio-source \
      --python /usr/bin/python3 \
      --no-python-downloads \
      --frozen \
      --no-dev \
      --extra mcp \
      --no-editable \
    && uv pip install --python /opt/clawbio/bin/python --no-deps /tmp/rdkit-2025.9.6-cp311-cp311-manylinux_2_28_x86_64.whl \
    && /opt/clawbio/bin/python /tmp/ligand-embeddability.py --self-test \
    && /opt/clawbio/bin/python /tmp/prepare-clawbio.py \
      --venv /opt/clawbio \
      --source /tmp/clawbio-source \
      --commit "${CLAWBIO_COMMIT}" \
    && RDKIT_LICENSE="$(find /opt/clawbio/lib -path '*/rdkit-*.dist-info/LICENSE.md' -print -quit)" \
    && test -n "${RDKIT_LICENSE}" \
    && install -m 0444 "${RDKIT_LICENSE}" /opt/clawbio/share/clawbio/RDKit-LICENSE \
    && rm -rf /tmp/clawbio-source /tmp/clawbio-source.tar.gz /tmp/prepare-clawbio.py /tmp/ligand-embeddability.py /tmp/rdkit-2025.9.6-cp311-cp311-manylinux_2_28_x86_64.whl \
    && chmod -R a-w /opt/clawbio

FROM ${OPENCLAW_IMAGE}

ARG CLOUDFLARED_VERSION="2026.7.3"
ARG CLOUDFLARED_SHA256="9d71c677db00134c1bd4144b7783486b654ad281b1ea62b4972098d19f770f17"
ARG BIONEMO_TOOLKIT_COMMIT="23d483511e0b42221bdafd7259ff43c05220ee86"
ARG CODEX_VERSION="0.147.0"
ARG CLAUDE_CODE_VERSION="2.1.228"
ARG THREEDMOL_VERSION="2.5.5"
ARG CLAWBIO_COMMIT="794dd1f5aacc1af308694c9b2f7966d0e396916e"
ARG RDKIT_VERSION="2025.9.6"

LABEL org.opencontainers.image.title="Nebius BioNeMo Agent Workbench" \
      org.opencontainers.image.description="Owner-controlled root-admin BioNeMo browser agent plus Codex and Claude Code CLIs with NVIDIA BioNeMo and redistributable ClawBio skills" \
      org.opencontainers.image.source="https://github.com/nebius/serverless-ai-cookbook/tree/main/life-science/bionemo-agent" \
      org.opencontainers.image.version="3.4.0" \
      org.opencontainers.image.licenses="Apache-2.0 AND CC-BY-4.0 AND BSD-3-Clause AND MIT AND GPL-3.0-only" \
      io.nebius.bionemo.toolkit.commit="${BIONEMO_TOOLKIT_COMMIT}" \
      io.nebius.clawbio.commit="${CLAWBIO_COMMIT}" \
      io.nebius.rdkit.version="${RDKIT_VERSION}" \
      io.nebius.openclaw.version="2026.7.1-2" \
      io.nebius.cloudflared.version="${CLOUDFLARED_VERSION}" \
      io.nebius.codex.version="${CODEX_VERSION}" \
      io.nebius.claude-code.version="${CLAUDE_CODE_VERSION}" \
      io.nebius.3dmol.version="${THREEDMOL_VERSION}"

USER root
COPY --from=clawbio-uv /uv /usr/local/bin/uv
RUN apt-get update \
    && apt-get install --only-upgrade --yes --no-install-recommends \
      libgnutls30=3.7.9-2+deb12u7 \
    && apt-get install --yes --no-install-recommends \
      build-essential \
      ca-certificates \
      curl \
      file \
      git \
      jq \
      less \
      lsof \
      openssh-client \
      pkg-config \
      procps \
      python3-dev \
      python3-pip \
      python3-venv \
      ripgrep \
      sudo \
      unzip \
      wget \
      zip \
    && npm install --global --omit=dev \
      "@openai/codex@${CODEX_VERSION}" \
      "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
      "3dmol@${THREEDMOL_VERSION}" \
    && install -d -o root -g root -m 0700 /opt/bionemo/assets /opt/bionemo/licenses \
    && install -o root -g root -m 0400 /usr/local/lib/node_modules/3dmol/build/3Dmol-min.js /opt/bionemo/assets/3Dmol-min.js \
    && install -o root -g root -m 0400 /usr/local/lib/node_modules/3dmol/LICENSE /opt/bionemo/licenses/3dmol-LICENSE \
    && rm -rf /var/lib/apt/lists/* \
      /root/.npm \
      /usr/local/lib/node_modules/3dmol \
      /app/node_modules/@vitest \
      /app/node_modules/vitest
ADD --chmod=0755 --checksum=sha256:${CLOUDFLARED_SHA256} \
  https://github.com/cloudflare/cloudflared/releases/download/${CLOUDFLARED_VERSION}/cloudflared-linux-amd64 \
  /usr/local/bin/cloudflared

COPY --from=clawbio-builder --chown=root:root /opt/clawbio /opt/clawbio
COPY --chown=root:root openclaw-plugin /opt/bionemo/openclaw-plugin
COPY --chown=root:root config /opt/bionemo/config
COPY --chown=root:root runtime /opt/bionemo/runtime
COPY --chmod=0755 runtime/bionemo-agent /usr/local/bin/bionemo-agent
COPY --chown=root:root workspace /workspace/agent
COPY --chown=root:root vendor /opt/bionemo/vendor

RUN node /opt/bionemo/runtime/patch-openclaw-mcp-turn-context.mjs /app/dist \
    && node /opt/bionemo/runtime/patch-openclaw-final-presentation.mjs /app/dist \
    && node /opt/bionemo/runtime/patch-openclaw-super-followup.mjs /app/dist \
    && node /opt/bionemo/runtime/prepare-control-ui.mjs \
      /app/dist/control-ui \
      /opt/bionemo/control-ui \
      /opt/bionemo/runtime/control-ui-default-session.js \
    && install -d -o root -g root -m 0700 \
      /workspace/agent/artifacts /workspace/agent/artifacts/clawbio /workspace/state /root/.claude/skills /root/.codex \
    && install -d -o root -g root -m 0755 /etc/codex/skills \
    && cp -a /opt/bionemo/vendor/bionemo-agent-toolkit/plugins/bionemo-agent-toolkit/skills/. /etc/codex/skills/ \
    && cp -a /opt/bionemo/vendor/bionemo-agent-toolkit/plugins/bionemo-agent-toolkit/skills/. /root/.claude/skills/ \
    && cp -a /workspace/agent/skills/tavily-research /etc/codex/skills/ \
    && cp -a /workspace/agent/skills/tavily-research /root/.claude/skills/ \
    && CLAWBIO_SKILL_ROOT="$(/opt/clawbio/bin/python -c 'from clawbio.cli import SKILLS_DIR; print(SKILLS_DIR)')" \
    && for skill in "${CLAWBIO_SKILL_ROOT}"/*; do \
      test -f "${skill}/SKILL.md" || continue; \
      cp -a "${skill}" /etc/codex/skills/; \
      cp -a "${skill}" /root/.claude/skills/; \
    done \
    && test "$(find "${CLAWBIO_SKILL_ROOT}" -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l)" -eq 95 \
    && test "$(find /etc/codex/skills -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l)" -eq 127 \
    && test "$(find /root/.claude/skills -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l)" -eq 127 \
    && install -o root -g root -m 0400 /opt/clawbio/share/clawbio/LICENSE /opt/bionemo/licenses/clawbio-LICENSE \
    && install -o root -g root -m 0400 /opt/clawbio/share/clawbio/Apache-2.0 /opt/bionemo/licenses/clawbio-Apache-2.0 \
    && install -o root -g root -m 0400 /opt/clawbio/share/clawbio/GPL-3.0 /opt/bionemo/licenses/clawbio-GPL-3.0 \
    && install -o root -g root -m 0400 /opt/clawbio/share/clawbio/RDKit-LICENSE /opt/bionemo/licenses/rdkit-LICENSE \
    && chmod -R go-rwx /opt/bionemo /workspace/agent /root/.claude

ENV PORT=18789 \
    HOME=/root \
    SHELL=/bin/bash \
    PATH=/root/.local/bin:/opt/clawbio/bin:${PATH} \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OPENCLAW_GATEWAY_PORT=18789 \
    OPENCLAW_STATE_DIR=/workspace/state \
    OPENCLAW_CONFIG_PATH=/workspace/state/openclaw.json \
    BIONEMO_CONFIG_TEMPLATE=/opt/bionemo/config/openclaw.template.json \
    BIONEMO_ARTIFACT_ROOT=/workspace/agent/artifacts \
    BIONEMO_NOTEBOOK_ROOT=/workspace/agent/notebooks \
    BIONEMO_3DMOL_PATH=/opt/bionemo/assets/3Dmol-min.js \
    BIONEMO_VENDOR_ROOT=/opt/bionemo/vendor/bionemo-agent-toolkit \
    BIONEMO_MCP_URL=https://clawbio-mcp.89-169-122-161.sslip.io/mcp \
    BIONEMO_ENABLE_HTTPS_TUNNEL=false \
    BIONEMO_REQUIRE_DEVICE_PAIRING=false \
    NODE_ENV=production

WORKDIR /workspace/agent
USER root
EXPOSE 18789
HEALTHCHECK --interval=15s --timeout=5s --start-period=45s --retries=4 CMD ["node", "/opt/bionemo/runtime/healthcheck.mjs"]
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/bionemo-agent"]
CMD ["openclaw"]
