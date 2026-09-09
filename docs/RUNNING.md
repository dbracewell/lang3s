# Running Lang3s

Lang3s supports two local layouts:

- **macOS:** Docker runs Postgres, Redis, and Inngest. Caddy, Next.js, and all Python/ML services run on the host so PyTorch and `llama-server` can use Apple Silicon Metal/MPS.
- **Linux with NVIDIA CUDA:** Docker runs the complete application stack, including the Python/ML services and frontend.

Run the commands below from the repository root unless a command changes directory.

## Common setup

### Prerequisites

Install the following before running the platform setup command:

- Docker Engine with Docker Compose v2. Docker Desktop is the supported Docker runtime on macOS.
- Node.js 20 or newer, Corepack, and pnpm 12.3.4. The repository declares pnpm through Corepack.
- Python 3.12 and [uv](https://docs.astral.sh/uv/).
- A local copy of the Lang3s artifact bundle. The checked-in `artifacts/` directory is the default bundle used in the examples below.
- macOS only: [Caddy](https://caddyserver.com/docs/install) and a native Metal-enabled `llama-server` on `PATH`.
- Linux only: an NVIDIA driver, NVIDIA Container Toolkit, and a CUDA-capable NVIDIA GPU.

Enable Corepack and confirm the main tools are available:

```bash
corepack enable
node --version
pnpm --version
python3 --version
uv --version
docker compose version
```

The backend requires Python 3.12. Corepack selects the repository's pinned pnpm version (`12.3.4`).

### Run the platform setup

From the repository root, run exactly one of these commands:

```bash
# macOS
pnpm run setup:mac --source ./artifacts

# Linux with NVIDIA CUDA
pnpm run setup:linux --source ./artifacts
```

`--source` can also be a directory outside the checkout or an HTTPS artifact base URL. The source must use the same layout as `artifacts/filestore-manifest.json`, including `models/embedding/` and `models/locallm/`.

The setup command installs JavaScript and Python dependencies, creates local secrets and environment files, synchronizes and verifies the model artifacts, and initializes the platform-specific services. It also runs `pnpm run doctor` before it exits.

Setup is a first-install or full-reset command. It removes the local Docker volumes, generated environment files, Docker secrets, and `filestore/` before rebuilding them. Do not run it against data you need to keep.

The generated configuration uses:

```text
backend/.env
frontend/.env
docker/secrets/
filestore/
```

The frontend and backend receive the same `SYSTEM_KEY`. The generated native configuration points at Postgres on `localhost:5432`, Redis on `localhost:6379`, Inngest on `localhost:8288`, and the Caddy gateway on `localhost:8003`.

## macOS

The macOS setup keeps the application and ML services on the host. This lets native PyTorch use MPS on Apple Silicon and lets the native `llama-server` build use Metal.

### First install

Install Caddy and a native `llama-server`, confirm the server is on `PATH`, and then run:

```bash
llama-server --version
pnpm run setup:mac --source ./artifacts
```

The setup command starts the Docker infrastructure and bootstraps both the backend database and frontend auth database. It does not start the native application processes.

### Start Lang3s

Start the native application stack from the repository root:

```bash
pnpm dev
```

`mprocs` starts Caddy, Next.js, the core API, analytics, NLP, topic, claims, and local LLM services. Open the application at [http://localhost:3000](http://localhost:3000). Caddy serves the browser-facing API at `http://localhost:8003`.

Check that native PyTorch can see Metal on Apple Silicon:

```bash
cd backend
uv run python -c 'import torch; print(torch.backends.mps.is_available())'
cd ..
```

`True` means MPS is available. Individual Python services currently default inference to CPU unless their configuration selects an accelerator; running them natively keeps MPS available.

### Stop and restart

Stop `pnpm dev` with `Ctrl-C`. To stop the Docker infrastructure while keeping its data:

```bash
cd docker
docker compose down
cd ..
```

On a later start, bring the infrastructure back and then start the native stack:

```bash
cd docker
docker compose up -d --wait
cd ..
pnpm dev
```

## Linux with NVIDIA CUDA

The Linux setup runs the complete application in Docker under the `production` profile.

### Verify GPU support

Before running Lang3s, confirm that Docker can access the NVIDIA GPU:

```bash
docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi
```

The command must print the GPU details. If it fails, fix the NVIDIA Container Toolkit or Docker GPU configuration first.

### First install and start

Run:

```bash
pnpm run setup:linux --source ./artifacts
```

The setup command builds the Python image, starts the complete production profile, seeds the named filestore volume, initializes the database and ontology, and checks the installation. Open the application at [http://localhost:3000](http://localhost:3000).

The production containers use the bundled embedding model, GGUF base model, and registered LoRA adapters from the synchronized filestore. The LLM service verifies those artifacts before starting.

### Inspect, stop, and restart

Useful checks:

```bash
cd docker
docker compose --profile production ps
docker compose --profile production logs -f api analytics nlp
docker exec lang3s_api python -c 'import torch; print(torch.cuda.is_available())'
```

The final command should print `True`.

Stop the stack while retaining databases, models, and frontend state:

```bash
docker compose --profile production down
```

Restart it later with:

```bash
docker compose --profile production up -d
```

Appending `-v` deletes the named Postgres, Redis, filestore, Caddy, and frontend-data volumes. Use it only when you intend to reset Docker-managed state.

## Troubleshooting

Run the diagnostic from the repository root:

```bash
pnpm run doctor
```

It checks the Python environment, generated `.env` files and matching system keys, registered model artifacts, `llama-server`, the available native accelerator, Docker/Compose, and Postgres/Redis/Inngest reachability. Use `pnpm run doctor --skip-infra` when Docker infrastructure is intentionally stopped.

- **Missing model or config files:** confirm the artifact source contains the paths listed in `artifacts/filestore-manifest.json`, then run `pnpm run filestore:verify`.
- **Database tables do not exist:** on macOS, run `cd backend && pnpm bootstrap-db`; on Linux, inspect the `db_init` container logs.
- **Frontend cannot reach the API:** confirm `NEXT_PUBLIC_BACKEND_URL=http://localhost:8003` in `frontend/.env`. Browser requests should use the Caddy gateway, not Docker service names.
- **A port is already in use:** the infrastructure uses `5432`, `6379`, `8288`, and `8289`; the application uses `3000` and `8003`.
- **The setup command refuses to replace environment files:** this protects an existing installation. Use the ordinary start commands for that installation, or deliberately rerun setup only after backing up data you need.
