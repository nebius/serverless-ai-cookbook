# syntax=docker/dockerfile:1.7
FROM gcr.io/go-containerregistry/crane@sha256:e78770b31258a3846f878036d9c1f63fbe4c871f9f56990bf77fd95c013e3c1b AS crane

FROM python:3.12-slim-bookworm@sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134
ARG HCLS_IMAGE_REVISION=unknown

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HCLS_STORAGE_ROOT=/mnt/hcls \
    HCLS_ENABLE_MCP=1 \
    HCLS_SEQUENTIAL_JSON_WRITES=1 \
    HCLS_IMMUTABLE_STATUS_SNAPSHOTS=1 \
    HCLS_IMAGE_REVISION=${HCLS_IMAGE_REVISION} \
    HCLS_PARABRICKS_INPUT_ROOT=/mnt/hcls/parabricks-deepvariant/fixtures \
    PARABRICKS_IMAGE_REPOSITORY=nvcr.io/nvidia/clara/clara-parabricks \
    PARABRICKS_VERSION=latest \
    PARABRICKS_GPU_COUNT=1 \
    PARABRICKS_RUNTIME_CACHE=/var/cache/hcls-parabricks \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility

LABEL org.opencontainers.image.title="Nebius HCLS dynamic Parabricks DeepVariant API" \
      org.opencontainers.image.source="https://github.com/nebius/serverless-ai-cookbook" \
      org.opencontainers.image.revision="${HCLS_IMAGE_REVISION}" \
      org.opencontainers.image.licenses="LicenseRef-NVIDIA-AI-Product-Agreement"

COPY --from=crane /ko-app/crane /usr/local/bin/crane
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates=20250419~deb12u1 tar=1.34+dfsg-1.2+deb12u1 \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv /opt/hcls \
 && /opt/hcls/bin/pip install --no-cache-dir fastapi==0.136.1 mcp==2.2.0 pydantic==2.12.5 uvicorn==0.52.4 \
 && /opt/hcls/bin/pip uninstall -y setuptools \
 && mkdir -p /app /mnt/hcls /var/cache/hcls-parabricks /run/hcls-parabricks

COPY templates/hcls-common/hcls_api /app/hcls_api
COPY templates/endpoint-hcls-parabricks/app.py /app/app.py
COPY templates/endpoint-hcls-parabricks/runtime_loader.py /app/runtime_loader.py
COPY templates/endpoint-hcls-parabricks/entrypoint.sh /usr/local/bin/hcls-parabricks-entrypoint
RUN chmod 0755 /usr/local/bin/crane /usr/local/bin/hcls-parabricks-entrypoint

WORKDIR /app
ENV PATH=/opt/hcls/bin:/usr/local/bin:${PATH} PYTHONPATH=/app
ENTRYPOINT ["/usr/local/bin/hcls-parabricks-entrypoint"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=20m --retries=5 \
  CMD ["/opt/hcls/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=5)"]
CMD ["/opt/hcls/bin/uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--no-server-header"]
