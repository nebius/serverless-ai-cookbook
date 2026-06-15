# GPU-ready MONAI runtime for a bounded synthetic medical-imaging job.
ARG PYTORCH_IMAGE=pytorch/pytorch:2.7.1-cuda12.6-cudnn9-runtime
FROM ${PYTORCH_IMAGE}

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 --shell /bin/bash nebius && \
    mkdir -p /workspace/output && \
    chown -R nebius:nebius /workspace

WORKDIR /workspace

COPY pyproject.toml README.md ./
COPY monai_job/ ./monai_job/

RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir .

USER nebius

ENTRYPOINT ["python", "-m", "monai_job.run"]

