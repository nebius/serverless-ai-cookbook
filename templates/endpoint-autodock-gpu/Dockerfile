# syntax=docker/dockerfile:1.7

ARG CUDA_DEVEL_IMAGE=nvidia/cuda:12.8.1-devel-ubuntu22.04@sha256:a99a1860ba8e2916e5c3e73b72ec4c4301653a84586e05bfc9a2aa2d58027e97
ARG CUDA_RUNTIME_IMAGE=nvidia/cuda:12.8.1-runtime-ubuntu22.04@sha256:4a801ef9232d2b05e69df4eb8aa054dbbe2824e5499e1e6e857320bb01ac41a9

FROM ${CUDA_DEVEL_IMAGE} AS engine
ARG AUTODOCK_GPU_REVISION=e63e6f6280ebfad18caa3e8f48afdc269e79e063
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=5 -o Acquire::http::Timeout=20 update && \
    apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=5 -o Acquire::http::Timeout=20 install -y --no-install-recommends \
      build-essential=12.9ubuntu3 \
      ca-certificates=20260601~22.04.1 \
      git=1:2.34.1-1ubuntu1.17 && \
    rm -rf /var/lib/apt/lists/*
RUN git clone --filter=blob:none https://github.com/ccsb-scripps/AutoDock-GPU.git /src/autodock-gpu
WORKDIR /src/autodock-gpu
RUN \
    git checkout --detach "${AUTODOCK_GPU_REVISION}" && \
    test "$(git rev-parse HEAD)" = "${AUTODOCK_GPU_REVISION}" && \
    GPU_INCLUDE_PATH=/usr/local/cuda/include \
    GPU_LIBRARY_PATH=/usr/local/cuda/lib64 \
    make DEVICE=CUDA NUMWI=128 TARGETS="80 86 89 90" && \
    test -x bin/autodock_gpu_128wi && \
    tar --exclude=.git -czf /tmp/autodock-gpu-v1.6-corresponding-source.tar.gz .

FROM ${CUDA_RUNTIME_IMAGE}
ARG HCLS_IMAGE_REVISION=unknown
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HCLS_IMAGE_REVISION=${HCLS_IMAGE_REVISION} \
    HCLS_STORAGE_ROOT=/mnt/hcls \
    HCLS_SCRATCH_ROOT=/tmp/hcls-scratch \
    HCLS_ENABLE_MCP=1 \
    HCLS_SEQUENTIAL_JSON_WRITES=1 \
    HCLS_IMMUTABLE_STATUS_SNAPSHOTS=1 \
    AUTODOCK_GPU_EXAMPLE_ROOT=/opt/hcls/examples/autodock-gpu/1stp
LABEL org.opencontainers.image.title="Nebius Serverless AutoDock-GPU REST and MCP API" \
      org.opencontainers.image.source="https://github.com/nebius/serverless-ai-cookbook" \
      org.opencontainers.image.revision="${HCLS_IMAGE_REVISION}" \
      org.opencontainers.image.licenses="GPL-2.0-only AND LGPL-2.1-only"
RUN sed -i -e 's|http://archive.ubuntu.com/ubuntu|https://mirror.zetup.net/ubuntu|g' -e 's|http://security.ubuntu.com/ubuntu|https://mirror.zetup.net/ubuntu|g' /etc/apt/sources.list && \
    apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=5 -o Acquire::http::Timeout=20 update && \
    apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=5 -o Acquire::http::Timeout=20 install -y --no-install-recommends \
      ca-certificates=20260601~22.04.1 \
      dirmngr=2.2.27-3ubuntu2.5 \
      gnupg=2.2.27-3ubuntu2.5 \
      gnupg-l10n=2.2.27-3ubuntu2.5 \
      gnupg-utils=2.2.27-3ubuntu2.5 \
      gnupg2=2.2.27-3ubuntu2.5 \
      gpg=2.2.27-3ubuntu2.5 \
      gpg-agent=2.2.27-3ubuntu2.5 \
      gpg-wks-client=2.2.27-3ubuntu2.5 \
      gpg-wks-server=2.2.27-3ubuntu2.5 \
      gpgconf=2.2.27-3ubuntu2.5 \
      gpgsm=2.2.27-3ubuntu2.5 \
      gpgv=2.2.27-3ubuntu2.5 \
      libgomp1=12.3.0-1ubuntu1~22.04.3 \
      libssl3=3.0.2-0ubuntu1.29 \
      openssl=3.0.2-0ubuntu1.29 \
      python3=3.10.6-1~22.04.1 \
      python3-pip=22.0.2+dfsg-1ubuntu0.7 \
      python3-venv=3.10.6-1~22.04.1 && \
    rm -rf /var/lib/apt/lists/* && \
    python3 -m venv /opt/hcls && \
    /opt/hcls/bin/pip install --no-cache-dir fastapi==0.136.1 mcp==2.2.0 pydantic==2.12.5 uvicorn==0.52.4 && \
    /opt/hcls/bin/pip uninstall -y setuptools && \
    mkdir -p /app /mnt/hcls /tmp/hcls-scratch /opt/hcls/examples/autodock-gpu/1stp
COPY --from=engine /src/autodock-gpu/bin/autodock_gpu_128wi /usr/local/bin/autodock_gpu_128wi
COPY --from=engine /src/autodock-gpu/input/1stp/derived/ /opt/hcls/examples/autodock-gpu/1stp/
COPY --from=engine /src/autodock-gpu/LICENSE /src/autodock-gpu/LICENSE_LGPL /usr/share/licenses/autodock-gpu/
COPY --from=engine /tmp/autodock-gpu-v1.6-corresponding-source.tar.gz /usr/src/autodock-gpu-v1.6-corresponding-source.tar.gz
COPY hcls_api /app/hcls_api
COPY app.py /app/app.py
WORKDIR /app
ENV PATH=/opt/hcls/bin:${PATH} PYTHONPATH=/app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=2m --retries=5 \
  CMD ["/opt/hcls/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=5)"]
ENTRYPOINT ["/opt/hcls/bin/python", "-m", "uvicorn"]
CMD ["app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
