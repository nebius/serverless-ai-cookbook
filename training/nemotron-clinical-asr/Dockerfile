# Public immutable dependencies; no private checkpoint or platform grant.
FROM pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385
ENV PYTHONUNBUFFERED=1 HF_HOME=/cache/huggingface NUMBA_CACHE_DIR=/cache/numba TORCHINDUCTOR_COMPILE_THREADS=1
RUN apt-get update && apt-get install -y --no-install-recommends git ffmpeg libsndfile1 espeak-ng build-essential && rm -rf /var/lib/apt/lists/*
ADD --checksum=sha256:bef3462da5a6f44a12309bec70359de427f9f31648177bff6ad21cb3afdd64bf https://codeload.github.com/NVIDIA/NeMo/tar.gz/3b08b2acacc13ec1268e53653346266202b2335f /tmp/nemo.tgz
RUN mkdir /opt/nemo && tar -xzf /tmp/nemo.tgz --strip-components=1 -C /opt/nemo && rm /tmp/nemo.tgz
ADD --checksum=sha256:709f6f96c9813fec542a023036d9b06ab8f0f4ec817640d2e06962a5ce920c2e https://codeload.github.com/rene-tech/serverless-ai-cookbook/tar.gz/db9e31e3ce4f760804b448a846101797111594fa /tmp/dependencies.tgz
RUN mkdir /tmp/dependencies && tar -xzf /tmp/dependencies.tgz --strip-components=1 -C /tmp/dependencies \
    && python -m pip install --no-cache-dir --require-hashes -r /tmp/dependencies/training/nemotron-clinical-asr/requirements.lock \
    && python -m pip install --no-deps /opt/nemo \
    && rm -rf /tmp/dependencies /tmp/dependencies.tgz
COPY train.py /opt/recipe/train.py
RUN useradd --uid 10001 --create-home speech \
    && mkdir -p /cache /data \
    && chown 10001:10001 /cache /data
USER 10001:10001
ENTRYPOINT ["python", "/opt/recipe/train.py"]
