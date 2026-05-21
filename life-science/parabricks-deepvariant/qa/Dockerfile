# syntax=docker/dockerfile:1.7
# QA image: BioContainers/Bioconda is the maintained hap.py distribution.
# The long-stale pkrusche/hap.py Docker Hub images use a deprecated manifest v1
# schema that modern Docker refuses to pull. We copy the BioContainers hap.py
# toolchain into a Python 3 image so validate.py can use current boto3 without
# colliding with hap.py's Python 2 runtime.
FROM quay.io/biocontainers/hap.py:0.3.15--py27hcb73b3d_0 AS happy

FROM python:3.11-slim-bookworm

COPY --from=happy /usr/local /opt/happy

ENV PATH="/opt/happy/bin:${PATH}"

RUN python3 -m pip install --no-cache-dir 'boto3==1.43.6'

# Keep plain `python` on Python 3 for smoke checks and wrapper tooling, but run
# hap.py itself with the Python 2.7 runtime bundled in the BioContainers image.
RUN printf '%s\n' \
        '#!/bin/sh' \
        'export PATH="/opt/happy/bin:${PATH}"' \
        'exec /opt/happy/bin/python2.7 /opt/happy/bin/hap.py "$@"' \
        > /usr/local/bin/hap.py \
    && chmod +x /usr/local/bin/hap.py

ENV PATH="/usr/local/bin:/opt/happy/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin"

WORKDIR /opt/qa
COPY validate.py ./

# validate.py runs on the base image's Python 3 runtime; the hap.py wrapper above
# dispatches to BioContainers' Python 2 runtime for hap.py internals.
ENTRYPOINT ["/usr/local/bin/python3", "validate.py"]
