FROM ghcr.io/astral-sh/uv:0.9.28-python3.11-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
ENV PATH="/app/.venv/bin:$PATH"
ENV PORT=8000

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY bionemo_agent/ ./bionemo_agent/
COPY configs/ ./configs/

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["sh", "-c", "nat serve --config_file configs/config.yml --host 0.0.0.0 --port ${PORT}"]
