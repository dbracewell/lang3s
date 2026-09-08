# Lang3s Backend

Python backend workspace for Lang3s.

> Status: work in progress; package boundaries and service contracts may evolve.

It contains multiple internal packages under `backend/packages/*` (core, data, ml, nlp, llm, services, etc.) and service entrypoints used by the frontend and workers.

## Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/)

## Install / sync dependencies

From `backend/`:

```bash
uv sync --all-packages
```

(or from npm script)

```bash
pnpm sync
```

## Environment

Backend reads environment variables from `.env` and Docker secrets.

Current local `.env` includes values like:

- `NODEJS_HOST`
- `POSTGRES_HOST`
- `REDIS_HOST`
- `SYSTEM_KEY`
- `FILESTORE_ROOT`
- optional `LLM_HOST`, `LLM_MODEL`

## Running services

### Option A: full local stack (recommended)

From repo root:

```bash
pnpm dev
```

This uses `mprocs.yaml` to start:

- `lang3s.services.apps.main`
- `lang3s.services.apps.analytics`
- `lang3s.services.apps.nlp`
- `lang3s.services.apps.topic`
- `lang3s.services.apps.claims`
- `lang3s.services.apps.llm`
- plus Caddy and frontend

### Option B: run individual backend services

From `backend/`:

```bash
uv run --package lang3s-services python -m lang3s.services.apps.main
uv run --package lang3s-services python -m lang3s.services.apps.analytics
uv run --package lang3s-services python -m lang3s.services.apps.nlp --num_workers 3 --batch_size 100
uv run --package lang3s-services python -m lang3s.services.apps.topic
uv run --package lang3s-services python -m lang3s.services.apps.claims --num_workers 4
uv run --package lang3s-services python -m lang3s.services.apps.llm
```

## Lint / quality checks

From `backend/`:

```bash
uv run ruff check packages
```

Dependency boundary checks:

```bash
uv run tach check-external
```

## Useful scripts (`backend/package.json`)

```bash
pnpm check-deps   # uv run tach check-external
pnpm sync         # uv sync --all-packages
pnpm bootstrap-db # create schema + seed ontology if missing (packages/data/bootstrap_db.py)
pnpm wipe-db      # reset db/schema + seed support (packages/data/init_db.py)
```

## Database setup

The Postgres schema is created from the SQLAlchemy models (`Base.metadata.create_all`);
Alembic is only used for stamping, there are no migration revisions.
Nothing creates the schema automatically on `docker compose up`, so a fresh stack has an
empty `lang3s` database and the services fail with `relation "..." does not exist` /
`Catalog Error: Table with name ... does not exist`.

```bash
# from backend/: non-destructive, safe to re-run
pnpm bootstrap-db

# destructive: drops the public schema, re-seeds the ontology, clears Redis + DuckDB
pnpm wipe-db
```

With Docker the same bootstrap runs automatically as the one-shot `db_init` compose
service (see `docker/docker-compose.yml`), which gates `api`, `analytics`, `nlp`,
`topic` and `claims`. To run it by hand:

```bash
docker compose --profile production up -d db_init
```

After the schema exists, delete the stale analytics store so DuckDB rebuilds its
views/caches (`/filestore/analytics.duckdb` inside the `lang3s_internal_filestore` volume)
and restart `lang3s_analytics`.

## Package layout

- `packages/core` – shared config, logging, utilities
- `packages/data` – DB models/repositories/schemas, filestore, migrations
- `packages/ml` – ML layers/losses/cluster helpers
- `packages/nlp` – NLP pipeline/components/models
- `packages/llm` – LLM client + tool orchestration helpers
- `packages/services` – FastAPI apps and worker-facing services
- `packages/agent` / `packages/client` – agent logic and client bindings
- `training/` – model/dataset training scripts

## Contributing / license

See root `CONTRIBUTING.md` for contribution workflow and `LICENSE` for terms
(GPL-3.0-or-later).
