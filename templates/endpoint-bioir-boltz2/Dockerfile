# This image intentionally contains only the HTTP tutorial adapter and its
# bootstrapper. BioIR itself is installed from NVIDIA's public package release
# at endpoint start-up; no early-access image, wheel, or checkpoint is copied
# into the published image.
FROM nvidia/cuda:13.2.0-base-ubuntu24.04

LABEL org.opencontainers.image.title="BioNeMo Inference Runtime Boltz-2 Serverless tutorial" \
      org.opencontainers.image.description="Thin public launcher for the BioIR Boltz-2 endpoint tutorial" \
      org.opencontainers.image.source="https://github.com/nebius/serverless-ai-cookbook"

ENV DEBIAN_FRONTEND=noninteractive \
    VIRTUAL_ENV=/opt/bioir/venv \
    PATH=/opt/bioir/venv/bin:$PATH \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/var/lib/bioir \
    BIOIR_CACHE=/var/lib/bioir/.cache/bionemo_ir \
    HF_HOME=/var/lib/bioir/.cache/huggingface \
    OUTPUT_DIR=/var/lib/bioir/output \
    BIOIR_SAMPLING_STEPS=50 \
    MAX_SEQUENCE_LENGTH=1024 \
    BIOIR_DISTRIBUTION=bionemo-ir

RUN apt-get update \
 && apt-get install --yes --no-install-recommends \
      build-essential ca-certificates curl git python3.12 python3.12-dev python3.12-venv \
 && python3.12 -m venv "$VIRTUAL_ENV" \
 && "$VIRTUAL_ENV/bin/pip" install --no-cache-dir --upgrade pip \
 && groupadd --gid 10001 bioir \
 && useradd --uid 10001 --gid 10001 --create-home --home-dir "$HOME" --shell /usr/sbin/nologin bioir \
 && install -d -o bioir -g bioir "$BIOIR_CACHE" "$HF_HOME" "$OUTPUT_DIR" \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN "$VIRTUAL_ENV/bin/pip" install --no-cache-dir -r /tmp/requirements.txt

COPY entrypoint.sh /usr/local/bin/bioir-bootstrap
COPY notebook.sh /usr/local/bin/bioir-notebook
COPY src /app
COPY notebooks /workspace/notebooks
RUN chmod 0755 /usr/local/bin/bioir-bootstrap /usr/local/bin/bioir-notebook \
 && chown -R bioir:bioir /app /workspace "$VIRTUAL_ENV"

USER 10001:10001
EXPOSE 8000 8888

ENTRYPOINT ["/usr/local/bin/bioir-bootstrap"]
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
