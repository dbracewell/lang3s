"""Local runtime diagnostics for Lang3s development environments."""

import argparse
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from dotenv import dotenv_values

from lang3s.core import config
from lang3s.llm import get_local_model


class Doctor:
    def __init__(self) -> None:
        self.failed: bool = False

    def ok(self, message: str) -> None:
        print(f"OK   {message}")

    def warn(self, message: str) -> None:
        print(f"WARN {message}")

    def fail(self, message: str) -> None:
        self.failed = True
        print(f"FAIL {message}")


def check_tcp(doctor: Doctor, label: str, host: str, port: int) -> None:
    try:
        with socket.create_connection((host, port), timeout=2):
            doctor.ok(f"{label} is reachable at {host}:{port}")
    except OSError:
        doctor.fail(f"{label} is not reachable at {host}:{port}")


def check_docker(doctor: Doctor) -> None:
    docker = shutil.which("docker")
    if docker is None:
        doctor.fail("Docker is not on PATH")
        return
    try:
        result = subprocess.run(
            [docker, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        )
        doctor.ok(f"Docker daemon is available ({result.stdout.strip()})")
    except (OSError, subprocess.SubprocessError):
        doctor.fail("Docker daemon is not available")
        return
    try:
        subprocess.run(
            [docker, "compose", "version"],
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        )
        doctor.ok("Docker Compose is available")
    except (OSError, subprocess.SubprocessError):
        doctor.fail("Docker Compose v2 is not available")


def check_inngest(doctor: Doctor, frontend_env: dict[str, str | None]) -> None:
    url = frontend_env.get("INNGEST_URL", "http://localhost:8288")
    if not url:
        doctor.fail("INNGEST_URL is not configured in frontend/.env")
        return
    try:
        parsed = urlparse(url)
        with urlopen(f"{url.rstrip('/')}/health", timeout=2) as response:
            if response.status < 400:
                doctor.ok(f"Inngest is reachable at {parsed.netloc}")
                return
    except OSError:
        pass
    doctor.fail(f"Inngest is not reachable at {url}")


def check_accelerator(doctor: Doctor) -> None:
    try:
        import torch
    except ImportError:
        doctor.fail("PyTorch is not installed")
        return

    if sys.platform == "darwin":
        if torch.backends.mps.is_available():
            doctor.ok("PyTorch MPS is available")
        else:
            doctor.warn("PyTorch MPS is unavailable; ML work will use CPU")
        return

    if sys.platform.startswith("linux"):
        if torch.cuda.is_available():
            doctor.ok(f"PyTorch CUDA is available ({torch.cuda.get_device_name(0)})")
        else:
            doctor.warn("PyTorch CUDA is unavailable; ML work will use CPU")


def check_config(doctor: Doctor, repo_root: Path, check_services: bool) -> None:
    backend_env = dotenv_values(Path.cwd() / ".env")
    frontend_env_path = repo_root / "frontend" / ".env"
    frontend_env = dotenv_values(frontend_env_path)

    if not (Path.cwd() / ".env").is_file():
        doctor.fail("backend/.env is missing; copy backend/.env.example")
    else:
        doctor.ok("backend/.env exists")
    if not frontend_env_path.is_file():
        doctor.fail("frontend/.env is missing; copy frontend/.env.example")
    else:
        doctor.ok("frontend/.env exists")

    backend_key = backend_env.get("SYSTEM_KEY")
    frontend_key = frontend_env.get("SYSTEM_KEY")
    if backend_key and frontend_key and backend_key == frontend_key:
        doctor.ok("backend and frontend SYSTEM_KEY values match")
    else:
        doctor.fail("backend and frontend SYSTEM_KEY values must match")

    if check_services:
        check_inngest(doctor, frontend_env)


def check_llm(doctor: Doctor) -> None:
    model = get_local_model()
    model_directory = Path(config.MODELS_DIR) / "locallm"
    try:
        model.validate_files(model_directory)
        doctor.ok(f"local model artifacts exist for {model.name}")
    except FileNotFoundError as exc:
        doctor.fail(str(exc))

    llama_server = shutil.which("llama-server")
    if llama_server:
        doctor.ok(f"llama-server is on PATH ({llama_server})")
    else:
        doctor.fail("llama-server is not on PATH")

    slots = ", ".join(
        f"{index}:{adapter.name}={adapter.filename}"
        for index, adapter in enumerate(model.adapters)
    )
    doctor.ok(f"local model {model.name} adapter slots: {slots or 'none'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a Lang3s local runtime")
    parser.add_argument(
        "--skip-infra",
        action="store_true",
        help="Skip Postgres, Redis, and Inngest reachability checks",
    )
    args = parser.parse_args()

    doctor = Doctor()
    repo_root = Path.cwd().parent
    if not (repo_root / "frontend").is_dir():
        doctor.fail("Run this command from the backend directory")
        return 1

    if sys.version_info[:2] == (3, 12):
        doctor.ok(f"Python {sys.version.split()[0]}")
    else:
        doctor.fail(f"Python 3.12 is required; found {sys.version.split()[0]}")

    check_config(doctor, repo_root, check_services=not args.skip_infra)
    check_llm(doctor)
    check_accelerator(doctor)

    if not args.skip_infra:
        check_docker(doctor)
        check_tcp(doctor, "Postgres", config.DB_HOST, config.DB_PORT)
        check_tcp(doctor, "Redis", config.REDIS_HOST, config.REDIS_PORT)

    return 1 if doctor.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
