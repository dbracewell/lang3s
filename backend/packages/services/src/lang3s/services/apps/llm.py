import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from logging import Logger
from pathlib import Path

from lang3s.core import config
from lang3s.core.logger import get_logger
from lang3s.llm import get_local_model

logger: Logger = get_logger("LOCAL_LLM")


def main(num_workers: int):
    model = get_local_model()
    root = Path(config.MODELS_DIR) / "locallm"
    model.validate_files(root)
    if shutil.which("llama-server") is None:
        raise RuntimeError(
            "llama-server is not on PATH. Install a native llama.cpp build or "
            "use the Docker image that bundles the CUDA server."
        )
    model_path = root / model.filename

    parallel_factor = num_workers
    # 1024, 2048, 3072, 4,096
    context_window = 4096 * num_workers

    # fmt: off
    cmd = [
        "llama-server",
        "--model", str(model_path),
        "--host", "0.0.0.0",
        "--port", str(config.LOCAL_LLM_PORT),
        "-np", str(parallel_factor),
        "-c", str(parallel_factor * context_window),
        "-b", "256",
        "-ub", "256",
        # "--verbosity", "1", # only log errors
        "-fa", "1",
        "--cont-batching",
        "--no-context-shift",
        "-ngl", "99",
        "--mlock",
        "--prio", "2",
        "-t", "4",
        "--chat-template", "chatml",
        "--lora-init-without-apply",
       "--cache-type-k", "q8_0",
       "--cache-type-v", "q8_0"
    ]

    # fmt: on
    for adapter in model.adapters:
        cmd.append("--lora")
        cmd.append(str(root / "adapters" / adapter.filename))

    adapter_slots = ", ".join(
        f"{index}:{adapter.name}={adapter.filename}"
        for index, adapter in enumerate(model.adapters)
    )
    logger.info(
        f"Starting local model {model.name} ({model.filename}); "
        f"adapter slots: {adapter_slots or 'none'}"
    )
    logger.info(f"Server is starting at http://localhost:{config.LOCAL_LLM_PORT}")
    server_process = None

    def handle_termination(signum, frame):
        if server_process and server_process.poll() is None:
            logger.info("Terminating llama-server...")
            if os.name == "posix":
                try:
                    os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass
            else:
                server_process.terminate()

            server_process.wait()
            logger.info("llama-server terminated")

        if sys.platform != "win32" and sys.platform != "darwin":
            try:
                kill_pattern = f"llama-server.*{config.LOCAL_LLM_PORT}"
                subprocess.run(["pkill", "-f", kill_pattern], check=False)
            except Exception as e:
                logger.error(f"Failed to run pkill cleanup: {e}")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_termination)
    signal.signal(signal.SIGTERM, handle_termination)

    posix_kwargs = {"start_new_session": True} if os.name == "posix" else {}

    server_process = subprocess.Popen(
        cmd,
        **posix_kwargs,
    )

    while True:
        time.sleep(1)
        if server_process.poll() is not None:
            print("llama.cpp terminated unexpectedly. Restarting...")
            server_process = subprocess.Popen(
                cmd,
                **posix_kwargs,
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--num_workers",
        help="The number of worker processes to use",
        default=8,
        type=int,
    )
    args = parser.parse_args()
    main(args.num_workers)
