FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04@sha256:ac55d124da4882b497f732d8dfd9a702d5447a5f29d08d56da6f64f0a1eb34bc

ENV DEBIAN_FRONTEND=noninteractive UV_NO_PROGRESS=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates ffmpeg git python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/tools && /opt/tools/bin/pip install --no-cache-dir uv==0.11.23

# The pinned LeRobot integration supplies FLUX 3 training, processors, and inference.
RUN git clone https://github.com/huggingface/lerobot.git /opt/lerobot \
    && cd /opt/lerobot \
    && git checkout --detach 1bc0bdfb20ad4f4f76dc8a68a0e0746d54f50de9 \
    && test "$(git rev-parse HEAD)" = 1bc0bdfb20ad4f4f76dc8a68a0e0746d54f50de9 \
    && /opt/tools/bin/uv sync --locked --extra training --extra flux3 --extra peft --extra diffusion \
    && /opt/tools/bin/uv pip install --python /opt/lerobot/.venv/bin/python \
      'natten==0.21.6+torch2110cu128' --find-links https://whl.natten.org/

ENV PATH="/opt/lerobot/.venv/bin:/opt/tools/bin:${PATH}" \
    HF_HOME=/workspace/cache/huggingface \
    HF_LEROBOT_HOME=/workspace/cache/lerobot \
    PYTHONUNBUFFERED=1
WORKDIR /opt/lerobot
COPY recipe.json calibration.py prepare_dataset.py publish.py train_job.py policy_service.py /app/recipe/
RUN python -c 'import torch, natten, lerobot; assert torch.__version__.startswith("2.11.")'
