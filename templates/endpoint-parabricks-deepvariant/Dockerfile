# syntax=docker/dockerfile:1.7
ARG PARABRICKS_IMAGE=nvcr.io/nvidia/clara/clara-parabricks:4.7.1-1@sha256:a748d86cbb850641a1e0afae6de2e7422f1375e4a0cce08a5c2cead9fa302237
FROM ${PARABRICKS_IMAGE}
ARG PARABRICKS_IMAGE
ARG HCLS_IMAGE_REVISION=unknown
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HCLS_STORAGE_ROOT=/mnt/hcls \
    HCLS_SCRATCH_ROOT=/tmp/hcls-scratch \
    HCLS_ENABLE_MCP=1 \
    HCLS_SEQUENTIAL_JSON_WRITES=1 \
    HCLS_IMMUTABLE_STATUS_SNAPSHOTS=1 \
    HCLS_IMAGE_REVISION=${HCLS_IMAGE_REVISION} \
    HCLS_PARABRICKS_INPUT_ROOT=/mnt/hcls/parabricks-deepvariant/fixtures \
    PARABRICKS_BASE_IMAGE=${PARABRICKS_IMAGE} \
    PARABRICKS_GPU_COUNT=1
LABEL org.opencontainers.image.title="Nebius Serverless Parabricks DeepVariant REST and MCP API" \
      org.opencontainers.image.source="https://github.com/nebius/serverless-ai-cookbook" \
      org.opencontainers.image.revision="${HCLS_IMAGE_REVISION}" \
      org.opencontainers.image.licenses="Apache-2.0 AND LicenseRef-NVIDIA-AI-Product-Agreement"
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates python3-venv samtools \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv /opt/hcls \
 && /opt/hcls/bin/pip install --no-cache-dir fastapi==0.136.1 mcp==2.2.0 pydantic==2.12.5 uvicorn==0.52.4 \
 && mkdir -p /app /mnt/hcls /tmp/hcls-scratch
COPY hcls_api /app/hcls_api
COPY app.py /app/app.py
WORKDIR /app
ENV PATH=/opt/hcls/bin:${PATH} PYTHONPATH=/app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=2m --retries=5 \
  CMD ["/opt/hcls/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=5)"]
ENTRYPOINT ["/opt/hcls/bin/python", "-m", "uvicorn"]
CMD ["app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--no-server-header"]
