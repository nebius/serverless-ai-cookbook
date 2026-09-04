# syntax=docker/dockerfile:1.7
FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7
ARG HCLS_IMAGE_REVISION=unknown
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HCLS_IMAGE_REVISION=${HCLS_IMAGE_REVISION}
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates=20250419~deb12u1 \
      libgnutls30=3.7.9-2+deb12u7 \
      libssl3=3.0.20-1~deb12u2 \
      openssl=3.0.20-1~deb12u2 && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir fastapi==0.136.1 httpx==0.28.1 pydantic==2.12.5 uvicorn==0.34.0 && \
    groupadd --gid 10001 hcls && useradd --uid 10001 --gid hcls --create-home --home-dir /home/hcls hcls && \
    mkdir -p /app/static && chown -R 10001:10001 /app /home/hcls
COPY --chown=10001:10001 templates/hcls-workbench/app.py /app/app.py
COPY --chown=10001:10001 templates/hcls-workbench/static/ /app/static/
WORKDIR /app
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=5 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=5)"]
ENTRYPOINT ["python", "-m", "uvicorn"]
CMD ["app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--no-server-header"]
