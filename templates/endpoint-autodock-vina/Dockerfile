# syntax=docker/dockerfile:1.7
FROM docker.io/python:3.12-slim-bookworm@sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134

ARG VINA_COMMIT=8eb40404f4f45608acb3b01427587ac049f27c1f
ARG HCLS_IMAGE_REVISION=unknown
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HCLS_STORAGE_ROOT=/mnt/hcls \
    HCLS_SCRATCH_ROOT=/tmp/hcls-scratch \
    HCLS_ENABLE_MCP=1 \
    HCLS_SEQUENTIAL_JSON_WRITES=1 \
    HCLS_IMMUTABLE_STATUS_SNAPSHOTS=1 \
    VINA_EXAMPLE_ROOT=/opt/hcls/examples/vina \
    HCLS_IMAGE_REVISION=${HCLS_IMAGE_REVISION}
LABEL org.opencontainers.image.title="Nebius Serverless AutoDock Vina REST and MCP API" \
      org.opencontainers.image.source="https://github.com/nebius/serverless-ai-cookbook" \
      org.opencontainers.image.revision="${HCLS_IMAGE_REVISION}" \
      org.opencontainers.image.licenses="Apache-2.0"
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates=20250419~deb12u1 \
      curl=7.88.1-10+deb12u15 \
      libgomp1=12.2.0-14+deb12u1 \
      libgnutls30=3.7.9-2+deb12u7 \
      libssl3=3.0.20-1~deb12u2 \
      openssl=3.0.20-1~deb12u2 \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv /opt/hcls \
 && /opt/hcls/bin/pip install --no-cache-dir fastapi==0.136.1 mcp==2.2.0 pydantic==2.12.5 uvicorn==0.52.4 vina==1.2.7 \
 && /opt/hcls/bin/pip uninstall -y setuptools \
 && mkdir -p /app /mnt/hcls /tmp/hcls-scratch /opt/hcls/examples/vina \
 && curl --fail --location --proto '=https' --tlsv1.2 \
      "https://raw.githubusercontent.com/ccsb-scripps/AutoDock-Vina/${VINA_COMMIT}/example/basic_docking/solution/1iep_receptor.pdbqt" \
      --output /opt/hcls/examples/vina/1iep_receptor.pdbqt \
 && curl --fail --location --proto '=https' --tlsv1.2 \
      "https://raw.githubusercontent.com/ccsb-scripps/AutoDock-Vina/${VINA_COMMIT}/example/basic_docking/solution/1iep_ligand.pdbqt" \
      --output /opt/hcls/examples/vina/1iep_ligand.pdbqt
COPY hcls_api /app/hcls_api
COPY app.py /app/app.py
WORKDIR /app
ENV PATH=/opt/hcls/bin:${PATH} PYTHONPATH=/app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=5 \
  CMD ["/opt/hcls/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=5)"]
ENTRYPOINT ["/opt/hcls/bin/python", "-m", "uvicorn"]
CMD ["app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--no-server-header"]
