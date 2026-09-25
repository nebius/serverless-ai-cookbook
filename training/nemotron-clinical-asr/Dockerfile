# Public reconstruction: no dependency on an internal Scientific AI image.
FROM pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385
ENV PYTHONUNBUFFERED=1 HF_HOME=/cache/huggingface NUMBA_CACHE_DIR=/cache/numba TORCHINDUCTOR_COMPILE_THREADS=1
RUN apt-get update && apt-get install -y --no-install-recommends git ffmpeg libsndfile1 espeak-ng build-essential && rm -rf /var/lib/apt/lists/*
ADD --checksum=sha256:bef3462da5a6f44a12309bec70359de427f9f31648177bff6ad21cb3afdd64bf https://codeload.github.com/NVIDIA/NeMo/tar.gz/3b08b2acacc13ec1268e53653346266202b2335f /tmp/nemo.tgz
RUN mkdir /opt/nemo && tar -xzf /tmp/nemo.tgz --strip-components=1 -C /opt/nemo && rm /tmp/nemo.tgz
COPY requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock && python -m pip install --no-deps /opt/nemo && python -c 'from nemo.collections.asr.inference.factory.pipeline_builder import PipelineBuilder'
WORKDIR /opt/clinical-asr
COPY clinical_asr ./clinical_asr
ENV PYTHONPATH=/opt/clinical-asr
RUN useradd --uid 10001 --create-home speech \
    && mkdir -p /output /cache /data/clinical-speech \
    && chown -R 10001:10001 /opt/clinical-asr /output /cache /data/clinical-speech
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["python", "-m", "clinical_asr"]
CMD ["serve"]
