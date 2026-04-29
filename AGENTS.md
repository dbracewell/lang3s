# Lang3s – Agent Guide

## Architecture Overview

Lang3s is an NLP document-analysis platform with three major layers:

| Layer | Tech | Location |
|-------|------|----------|
| Frontend | Next.js 16 + React 19 + tRPC + Drizzle ORM | `frontend/lang3s/` |
| NLP backend | Python / FastAPI (multi-process) | `backend/nlp/` |
| Infrastructure | PostgreSQL 17+PGroonga+pgvector, Redis 7, Caddy, Inngest | `docker/docker-compose.yml` |

Analytics are stored in DuckDB (`filestore/analytics.duckdb`). Document binary blobs live in `filestore/`. Fine-tuned models live in `filestore/models/` and `finetuned_xlm_roberta/`.

## Dev Workflows

### Start everything (preferred)
```bash
# from project root – starts Caddy + NLP backend + Next.js via mprocs
mprocs
```

### Start infrastructure only
```bash
cd docker && docker compose up   # PostgreSQL, Redis, Inngest; omit --profile production to skip NLP containers
```

### Backend NLP (standalone)
```bash
cd backend/nlp
uv run python ../run.py --num_workers 5 --batch_size 100
```
`run.py` is the multiprocess supervisor; it auto-restarts each subprocess on crash.

### Frontend
```bash
cd frontend/lang3s
pnpm dev          # Turbopack dev server on :3000
pnpm drizzle:push # Apply schema changes to Postgres
pnpm seed         # Seed ontology data
```

### Tests (Python)
```bash
cd backend/nlp
uv run pytest
```

## NLP Backend – Internal Architecture

`backend/run.py` spawns **five** subprocesses:

| Module | Role | Port |
|--------|------|------|
| `lang3s.services.worker.annotation_worker` | Batched ML pipeline; reads `annotation_queue` from Redis | — |
| `lang3s.services.worker.claim_extraction_worker` | Reads `claim_extract_queue` | — |
| `lang3s.services.app` | FastAPI: embeddings, topics, agent APIs | 23000 |
| `lang3s.services.analytics_app` | FastAPI: analytics + charts | 23001 |
| `lang3s.services.local_llm_app` | llama-cpp OpenAI-compatible server | 23002 |

**Caddy** (`Caddyfile`, port 8003) routes: `/v1/*` → 23002 (LLM), `/analytics*` & `/charts*` → 23001, all else → 23000.

### NLP Processing Pipeline
Documents flow: **Redis `annotation_queue`** → two-stage NLP:
1. **Core NLP** (`lang3s.nlp.core_nlp`) – spaCy tokenisation/POS/dep-parse, language detection
2. **Heavy NLP** (`lang3s.nlp.heavy_nlp`) – XLM-RoBERTa embeddings, NER (GLiNER), event extraction, coreference

After annotation, workers push document IDs to `claim_extract_queue` (claim extraction) and `db_queue` (DuckDB storage), and update the topic model incrementally.

Workers use `joblib.Parallel(backend="loky")` and recycle processes after **5 cycles** to cap memory growth. All inference is wrapped in `torch.inference_mode()`.

Ontology hot-reload is handled via `ontology_update` Redis pub/sub channel.

### Configuration Priority
`lang3s.config.Config` (singleton `config`) resolves values in order:
1. Docker secret (`/run/secrets/<KEY>`)
2. Postgres `ConfigurationTable` (runtime DB config for LLM settings etc.)
3. Environment variable / `.env`

Default env file is `lang3s_backend.env` (override with `LANG3S_BACKEND_ENV`).

### `Application` base class
CLI scripts subclass `lang3s.app.Application` (a Pydantic `BaseModel`). Fields become argparse arguments automatically; YAML config files can be merged via `--config-file`. Mark a field with `examples=["ignore"]` to exclude it from CLI.

### Local package dependency
`lang3s-job-service` (`backend/jobs_service/`) is an editable local package managed via `uv` workspaces. `JobService` authenticates to the Next.js API using `config.SYSTEM_API_KEY`.

## Frontend Conventions

- **Feature-first layout**: all domain code lives in `src/features/<domain>/` (analytics, documents, ontology, jobs, search, reports, chat, …).
- **tRPC routers** are registered in `src/lib/trpc/routers/_app.ts`; add new routers there.
- **Inngest functions** for background jobs are registered in `src/app/api/inngest/route.ts`.
- State management uses **Jotai** atoms (not Redux/Zustand).
- `@msgpack/msgpack` is used for binary document transport between Python and Next.js.
- Run server-side scripts with `pnpm tsx-server <script>` (sets `react-server` condition + loads `.env`).

## Key Files

| File | Purpose |
|------|---------|
| `backend/run.py` | Master process supervisor |
| `backend/nlp/src/lang3s/config.py` | Singleton config (DB → env fallback chain) |
| `backend/nlp/src/lang3s/pipeline/runner.py` | Core NLP → Heavy NLP orchestration |
| `backend/nlp/src/lang3s/services/client/redis_client.py` | Queue names & Redis helpers |
| `backend/nlp/src/lang3s/app.py` | `Application` base class (Pydantic + argparse) |
| `frontend/lang3s/src/lib/trpc/routers/_app.ts` | tRPC router registry |
| `docker/docker-compose.yml` | All infrastructure services |
| `mprocs.yaml` | Local dev process manager config |

