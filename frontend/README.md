# Lang3s Frontend

This is the Next.js frontend for Lang3s.

> Status: work in progress; APIs and UI behavior may change.

It provides:
- Authentication and user/admin UI (Better Auth)
- Search, documents, analytics, reports, ontology, jobs, and system pages
- API route handlers for auth, Inngest, realtime/events, and API-key verification

## Stack

- Next.js (App Router)
- React + TypeScript
- Tailwind CSS
- TanStack Query
- Better Auth (SQLite for auth DB)

## Prerequisites

- Node.js 20+
- pnpm

## Environment

Copy and edit:

```bash
cp .env.example .env
```

Key variables:
- `NEXT_PUBLIC_APP_URL`: frontend URL (usually `http://localhost:3000`)
- `NEXT_PUBLIC_BACKEND_URL`: backend gateway URL (usually `http://localhost:8003`)
- `PYTHON_SERVER`: backend gateway URL used server-side
- `INNGEST_URL`: Inngest URL
- Auth + system keys (`BETTER_AUTH_SECRET`, `SYSTEM_KEY`, etc.)

## Running the frontend

From this folder:

```bash
pnpm install
pnpm dev
```

Frontend runs on `http://localhost:3000`.

---

## Services required by the frontend

The frontend depends on backend services for most functionality.

### Required for core UI flows

1. **Backend API gateway** at `http://localhost:8003`
   - Proxied by Caddy
   - Config: `../Caddyfile`

2. **Python API services** behind the gateway
   - Core API (`:23000`)
   - Analytics API (`:23001`)
   - (Optional for chat/LLM features) local LLM service (`:23002`)

3. **Redis** (used by background/event features)

4. **Postgres** (used by backend services)

5. **Inngest** (for event/workflow integration)

---

## Easiest way to run everything

From repo root (`../`):

```bash
pnpm dev
```

This uses `mprocs` (`../mprocs.yaml`) to launch:
- Caddy gateway
- Python services
- Next.js frontend

---

## Docker services you can run

Infra/services are defined in:
- `../docker/docker-compose.yml`
- `../docker/Caddyfile`

From `../docker` you can start dependencies like Postgres, Redis, and Inngest:

```bash
docker compose up -d
```

Note: some services in `docker-compose.yml` are under the `production` profile.

If you run frontend + backend locally (outside Docker), keep `NEXT_PUBLIC_BACKEND_URL` and `PYTHON_SERVER` pointed at `http://localhost:8003` and run Caddy with `../Caddyfile`.

## Useful scripts

```bash
pnpm dev        # next dev --turbopack
pnpm build      # production build
pnpm start      # start production server
pnpm lint       # eslint
pnpm codegen    # regenerate OpenAPI clients
```

## Contributing / license

See root `CONTRIBUTING.md` for contribution workflow and `LICENSE` for terms
(GPL-3.0-or-later).
