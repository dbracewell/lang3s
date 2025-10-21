FROM postgres:17-trixie

ARG PGROONGA_VERSION=4.0.4-1
ARG POSTGRESQL_VERSION=17

RUN set -eux; \
    apt-get update && \
    apt-get install -y -V lsb-release wget ca-certificates gnupg && \
    \
    # --- Add Apache Arrow repo ---
    wget https://apache.jfrog.io/artifactory/arrow/debian/apache-arrow-apt-source-latest-$(lsb_release --codename --short).deb && \
    apt-get install -y -V ./apache-arrow-apt-source-latest-$(lsb_release --codename --short).deb && \
    rm apache-arrow-apt-source-latest-*.deb && \
    \
    # --- Add Groonga repo ---
    wget https://packages.groonga.org/debian/groonga-apt-source-latest-$(lsb_release --codename --short).deb && \
    apt-get install -y -V ./groonga-apt-source-latest-$(lsb_release --codename --short).deb && \
    rm groonga-apt-source-latest-*.deb && \
    \
    # --- Add PostgreSQL PGDG repo (modern method) ---
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
ENV POSTGRES_DB=postgres
ENV POSTGRES_USER=admin
ENV PGDATA=/var/lib/postgresql/data
