# syntax=docker/dockerfile:1.7
# QA image: BioContainers/Bioconda is the canonical maintained hap.py
# distribution. The long-stale pkrusche/hap.py Docker Hub images use a
# deprecated manifest v1 schema that modern Docker refuses to pull.
FROM quay.io/biocontainers/hap.py:0.3.15--py27hcb73b3d_0

USER root

# BioContainers ships hap.py under a Python 2.7 Conda env. We add a
# Python 3 venv for our validate.py wrapper so it never collides with
# the conda environment hap.py itself runs in.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv ca-certificates wget \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/qa-venv \
    && /opt/qa-venv/bin/pip install --no-cache-dir boto3

ENV PATH="/opt/qa-venv/bin:${PATH}"

WORKDIR /opt/qa
COPY validate.py ./

# hap.py resolves from PATH via the BioContainers conda env
# (/usr/local/bin/hap.py).
ENTRYPOINT ["/opt/qa-venv/bin/python", "validate.py"]
