FROM ghcr.io/astral-sh/uv:latest AS uv_bin

FROM python:3.12-bookworm AS builder

RUN apt-get update && apt-get install -y build-essential cargo && rm -rf /var/lib/apt/lists/*
COPY --from=uv_bin /uv /uvx /bin/

WORKDIR /app

ENV HF_HOME=/app/hf
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY backend/jobs_service/ jobs_service
COPY backend/nlp/src/ nlp/src
COPY backend/nlp/README.md nlp/README.md
COPY backend/nlp/pyproject.toml backend/nlp/uv.lock ./nlp/
COPY backend/run.py nlp/
COPY backend/nlp/init_data.py nlp/

WORKDIR /app/nlp
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PATH="/app/nlp/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
RUN python init_data.py


FROM python:3.12-bookworm


ENV HF_HOME=/app/hf
WORKDIR /app/nlp

ENV NODEJS_HOST=http://langs_frontend:3000
ENV PROXY_HOST=http://lang3s_caddy:8003
ENV POSTGRES_DB=lang3s
ENV POSTGRES_USER=admin
ENV POSTGRES_HOST=lang3s_database
ENV REDIS_HOST=lang3s_redis
ENV DEVICE=cpu
ENV PYTHONUNBUFFERED=1
ENV TOKENIZERS_PARALLELISM=false

ENV PATH="/app/nlp/.venv/bin:$PATH"
COPY --from=builder /app /app


CMD ["python", "run.py"]
