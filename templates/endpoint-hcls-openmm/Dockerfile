# syntax=docker/dockerfile:1.7
ARG CUDA_BASE=docker.io/nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04@sha256:ac55d124da4882b497f732d8dfd9a702d5447a5f29d08d56da6f64f0a1eb34bc
ARG MICROMAMBA_IMAGE=docker.io/mambaorg/micromamba:2.3.3@sha256:800e7ade3ffe29c9a9ac2026163131495f8197c3852e572c5835beb4e8a33cd6

FROM ${MICROMAMBA_IMAGE} AS micromamba
FROM ${CUDA_BASE}
ARG HCLS_IMAGE_REVISION=unknown

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    HCLS_RUN_ROOT=/data/runs HCLS_IMAGE_REVISION=${HCLS_IMAGE_REVISION}

COPY --from=micromamba /bin/micromamba /usr/local/bin/micromamba
COPY templates/endpoint-hcls-openmm/openmm-linux-64.lock /tmp/openmm-linux-64.lock
RUN sed -i -e 's|http://archive.ubuntu.com/ubuntu|https://mirror.zetup.net/ubuntu|g' -e 's|http://security.ubuntu.com/ubuntu|https://mirror.zetup.net/ubuntu|g' /etc/apt/sources.list /etc/apt/sources.list.d/ubuntu.sources && \
    apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=5 -o Acquire::http::Timeout=20 update && \
    apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=5 -o Acquire::http::Timeout=20 install -y --no-install-recommends \
      ca-certificates=20260601~24.04.1 \
      libgomp1=14.2.0-4ubuntu2~24.04.1 && \
    rm -rf /var/lib/apt/lists/* && \
    micromamba create -y -p /opt/hcls -f /tmp/openmm-linux-64.lock && \
    micromamba clean -a -y && \
    /opt/hcls/bin/pip install --no-cache-dir fastapi==0.136.1 pydantic==2.12.5 uvicorn==0.34.0

RUN groupadd --gid 10001 hcls && useradd --uid 10001 --gid hcls --create-home --home-dir /home/hcls hcls && \
    mkdir -p /app /data/runs && chown -R 10001:10001 /app /data /home/hcls
COPY --chown=10001:10001 templates/hcls-common/hcls_api /app/hcls_api
COPY --chown=10001:10001 templates/endpoint-hcls-openmm/app.py /app/app.py
WORKDIR /app
ENV PATH=/opt/hcls/bin:${PATH} PYTHONPATH=/app
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=5 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=5)"]
ENTRYPOINT ["python", "-m", "uvicorn"]
CMD ["app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--no-server-header"]
