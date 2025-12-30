# Repository Guidelines

## Project Structure & Module Organization

- `frontend/lang3s` – Next.js App Router; pages in `src/app`, shared UI in `src/components`, Drizzle schema/migrations
  in `drizzle/`, dev scripts in `scripts/`.
- `frontend/website` – static one-pager served directly from `index.html`.
- `backend/nlp` – FastAPI entry (`lang3s/services/app.py`), batched worker (`services/nlp_worker.py`), and the NLP
  pipeline/embeddings/topic models under `src/lang3s/`.
- `backend/jobs_service` – Pydantic client plus ingestion CLI (`annotate.py`) that posts jobs consumed by the worker.
- Datasets reside in `documents/`; infra/bootstrap assets live in `docker-compose.yml`, `postgres/`, and
  `backend/run.py`.

## Build, Test, and Development Commands

- UI: `cd frontend/lang3s && pnpm install && pnpm dev`; build + serve through `pnpm build && pnpm start`.
- Utilities: `pnpm seed` seeds ontology data, `pnpm check_redis` verifies cache connectivity before enabling dashboards.
- Backend: `cd backend/nlp && poetry install`, then `python ../run.py` to start both FastAPI and workers; target a
  single endpoint with `poetry run uvicorn lang3s.services.app:app --reload --port 8003`.
- Services: `docker compose up database redis` (add `inngest` when running workflows).
- Verification: `poetry run pytest` exercises backend logic, while `pnpm lint` and `pnpm prettier --write <files>` gate
  UI changes.

## Coding Style & Naming Conventions

- TypeScript follows ESLint’s Next.js core-web-vitals rules: 2-space indentation, PascalCase components, camelCase
  hooks, colocated route handlers, and Tailwind classes kept in Prettier-sorted order.
- Python code uses 4-space indents, type hints, and shared Pydantic models from `lang3s/shared_types`; prefer
  descriptive filenames and confine side effects to `lang3s/services/`.

## Testing Guidelines

- Pytest is the canonical harness; mirror `backend/nlp/src/lang3s/test.py`, name suites `test_<feature>.py`, and reuse
  helpers like `lang3s.db.TextDatabase` or `lang3s_job_service.File` for fixtures.
- Frontend changes must pass `pnpm lint`; add React Testing Library or Playwright specs under
  `frontend/lang3s/src/__tests__` for significant UI logic.
- Document evaluation datasets or prompt files in `documents/` so reviewers can rerun metrics.

## Commit & Pull Request Guidelines

- Commits stay short and imperative (“Refactor types to shared_types”), optionally scoped (`frontend:`, `nlp:`).
- PRs should link issues, summarize schema/data impacts, and attach screenshots or CLI output for UX- or
  ingestion-facing behavior.
- Highlight new t3env vars, Docker args, or migrations in a checklist to speed reviewer setup.

## Environment & Data Notes

- Copy `.t3env.example` to `.t3env`, avoid committing secrets, and use direnv or `pnpm t3env` for overrides.
- Large corpora in `documents/` are unsynced; mention additions in PRs and set the `DEVICE` t3env so
  `backend/Dockerfile` selects the correct ARM or NVIDIA build profile.
