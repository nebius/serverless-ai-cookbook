# ACE-Step 1.5 sync wrapper + upstream acestep-api. Pinned upstream tag — no rolling tags.
FROM nvidia/cuda:12.8.0-runtime-ubuntu22.04

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1

RUN printf 'Acquire::Retries "5";\nAcquire::http::Timeout "30";\n' \
      > /etc/apt/apt.conf.d/80-retries \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
      python3.11 \
      python3.11-dev \
      python3-pip \
      git \
      curl \
      ffmpeg \
      libsndfile1 \
      build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.11 /usr/bin/python

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Upstream tags are v0.1.x (pyproject version is 1.5.0). Pin commit, not a missing v1.5.0 tag.
ARG ACESTEP_COMMIT=6d467e4b5081ccb0abf1ec1bf4fdf9051a2d34b0
RUN git clone --filter=blob:none --no-checkout https://github.com/ace-step/ACE-Step-1.5.git /opt/acestep \
    && cd /opt/acestep \
    && git checkout "${ACESTEP_COMMIT}" \
    && uv pip install --system --no-cache .

RUN pip install --no-cache-dir \
      fastapi==0.141.1 \
      uvicorn==0.52.1 \
      httpx==0.28.1

WORKDIR /app
COPY serve.py /app/serve.py

ENV ACESTEP_PROJECT_ROOT=/opt/acestep \
    ACESTEP_OUTPUT_DIR=/tmp/acestep-outputs \
    ACESTEP_DEVICE=cuda \
    ACESTEP_API_HOST=127.0.0.1 \
    ACESTEP_API_PORT=8001 \
    ACESTEP_NO_INIT=false \
    ACESTEP_INIT_LLM=false \
    ACESTEP_CONFIG_PATH=acestep-v15-turbo \
    ACESTEP_LM_MODEL_PATH=acestep-5Hz-lm-0.6B \
    UPSTREAM_BASE=http://127.0.0.1:8001 \
    PORT=8000 \
    API_MODEL=ACE-Step/Ace-Step1.5

EXPOSE 8000
CMD ["python", "serve.py"]
