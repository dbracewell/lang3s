FROM python:3.13-slim

WORKDIR /app

#Install supervisord
RUN apt-get update && apt-get install -y supervisor cargo && rm -rf /var/lib/apt/lists/*

#Install requirements
COPY requirements.txt .
RUN pip install -r requirements.txt

#Download Spacy Models
RUN python -m spacy download en_core_web_sm
RUN python -m spacy download ja_core_news_sm
RUN python -m spacy download es_core_news_sm

#Copy core models
COPY models models
ENV MODELS_DIR=models
#Install base model
COPY load_base_model.py .
RUN python load_base_model.py && rm load_base_model.py

#Copy project, install, and remove unneeded source
COPY lang3s src/lang3s
COPY pyproject.toml src/pyproject.toml
RUN  cd src && pip install  . &&  rm -rf src/


#Copy config files
COPY docker_config/supervisord.conf .
CMD ["supervisord", "-c", "/app/supervisord.conf"]
