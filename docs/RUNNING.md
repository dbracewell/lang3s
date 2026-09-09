# Running Lang3s

This repository has two supported local layouts:

- **Linux with NVIDIA CUDA:** run the complete stack in Docker.
- **macOS (including Apple Silicon):** run only Postgres, Redis, and Inngest in Docker; run the frontend and all Python/ML processes on the host. This is the default path because native PyTorch can use Metal/MPS directly. Docker Desktop does not expose MPS to Linux containers; alternative runtimes such as Colima with Krunkit may provide Metal-capable container acceleration, but are not assumed by these instructions.

The commands below assume the repository root as the current directory unless they explicitly change directory.

## Common prerequisites

- Node.js 20+ and Corepack/pnpm 12
- Docker Engine plus Docker Compose v2
- Python 3.12 and [uv](https://docs.astral.sh/uv/) for the macOS/native path
- Caddy for the macOS/native path

### Provision model and runtime data

`filestore/` is gitignored. It contains the embedding model and other runtime artifacts, and is required by the NLP, topic, claims, API, and analytics services. Obtain the project filestore from the team/deployment artifact and place it at:

```text
<checkout>/filestore/
```

At minimum, the checked-in services expect `filestore/models/embedding/` to contain the Hugging Face model files (including `config.json` and `model.safetensors`). The Docker data seeder copies this directory into its named `internal_filestore` volume; it cannot create a model from source.

The runtime embedding model, local LLM base model, and registered LoRAs are
pinned in `artifacts/filestore-manifest.json`. Verify them with:

```bash
pnpm run filestore:verify
```

To populate them from a team artifact directory or HTTPS artifact base URL,
use the same relative layout as the manifest:

```bash
pnpm run filestore:sync --source /path/to/lang3s-artifacts
pnpm run filestore:sync --source https://artifacts.example.com/lang3s
```

Each downloaded file is checksum-verified before it replaces the local copy.
The Docker filestore seeder verifies this same manifest before copying artifacts
into its named volume.

### Set secrets and matching application settings

Compose reads five local files from `docker/secrets/local/`:

```text
db_password.txt
inngest_db_password.txt
system_api_key.txt
better_auth_secret.txt
admin_passphrase.txt
```

Generate private local secrets and matching application environments with:

```bash
bash scripts/setup-env.sh mac
# or: bash scripts/setup-env.sh linux
```

It writes ignored files under `docker/secrets/local/`, plus `backend/.env` and
`frontend/.env`, without printing secret values. Existing `.env` files are
preserved; use `--force` to replace them and `--rotate-secrets` to regenerate
the Docker secrets. The `SYSTEM_KEY` in the frontend and backend is identical.

The provided `.env.example` files are the starting point. Use absolute paths for `FILESTORE_ROOT` (for example, `/Users/me/src/Lang3s/filestore` on macOS), and set `POSTGRES_HOST=localhost`, `POSTGRES_PORT=5432`, `POSTGRES_USER=admin`, `REDIS_HOST=localhost`, and `REDIS_PORT=6379` for the native-services layout.

## Linux + NVIDIA CUDA: complete Docker stack

With configured `.env` files and an artifact source, the complete setup is:

```bash
pnpm run setup:linux --source /path/to/lang3s-artifacts
```

`setup:linux` is a first-install command. Its one-shot database initializer
creates a clean schema, seeds the ontology, and clears Redis and analytics
state. Do not use it against a database with data you need to keep.

### Prerequisites

Install an NVIDIA driver and the NVIDIA Container Toolkit, then confirm Docker can use the GPU:

```bash
docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi
```

The repository's Compose file builds the Python image, requests all available NVIDIA GPUs for the ML-serving containers, and starts the complete application under its `production` profile. `api` loads the embedding model during its startup lifecycle; `nlp`, `topic`, and `claims` perform ML work. `lora_llm` launches the bundled GGUF model through `llama-server` with GPU layer offload enabled. Compose requests GPUs for each of these services.

The frontend uses `lang3s_caddy.localhost:8003` as its API origin. That hostname resolves to the host in modern browsers and to Caddy inside Compose, so it works from both places without a local Compose override.

The Python Docker image includes the official CUDA-enabled `llama-server` runtime. At startup, the LLM service verifies that the selected base GGUF and every adapter declared in the local-model registry are present before it launches, and logs the resolved llama-server slot map.

### Start and verify

```bash
cd docker
docker compose --profile production up --build -d
docker compose --profile production ps
```

The one-shot `filestore_seeder` and `db_init` services should finish successfully. The latter creates the schema and seeds the ontology before the application services begin. Open the UI at `http://localhost:3000`; the Docker Caddy gateway is exposed on host ports 80 and 8003 (the latter is used by the browser-facing backend URL).

Useful checks:

```bash
docker compose --profile production logs -f api analytics nlp
docker exec lang3s_api python -c 'import torch; print(torch.cuda.is_available())'
```

The second command should print `True`. If it does not, stop and correct the NVIDIA Container Toolkit/Compose GPU configuration before assuming the ML workers are using CUDA.

To stop while retaining the databases, models, and frontend state:

```bash
docker compose --profile production down
```

Appending `-v` also deletes the named Postgres, Redis, filestore, Caddy, and frontend-data volumes; it is a reset, not a normal shutdown.

## macOS: Docker infrastructure + native app and ML services

With configured `.env` files and an artifact source, setup can be automated:

```bash
pnpm run setup:mac --source /path/to/lang3s-artifacts
```

`setup:mac` is a first-install command. It runs `pnpm wipe-db`, which resets
the public schema, Redis, and analytics state. Do not rerun it after loading
data; use the ordinary macOS startup steps and `pnpm bootstrap-db` instead.

### Install dependencies and configure environments

```bash
pnpm install
cd backend && uv sync --all-packages && cd ..
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Edit the copied files as described in [Set secrets and matching application settings](#set-secrets-and-matching-application-settings). In particular, set both `FILESTORE_ROOT` values to the absolute checkout `filestore` path and use `http://localhost:8003` for `NEXT_PUBLIC_BACKEND_URL` and `PYTHON_SERVER` if you add the latter.

Start only the infrastructure services. Do not pass `--profile production` on macOS: that profile includes Linux application containers and the data seeder.

```bash
cd docker
docker compose up -d
docker compose ps
cd ..
```

This starts Postgres on `5432`, Redis on `6379`, and Inngest on `8288`/`8289`. Inngest calls the native Next.js endpoint through `host.docker.internal:3000`, which Docker Desktop provides on macOS.

Bootstrap the new database once the database health check passes:

```bash
cd backend
pnpm bootstrap-db
cd ..
```

`bootstrap-db` is safe to re-run. Do not use `pnpm wipe-db` unless you intend to drop the public schema and clear Redis/DuckDB state.

### Start the native application stack

`mprocs.yaml` launches Caddy, Next.js, and these Python services: core API, analytics, NLP, topic, claims, and the local LLM server. Install a native Metal-enabled llama.cpp build that provides `llama-server` on `PATH`; it is intentionally independent from Python's `uv` dependencies. Confirm it before starting:

```bash
llama-server --version
```

Then start the stack from the root:

```bash
pnpm dev
```

Open `http://localhost:3000`. Caddy listens on `http://localhost:8003` and routes requests to the native core API (`23000`), analytics API (`23001`), and LLM client (`23002`).

Confirm native PyTorch sees Metal when using Apple Silicon:

```bash
cd backend
uv run python -c 'import torch; print(torch.backends.mps.is_available())'
```

`True` means MPS is available to native PyTorch. The Python configuration currently defaults inference to CPU, but running the processes natively keeps MPS available to code paths that select it and lets `llama-server` use its native Metal build.

To stop the infrastructure while retaining data:

```bash
cd docker
docker compose down
```

## Troubleshooting

Run the environment diagnostic from the repository root before starting the
stack or when a prerequisite is unclear:

```bash
pnpm run doctor
```

It checks Python, `.env` files and matching system keys, the registered local
model and LoRA artifacts, `llama-server`, the available native accelerator,
Docker/Compose availability, and Postgres/Redis/Inngest reachability. Use
`pnpm run doctor --skip-infra` when the
Docker infrastructure is intentionally stopped.

- **Database tables do not exist:** run `cd backend && pnpm bootstrap-db` for native services, or inspect the `db_init` logs for the Docker profile.
- **Model/config file missing:** re-check `FILESTORE_ROOT` and the provisioned `filestore/models/embedding/` files. A fresh clone does not include them.
- **Port already in use:** Docker infrastructure uses `5432`, `6379`, `8288`, and `8289`; the native gateway/UI additionally use `8003` and `3000`.
- **Frontend cannot reach APIs:** native development must use `NEXT_PUBLIC_BACKEND_URL=http://localhost:8003`. The browser cannot resolve Docker-only service names such as `lang3s_caddy`.
