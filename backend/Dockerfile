FROM ghcr.io/astral-sh/uv:latest AS uv_bin
FROM ghcr.io/ggml-org/llama.cpp:server-cuda AS llama_cpp
FROM python:3.12-bookworm

RUN apt-get update && apt-get install -y build-essential cargo && rm -rf /var/lib/apt/lists/*
COPY --from=uv_bin /uv /uvx /bin/
COPY --from=llama_cpp /app /opt/llama.cpp

WORKDIR /app/backend

ENV HF_HOME=/app/hf
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    TOKENIZERS_PARALLELISM=false

COPY backend/ /app/backend/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --all-packages --no-dev --no-cache

ENV PATH="/app/backend/.venv/bin:/opt/llama.cpp:$PATH" \
    LD_LIBRARY_PATH="/opt/llama.cpp"

CMD ["python", "-m", "lang3s.services.run"]
