# syntax=docker/dockerfile:1.7
FROM docker.io/python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

ARG VINA_COMMIT=8eb40404f4f45608acb3b01427587ac049f27c1f
ARG HCLS_IMAGE_REVISION=unknown
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    HCLS_RUN_ROOT=/data/runs VINA_EXAMPLE_ROOT=/opt/hcls/examples/vina \
    HCLS_IMAGE_REVISION=${HCLS_IMAGE_REVISION}
LABEL org.opencontainers.image.title="Nebius HCLS AutoDock Vina API" \
      org.opencontainers.image.source="https://github.com/nebius/serverless-ai-cookbook" \
      org.opencontainers.image.revision="${HCLS_IMAGE_REVISION}" \
      org.opencontainers.image.licenses="Apache-2.0"
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates=20250419~deb12u1 \
      curl=7.88.1-10+deb12u15 \
      libgomp1=12.2.0-14+deb12u1 \
      libgnutls30=3.7.9-2+deb12u7 \
      libssl3=3.0.20-1~deb12u2 \
      openssl=3.0.20-1~deb12u2 && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir fastapi==0.136.1 pydantic==2.12.5 uvicorn==0.34.0 vina==1.2.7 && \
    groupadd --gid 10001 hcls && useradd --uid 10001 --gid hcls --create-home --home-dir /home/hcls hcls && \
    mkdir -p /app /data/runs /opt/hcls/examples/vina && \
    curl --fail --location --proto '=https' --tlsv1.2 \
      "https://raw.githubusercontent.com/ccsb-scripps/AutoDock-Vina/${VINA_COMMIT}/example/basic_docking/solution/1iep_receptor.pdbqt" \
      --output /opt/hcls/examples/vina/1iep_receptor.pdbqt && \
    curl --fail --location --proto '=https' --tlsv1.2 \
      "https://raw.githubusercontent.com/ccsb-scripps/AutoDock-Vina/${VINA_COMMIT}/example/basic_docking/solution/1iep_ligand.pdbqt" \
      --output /opt/hcls/examples/vina/1iep_ligand.pdbqt && \
    chown -R 10001:10001 /app /data /opt/hcls /home/hcls
COPY --chown=10001:10001 templates/hcls-common/hcls_api /app/hcls_api
COPY --chown=10001:10001 templates/endpoint-hcls-autodock-vina/app.py /app/app.py
WORKDIR /app
ENV PYTHONPATH=/app
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=5 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=5)"]
ENTRYPOINT ["python", "-m", "uvicorn"]
CMD ["app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--no-server-header"]
