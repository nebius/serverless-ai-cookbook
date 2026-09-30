# Set to the immutable image built by ../../training/nemotron-clinical-asr.
ARG TRAINING_IMAGE
FROM ${TRAINING_IMAGE}
USER root
ADD --checksum=sha256:709f6f96c9813fec542a023036d9b06ab8f0f4ec817640d2e06962a5ce920c2e https://codeload.github.com/rene-tech/serverless-ai-cookbook/tar.gz/db9e31e3ce4f760804b448a846101797111594fa /tmp/runtime.tgz
RUN mkdir /tmp/runtime /opt/shared-speech \
    && tar -xzf /tmp/runtime.tgz --strip-components=1 -C /tmp/runtime \
    && cp -r /tmp/runtime/training/nemotron-clinical-asr/shared-runtime/src /opt/shared-speech/ \
    && cp /tmp/runtime/training/nemotron-clinical-asr/shared-runtime/LICENSE /tmp/runtime/training/nemotron-clinical-asr/shared-runtime/NOTICE /opt/shared-speech/ \
    && rm -rf /tmp/runtime /tmp/runtime.tgz
COPY serve.py /opt/recipe/serve.py
ENV PYTHONPATH=/opt/shared-speech/src
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["python", "/opt/recipe/serve.py"]
