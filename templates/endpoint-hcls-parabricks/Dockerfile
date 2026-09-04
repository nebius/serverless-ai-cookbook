# syntax=docker/dockerfile:1.7
ARG PARABRICKS_API_BASE=cr.eu-north1.nebius.cloud/e00ffw8yqnrrd507t9/clawbio-event/parabricks-deepvariant@sha256:f4db163ea21b896643ac41c82999f068dfaaa9f2282d443a438e0dc40dbc4af9
FROM ${PARABRICKS_API_BASE}
ARG HCLS_IMAGE_REVISION=unknown
LABEL org.opencontainers.image.title="Nebius HCLS Parabricks DeepVariant API" \
      org.opencontainers.image.source="https://github.com/nebius/serverless-ai-cookbook" \
      org.opencontainers.image.revision="${HCLS_IMAGE_REVISION}" \
      org.opencontainers.image.licenses="LicenseRef-NVIDIA-AI-Product-Agreement" \
      ai.nvidia.parabricks.version="4.7.0-1"
ENV PARABRICKS_VERSION=4.7.0-1 \
    PARABRICKS_GPU_COUNT=2 \
    HCLS_IMAGE_REVISION=${HCLS_IMAGE_REVISION} \
    HCLS_RUN_ROOT=/data/hcls/parabricks/runs \
    HCLS_PARABRICKS_INPUT_ROOT=/data/hcls/parabricks/fixtures
RUN if ! getent group 10001 >/dev/null; then groupadd --gid 10001 hcls; fi && \
    if ! getent passwd 10001 >/dev/null; then useradd --uid 10001 --gid 10001 --create-home --home-dir /home/hcls hcls; fi && \
    mkdir -p /app/hcls_api /data/hcls/parabricks/runs /data/hcls/parabricks/fixtures && \
    chown -R 10001:10001 /app /data/hcls /home/hcls
COPY --chown=10001:10001 templates/hcls-common/hcls_api /app/hcls_api
COPY --chown=10001:10001 templates/endpoint-hcls-parabricks/app.py /app/app.py
WORKDIR /app
ENV PYTHONPATH=/app
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=15s --start-period=30s --retries=5 CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=10)"]
ENTRYPOINT ["python3", "-m", "uvicorn"]
CMD ["app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
