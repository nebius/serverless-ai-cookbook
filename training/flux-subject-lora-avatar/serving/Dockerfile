# FLUX.2-dev + LoRA serving image (solo subject mode).
# Flux2Pipeline is available in diffusers >= 0.36.0.
FROM pytorch/pytorch:2.9.1-cuda12.8-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HUB_ENABLE_HF_TRANSFER=1 \
    HF_HOME=/cache/hf \
    HOME=/tmp

RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir \
      diffusers==0.39.0 \
      transformers==4.57.6 \
      accelerate==1.14.0 \
      peft==0.19.1 \
      sentencepiece \
      protobuf \
      safetensors \
      fastapi==0.139.2 \
      "uvicorn[standard]==0.51.0" \
      pillow \
      boto3 \
      huggingface_hub \
      hf_transfer && \
    python -c "from diffusers import Flux2Pipeline; import peft, boto3; print('import check ok')"

COPY server.py /app/server.py
WORKDIR /app
RUN mkdir -p /cache && chmod -R 777 /cache

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
