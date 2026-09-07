# Lang3s Architecture Map

> High-level map of the repository for contributors. This is intentionally concise and may evolve while the project is WIP.

## Monorepo layout

- `frontend/` — Next.js app (UI, auth, API route handlers)
- `backend/` — Python workspace with internal packages and service apps
- `docker/` — local/production-ish infra definitions (Postgres, Redis, Inngest, Caddy, app containers)
- `mprocs.yaml` — local multi-process orchestration for development

## Frontend (Next.js)

Primary responsibilities:
- User/admin UI
- Calling backend APIs through configured gateway
- Auth/session handling
- Triggering background workflows (Inngest integration)

Key paths:
- `frontend/src/features/*` — feature modules
- `frontend/src/components/*` — shared UI components
- `frontend/src/lib/*` — service clients, auth, env, integration code

## Backend (Python workspace)

Workspace package areas under `backend/packages/*`:
- `core` — shared config, logger, utilities
- `data` — DB models/repositories/schemas, filestore integration
- `ml` — ML utilities/layers/losses
- `llm` — LLM client/adapters/tools
- `agent` — agent strategies/session tooling
- `nlp` — NLP pipeline + heavy processing components
- `services` — FastAPI service apps and worker entrypoints
- `client` — Python client bindings/examples

Service entrypoints:
- `lang3s.services.apps.main`
- `lang3s.services.apps.analytics`
- `lang3s.services.apps.nlp`
- `lang3s.services.apps.topic`
- `lang3s.services.apps.claims`
- `lang3s.services.apps.llm`
- orchestration runner: `lang3s.services.run`

## Runtime topology (local)

Typical local flow:
1. Frontend runs on `:3000`
2. Caddy/gateway exposes backend routes on `:8003`
3. Python services run behind gateway (`services.apps.*`)
4. Postgres stores app data
5. Redis supports queues/cache/event flow
6. Inngest handles async/event-driven workflows

## Data & model artifacts

- Local artifacts are expected under `filestore/` (ignored in git)
- Large model/data files should **not** be committed to the repository

## CI map

- `frontend-ci.yml` — frontend lint/typecheck/build
- `backend-ci.yml` — backend lint (Ruff)
- `security-ci.yml` — secret scan + dependency vulnerability checks

## Where to start contributing

- Pick issues labeled `good first issue` or `help wanted`
- Start with docs, tests, or isolated frontend/backend fixes
- For larger changes, open an issue/discussion before implementation
