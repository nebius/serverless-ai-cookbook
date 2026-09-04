# syntax=docker/dockerfile:1.7
ARG GROMACS_BASE=nvcr.io/hpc/gromacs:2023.2@sha256:04d5ac4416523624bbfcb36c85a63fd8a6ac8acf7c2eeb1af89dd03c60d45daf
FROM ${GROMACS_BASE}
ARG HCLS_IMAGE_REVISION=unknown

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    GROMACS_BINARY=/usr/local/gromacs/avx2_256/bin/gmx HCLS_RUN_ROOT=/data/runs \
    HCLS_IMAGE_REVISION=${HCLS_IMAGE_REVISION}
LABEL org.opencontainers.image.title="Nebius HCLS GROMACS API" \
      org.opencontainers.image.source="https://github.com/nebius/serverless-ai-cookbook" \
      org.opencontainers.image.revision="${HCLS_IMAGE_REVISION}" \
      org.opencontainers.image.licenses="LGPL-2.1-only"
RUN sed -i -e 's|http://archive.ubuntu.com/ubuntu|https://mirror.zetup.net/ubuntu|g' -e 's|http://security.ubuntu.com/ubuntu|https://mirror.zetup.net/ubuntu|g' /etc/apt/sources.list && \
    apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=5 -o Acquire::http::Timeout=20 update && \
    apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=5 -o Acquire::http::Timeout=20 install -y --no-install-recommends \
      ca-certificates=20260601~22.04.1 \
      python3=3.10.6-1~22.04.1 \
      python3-venv=3.10.6-1~22.04.1 && \
    rm -rf /var/lib/apt/lists/* && \
    python3 -m venv /opt/hcls && \
    /opt/hcls/bin/pip install --no-cache-dir fastapi==0.136.1 pydantic==2.12.5 uvicorn==0.34.0 && \
    groupadd --gid 10001 hcls && useradd --uid 10001 --gid hcls --create-home --home-dir /home/hcls hcls && \
    mkdir -p /app /data/runs && chown -R 10001:10001 /app /data /home/hcls
COPY --chown=10001:10001 templates/hcls-common/hcls_api /app/hcls_api
COPY --chown=10001:10001 templates/endpoint-hcls-gromacs/app.py /app/app.py
WORKDIR /app
ENV PATH=/opt/hcls/bin:/usr/local/gromacs/avx2_256/bin:${PATH} \
    LD_LIBRARY_PATH=/usr/local/gromacs/avx2_256/lib:${LD_LIBRARY_PATH} PYTHONPATH=/app
ENTRYPOINT []
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=5 CMD ["/opt/hcls/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=5)"]
CMD ["/opt/hcls/bin/uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--no-server-header"]
