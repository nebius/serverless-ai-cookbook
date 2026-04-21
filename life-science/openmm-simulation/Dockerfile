# Use CUDA 12 runtime image for broad driver compatibility
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    build-essential \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install AWS CLI
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    rm -rf awscliv2.zip aws

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Miniforge (conda-forge)
RUN curl -fsSL \
    "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh" \
    -o /tmp/miniforge.sh && \
    bash /tmp/miniforge.sh -b -p /opt/conda && \
    rm -f /tmp/miniforge.sh

ENV PATH="/opt/conda/bin:/root/.local/bin:$PATH"

# Install OpenMM with GPU support from conda-forge (Option A):
# https://docs.openmm.org/latest/userguide/application/01_getting_started.html
# cuda-version is pinned to 12 to avoid PTX incompatibilities.
RUN conda install -y -c conda-forge --strict-channel-priority \
    "openmm=8.4.*" "cuda-version=12" && \
    conda clean -afy

# Create an unprivileged user to run the simulation. The image itself is
# built as root (needed for apt, conda, AWS CLI install), but the container
# drops to this user for all runtime work.
RUN useradd --create-home --uid 1000 --shell /bin/bash nebius && \
    mkdir -p /openmm/results && \
    chown -R nebius:nebius /openmm

WORKDIR /openmm

# Copy project files with ownership set to the runtime user
COPY --chown=nebius:nebius pyproject.toml .
COPY --chown=nebius:nebius uv.lock .
COPY --chown=nebius:nebius README.md .
COPY --chown=nebius:nebius sim/ ./sim/
COPY --chown=nebius:nebius assets/ ./assets/

# Install the project plus all non-OpenMM dependencies pinned from uv.lock.
# We intentionally keep OpenMM from conda-forge to preserve CUDA platform
# support, so openmm is filtered out of the exported requirements.
RUN uv export --frozen --no-dev --no-hashes --no-emit-project -o /tmp/requirements.txt && \
    sed -i '/^openmm==/d' /tmp/requirements.txt && \
    uv pip install --python /opt/conda/bin/python -r /tmp/requirements.txt && \
    uv pip install --python /opt/conda/bin/python --no-deps .

# Drop privileges before running the simulation
USER nebius

# Define the entrypoint using the modular approach
ENTRYPOINT ["python", "-m", "sim.run"]
