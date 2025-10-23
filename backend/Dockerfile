FROM python:3.13-slim

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


#Install supervisord
RUN apt-get update && apt-get install -y supervisor cargo && rm -rf /var/lib/apt/lists/*

#Install Job Service
COPY jobs_service/src/lang3s_job_service src/lang3s_job_service
COPY jobs_service/pyproject.toml .
RUN  pip install . &&  rm -rf src/

#Install requirements
COPY nlp/requirements.txt .
RUN pip install -r requirements.txt

#Copy core models
COPY nlp/models models
ENV MODELS_DIR=models

#Install base model
COPY nlp/load_base_model.py .
RUN python load_base_model.py && rm load_base_model.py

#Copy project, install, and remove unneeded source
COPY nlp/src/lang3s src/lang3s
COPY nlp/pyproject.toml .
RUN  pip install  . &&  rm -rf src/

ENV TOKENIZERS_PARALLELISM=false
COPY run.py .
CMD ["python", "run.py"]
