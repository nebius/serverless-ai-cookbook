# Build from YOUR immutable image built by ../Dockerfile; no private base dependency.
ARG TRAINING_IMAGE
FROM ${TRAINING_IMAGE}
ARG CHECKPOINT_SHA256
ARG SOURCE_REVISION
USER root
COPY src/fs2_speech /opt/shared-speech/src/fs2_speech
COPY LICENSE NOTICE /opt/shared-speech/
COPY --from=model_bundle /model.nemo /models/domain-asr.nemo
COPY --from=model_bundle /MODEL_CARD.md /models/MODEL_CARD.md
COPY --from=model_bundle /MODEL_LICENSE /models/MODEL_LICENSE
RUN test "${#CHECKPOINT_SHA256}" -eq 64 \
    && printf '%s  /models/domain-asr.nemo\n' "$CHECKPOINT_SHA256" | sha256sum -c - \
    && test "${#SOURCE_REVISION}" -eq 40 \
    && chmod 0444 /models/domain-asr.nemo /models/MODEL_CARD.md /models/MODEL_LICENSE \
    && python -c 'import fastapi,pydantic,torch; from nemo.collections.asr.inference.factory.pipeline_builder import PipelineBuilder'
ENV PYTHONPATH=/opt/shared-speech/src \
    PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 \
    FS2_STT_RUNTIME=speech FS2_STT_REQUIRE_GATEWAY_AUTH=1 \
    FS2_SPEECH_CHECKPOINT_PATH=/models/domain-asr.nemo \
    FS2_SPEECH_CHECKPOINT_SHA256=${CHECKPOINT_SHA256} \
    FS2_SPEECH_PROFILE_JSON='{"model":"nemotron-speech-en-0.6b","chunk_size_ms":560,"strip_language_tags":true,"decoding":"greedy_batch","beam_size":4,"precision":"float32","confidence":false,"cuda_graphs":false}' \
    TORCHINDUCTOR_COMPILE_THREADS=1
USER 10001:10001
WORKDIR /opt/shared-speech
EXPOSE 8000
ENTRYPOINT ["python", "-m", "fs2_speech.serverless_entrypoint"]
CMD []
LABEL org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.opencontainers.image.source="https://github.com/nebius/serverless-ai-cookbook" \
      clinical-speech.scope="shared-worker; gateway required; exact capacity must be qualified"
