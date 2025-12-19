FROM python:3.12-bookworm

WORKDIR /app

ARG JOBS_API_KEY
ARG JOB_SERVICE_URL
ARG POSTGRES_PASSWORD
ARG POSTGRES_DB
ARG POSTGRES_USER
ARG POSTGRES_HOST
ARG REDIS_HOST
ARG DEVICE

ENV JOBS_API_KEY=${JOBS_API_KEY}
ENV JOB_SERVICE_URL=${JOB_SERVICE_URL}
ENV POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
ENV POSTGRES_DB=${POSTGRES_DB}
ENV POSTGRES_USER=${POSTGRES_USER}
ENV POSTGRES_HOST=${POSTGRES_HOST}
ENV REDIS_HOST=${REDIS_HOST}
ENV DEVICE=${DEVICE}
ENV PYTHONUNBUFFERED=1

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

#Install supervisord
RUN apt-get update && apt-get install -y supervisor cargo && rm -rf /var/lib/apt/lists/*

RUN pip install poetry

#Install Job Service
COPY jobs_service/ jobs_service
COPY nlp/src/ nlp/src
COPY nlp/pyproject.toml nlp/pyproject.toml
COPY nlp/setup.py nlp/setup.py
COPY nlp/README.md nlp/README.md
WORKDIR /app/nlp/
RUN poetry config virtualenvs.create false
RUN poetry install  --no-root  && rm -rf $POETRY_CACHE_DIR
RUN poetry run python setup.py build_ext --inplace


COPY nlp/models /app/models
ENV MODELS_DIR=models
ENV TOKENIZERS_PARALLELISM=false
COPY run.py /app/nlp/src

ENV VIRTUAL_ENV=/app/nlp/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
WORKDIR /app/nlp/src
CMD ["python", "run.py"]
