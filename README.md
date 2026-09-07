# Lang3s

Lang3s is a multi-service NLP and analytics application with:
- a **Next.js frontend** (`frontend/`)
- a **Python backend workspace** (`backend/`)
- local infrastructure/orchestration in `docker/` and `mprocs.yaml`

> **Status:** Work in progress. APIs, data models, and workflows may change.

## Why this repo is public

This repository is public so others can:
- follow progress
- use pieces of the system
- open issues and propose improvements
- contribute code and docs

## Quick start (local development)

### 1) Install dependencies

From repo root:

```bash
pnpm install
```

### 2) Configure frontend env

```bash
cd frontend
cp .env.example .env
cd ..
```

### 3) Start services

#### Option A (recommended): full local stack with mprocs

```bash
pnpm dev
```

#### Option B: infra with Docker, app services locally

From `docker/`:

```bash
docker compose up -d
```

Then run frontend/backend processes locally as needed.

## Docs by area

- Frontend: `frontend/README.md`
- Backend: `backend/README.md`

## Contributing and community

- Contributing guide: `CONTRIBUTING.md`
- Code of Conduct: `CODE_OF_CONDUCT.md`
- Security policy: `SECURITY.md`

## License

This project is licensed under **GPL-3.0-or-later**. See `LICENSE`.

## CI

GitHub Actions workflows:
- `.github/workflows/frontend-ci.yml`
- `.github/workflows/backend-ci.yml`
