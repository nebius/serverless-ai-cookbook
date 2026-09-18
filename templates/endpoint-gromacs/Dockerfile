# syntax=docker/dockerfile:1.7
FROM nvidia/cuda:12.8.1-devel-ubuntu24.04@sha256:520292dbb4f755fd360766059e62956e9379485d9e073bbd2f6e3c20c270ed66 AS engine
ARG GROMACS_VERSION=2025.3
ARG GROMACS_SHA256=8bdfca0268f3f10a7ca3c06e59b62f73ea02420c67211c0ff3912f32d7833c65
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential ca-certificates cmake curl libfftw3-dev \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN curl --fail --location --proto '=https' --tlsv1.2 \
      "https://ftp.gromacs.org/gromacs/gromacs-${GROMACS_VERSION}.tar.gz" -o gromacs.tar.gz \
 && echo "${GROMACS_SHA256}  gromacs.tar.gz" | sha256sum -c - \
 && tar -xzf gromacs.tar.gz \
 && cmake -S "gromacs-${GROMACS_VERSION}" -B build \
      -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/gromacs \
      -DGMX_GPU=CUDA -DGMX_CUDA_TARGET_SM="80;86;89;90" \
      -DGMX_SIMD=AVX2_256 -DGMX_BUILD_OWN_FFTW=OFF -DGMX_MPI=OFF \
      -DGMX_THREAD_MPI=ON -DGMX_OPENMP=ON -DGMXAPI=OFF -DREGRESSIONTEST_DOWNLOAD=OFF \
 && cmake --build build --parallel 8 \
 && cmake --install build

FROM nvidia/cuda:12.8.1-runtime-ubuntu24.04@sha256:ebef3c171eeef0298e4eb2e4be843105edf3b8b0ac45e0b43acee358e8046867
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
    GROMACS_BINARY=/opt/gromacs/bin/gmx
LABEL org.opencontainers.image.title="Nebius Serverless GROMACS REST and MCP API" \
      org.opencontainers.image.source="https://github.com/nebius/serverless-ai-cookbook" \
      org.opencontainers.image.revision="${HCLS_IMAGE_REVISION}" \
      org.opencontainers.image.licenses="Apache-2.0 AND LGPL-2.1-or-later AND GPL-2.0-or-later"
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates libfftw3-single3 libgomp1 python3 python3-venv \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv /opt/hcls \
 && /opt/hcls/bin/pip install --no-cache-dir fastapi==0.136.1 mcp==2.2.0 pydantic==2.12.5 uvicorn==0.52.4 \
 && mkdir -p /app /mnt/hcls /tmp/hcls-scratch
COPY --from=engine /opt/gromacs /opt/gromacs
COPY --from=engine /src/gromacs.tar.gz /usr/src/gromacs-2025.3.tar.gz
COPY hcls_api /app/hcls_api
COPY app.py /app/app.py
WORKDIR /app
ENV PATH=/opt/hcls/bin:/opt/gromacs/bin:${PATH} PYTHONPATH=/app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=2m --retries=5 \
  CMD ["/opt/hcls/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=5)"]
ENTRYPOINT ["/opt/hcls/bin/python", "-m", "uvicorn"]
CMD ["app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--no-server-header"]
