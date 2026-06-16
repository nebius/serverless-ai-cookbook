FROM nvidia/cuda:12.6.3-runtime-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY self-hosted-bionemo/requirements.txt ./requirements.txt
RUN python3 -m pip install --break-system-packages --no-cache-dir -r requirements.txt

COPY bionemo_agent/ ./bionemo_agent/

EXPOSE 8000

# Bypass the CUDA base image entrypoint so its startup banner does not pollute
# stdout. The smoke check (python3 -m bionemo_agent.service_smoke) prints a
# single JSON document to stdout, and clean stdout keeps that output parseable
# in Serverless Job logs.
ENTRYPOINT []

CMD ["sh", "-c", "python3 -m uvicorn bionemo_agent.self_hosted_service:app --host 0.0.0.0 --port ${PORT}"]

