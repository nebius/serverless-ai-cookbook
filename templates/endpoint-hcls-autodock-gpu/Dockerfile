# syntax=docker/dockerfile:1.7

ARG CUDA_DEVEL_IMAGE=nvidia/cuda:12.8.1-devel-ubuntu22.04@sha256:a99a1860ba8e2916e5c3e73b72ec4c4301653a84586e05bfc9a2aa2d58027e97
ARG CUDA_RUNTIME_IMAGE=nvidia/cuda:12.8.1-runtime-ubuntu22.04@sha256:4a801ef9232d2b05e69df4eb8aa054dbbe2824e5499e1e6e857320bb01ac41a9

FROM ${CUDA_DEVEL_IMAGE} AS engine
ARG AUTODOCK_GPU_REVISION=e63e6f6280ebfad18caa3e8f48afdc269e79e063
ENV DEBIAN_FRONTEND=noninteractive
RUN sed -i -e 's|http://archive.ubuntu.com/ubuntu|https://mirror.zetup.net/ubuntu|g' -e 's|http://security.ubuntu.com/ubuntu|https://mirror.zetup.net/ubuntu|g' /etc/apt/sources.list && \
    apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=5 -o Acquire::http::Timeout=20 update && \
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
    HCLS_IMAGE_REVISION=${HCLS_IMAGE_REVISION} \
    HCLS_RUN_ROOT=/data/runs \
    AUTODOCK_GPU_EXAMPLE_ROOT=/opt/hcls/examples/autodock-gpu/1stp
RUN sed -i -e 's|http://archive.ubuntu.com/ubuntu|https://mirror.zetup.net/ubuntu|g' -e 's|http://security.ubuntu.com/ubuntu|https://mirror.zetup.net/ubuntu|g' /etc/apt/sources.list && \
    apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=5 -o Acquire::http::Timeout=20 update && \
    apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=5 -o Acquire::http::Timeout=20 install -y --no-install-recommends \
      ca-certificates=20260601~22.04.1 \
      libgomp1=12.3.0-1ubuntu1~22.04.3 \
      python3=3.10.6-1~22.04.1 \
      python3-pip=22.0.2+dfsg-1ubuntu0.7 && \
    rm -rf /var/lib/apt/lists/* && \
    pip3 install --no-cache-dir fastapi==0.136.1 pydantic==2.12.5 uvicorn==0.34.0 && \
    groupadd --gid 10001 hcls && useradd --uid 10001 --gid hcls --create-home --home-dir /home/hcls hcls && \
    mkdir -p /app /data/runs /opt/hcls/examples/autodock-gpu/1stp && \
    chown -R 10001:10001 /app /data /opt/hcls /home/hcls
COPY --from=engine /src/autodock-gpu/bin/autodock_gpu_128wi /usr/local/bin/autodock_gpu_128wi
COPY --from=engine /src/autodock-gpu/input/1stp/derived/ /opt/hcls/examples/autodock-gpu/1stp/
COPY --from=engine /src/autodock-gpu/LICENSE /src/autodock-gpu/LICENSE_LGPL /usr/share/licenses/autodock-gpu/
COPY --from=engine /tmp/autodock-gpu-v1.6-corresponding-source.tar.gz /usr/src/autodock-gpu-v1.6-corresponding-source.tar.gz
COPY --chown=10001:10001 templates/hcls-common/hcls_api /app/hcls_api
COPY --chown=10001:10001 templates/endpoint-hcls-autodock-gpu/app.py /app/app.py
WORKDIR /app
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=5 CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=5)"]
ENTRYPOINT ["python3", "-m", "uvicorn"]
CMD ["app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
