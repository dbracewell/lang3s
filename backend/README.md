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
pnpm wipe-db      # reset db/schema + seed support (packages/data/init_db.py)
```

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
