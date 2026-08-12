# Kokoro-82M TTS server. Pinned base image — no rolling tags.
FROM pytorch/pytorch:2.13.0-cuda12.6-cudnn9-runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HUB_DISABLE_TELEMETRY=1

ENV PIP_BREAK_SYSTEM_PACKAGES=1

# Retries: long builds on flaky archive.ubuntu.com mirrors otherwise die mid-fetch.
RUN printf 'Acquire::Retries "5";\nAcquire::http::Timeout "30";\n' \
      > /etc/apt/apt.conf.d/80-retries \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
      espeak-ng \
      ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
      "kokoro==0.9.4" \
      soundfile==0.13.1 \
      fastapi==0.141.1 \
      uvicorn==0.52.1

WORKDIR /app
COPY serve.py /app/serve.py

EXPOSE 8000
CMD ["python", "serve.py"]
