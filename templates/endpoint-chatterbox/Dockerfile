# Chatterbox TTS server. Pinned base image — no rolling tags.
FROM pytorch/pytorch:2.13.0-cuda12.6-cudnn9-runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HUB_DISABLE_TELEMETRY=1

ENV PIP_BREAK_SYSTEM_PACKAGES=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
      ffmpeg \
      git \
      libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# chatterbox-tts pins torch 2.6; keep the base image CUDA torch and install deps manually.
RUN pip install --no-cache-dir "chatterbox-tts==0.1.7" --no-deps && \
    pip install --no-cache-dir \
      librosa==0.11.0 \
      s3tokenizer \
      transformers==5.2.0 \
      diffusers==0.29.0 \
      conformer==0.3.2 \
      safetensors==0.5.3 \
      spacy-pkuseg \
      pykakasi==2.3.0 \
      pyloudnorm \
      omegaconf \
      "resemble-perth @ git+https://github.com/resemble-ai/Perth.git@master" \
      fastapi==0.141.1 \
      uvicorn==0.52.1 \
      soundfile==0.13.1

WORKDIR /app

# Bundled preset voice for smoke tests (community voice pack; see README).
RUN mkdir -p /app/voices && \
    curl -fsSL -o /app/voices/Emily.wav \
      "https://raw.githubusercontent.com/devnen/Chatterbox-TTS-Server/main/voices/Emily.wav"

COPY serve.py /app/serve.py

EXPOSE 8000
CMD ["python", "serve.py"]
