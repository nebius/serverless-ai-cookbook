# syntax=docker/dockerfile:1.7
# Pipeline image: extends NVIDIA Parabricks 4.7 with the S3 staging wrapper.
ARG NGC_TAG=4.7.0-1
FROM nvcr.io/nvidia/clara/clara-parabricks:${NGC_TAG}

# Parabricks ships on Ubuntu 22.04. Add only what we need on top.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/pipeline

# Install boto3 from a frozen lockfile via uv (deterministic; mirrors openmm-simulation).
RUN pip install --no-cache-dir uv==0.4.* && \
    uv --version

COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project -o /tmp/requirements.txt && \
    pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

COPY pipeline/ ./pipeline/

# Run as root: pbrun requires it for /dev/nvidia* device access without
# extra container privilege flags. Rationale: Parabricks 4.7 is documented
# to run as the default container user on every supported cloud, and
# Nebius AI Jobs does not currently expose the supplemental groups needed
# to drop privileges cleanly. See spec §3 (Constraints) and §12 (Risks).

ENTRYPOINT ["python3", "-m", "pipeline.cli"]
