# CUDA 12.6 runtime on Ubuntu 22.04.
# uv manages Python 3.12 and all Python dependencies,
# following https://huggingface.co/docs/lerobot/installation (v0.5.1, uv path).
FROM nvidia/cuda:12.6.3-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

# ── System packages ──────────────────────────────────────────────────────────
# Ordered by origin in the LeRobot installation docs:
#
# Troubleshooting section — required when building C extensions (evdev, PyAV):
#   cmake build-essential python3-dev pkg-config libavformat-dev libavcodec-dev
#   libavdevice-dev libavutil-dev libswscale-dev libswresample-dev libavfilter-dev
#
# Step 2 (ffmpeg) — system-wide ffmpeg for TorchCodec ≥ 0.10 / PyTorch ≥ 2.10:
#   ffmpeg
#
# Step 2 (evdev on Linux) — gym-pusht pulls evdev as a transitive dependency;
#   libevdev-dev provides the Linux kernel headers evdev compiles against:
#   libevdev-dev
#
# Extra — headless rendering needed when gym environments render frames:
#   libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake \
    build-essential \
    python3-dev \
    pkg-config \
    git \
    ffmpeg \
    libevdev-dev \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libavfilter-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    curl \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── AWS CLI v2 ────────────────────────────────────────────────────────────────
# Used for S3 result verification; boto3 handles the actual upload.
RUN curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip && \
    unzip /tmp/awscliv2.zip -d /tmp && \
    /tmp/aws/install && \
    rm -rf /tmp/awscliv2.zip /tmp/aws

# ── uv ───────────────────────────────────────────────────────────────────────
# Docs: recommended package manager for the non-conda path.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /lerobot
RUN mkdir -p outputs

# ── Copy dependency files early for layer caching ─────────────────────────────
COPY pyproject.toml ./

# ── Python 3.12 virtual environment via uv ────────────────────────────────────
RUN uv python install 3.12 && uv venv --python 3.12 .venv
ENV VIRTUAL_ENV=/lerobot/.venv
ENV PATH="/lerobot/.venv/bin:$PATH"

# ── Sync dependencies (runtime only) ─────────────────────────────────────────
ENV UV_INDEX_STRATEGY=unsafe-best-match
RUN uv sync --no-dev --python 3.12 --index-strategy unsafe-best-match

# ── Entrypoint assets ─────────────────────────────────────────────────────────
COPY train/ ./train/
COPY configs/ ./configs/

ENTRYPOINT ["python", "-m", "train.run"]
