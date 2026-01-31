FROM postgres:17-trixie

ARG PGROONGA_VERSION=4.0.4-1
ARG POSTGRESQL_VERSION=17
ARG POSTGRES_DB
ARG POSTGRES_USER

RUN set -eux; \
    apt-get update && \
    apt-get install -y -V lsb-release wget ca-certificates gnupg \
		&& \
    \
    wget https://apache.jfrog.io/artifactory/arrow/debian/apache-arrow-apt-source-latest-$(lsb_release --codename --short).deb && \
    apt-get install -y -V ./apache-arrow-apt-source-latest-$(lsb_release --codename --short).deb && \
    rm apache-arrow-apt-source-latest-*.deb && \
    \
    wget https://packages.groonga.org/debian/groonga-apt-source-latest-$(lsb_release --codename --short).deb && \
    apt-get install -y -V ./groonga-apt-source-latest-$(lsb_release --codename --short).deb && \
    rm groonga-apt-source-latest-*.deb && \
    \
    install -d /etc/apt/keyrings; \
    wget -qO /etc/apt/keyrings/pgdg.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc; \
    echo "deb [signed-by=/etc/apt/keyrings/pgdg.asc] http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list; \
    \
    apt-get update && \
    apt-get install -y -V \
      postgresql-${POSTGRESQL_VERSION}-pgdg-pgroonga=${PGROONGA_VERSION} \
      postgresql-${POSTGRESQL_VERSION}-pgvector \
      groonga-normalizer-mysql \
      groonga-token-filter-stem \
      groonga-tokenizer-mecab && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Environment variables are set at runtime (via docker-compose)
ENV POSTGRES_DB=${POSTGRES_DB}
ENV POSTGRES_USER=${POSTGRES_USER}
ENV PGDATA=/var/lib/postgresql/data


CMD ["postgres", "-c", "maintenance_work_mem=${MAINTENCE_WORK_MEM:-2}gb", "-c", "max_parallel_maintenance_workers=${MAX_PARELLISM:-4}"]

