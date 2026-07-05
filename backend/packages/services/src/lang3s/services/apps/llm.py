import os
import signal
import subprocess
import sys
import time

from lang3s.core import config
from lang3s.core.logger import get_logger
from lang3s.llm import adapters

logger = get_logger("LOCAL_LLM")

MODEL_NAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"


def main():
    root = os.path.join(config.MODELS_DIR, "locallm")
    model_path = os.path.join(root, MODEL_NAME)

    parallel_factor = 4
    # 1024, 2048, 3072, 4,096
    context_window = 4096 * 4

    # fmt: off
    cmd = [
        "llama-server",
        "--model", model_path,
        "--host", "0.0.0.0",
        "--port", str(config.LOCAL_LLM_PORT),
        "-np", str(parallel_factor),
        "-c", str(parallel_factor * context_window),
        "-b", "2048",
        "-ub", "2048",
        # "--verbosity", "1", # only log errors
        "-fa", "1",
        "--cont-batching",
        "--no-context-shift",
        "-ngl", "99",
        "--mlock",
        "--prio", "2",
        "--chat-template", "chatml",
        "--lora-init-without-apply",
        # "--cache-type-k", "q8_0",
        # "--cache-type-v", "q8_0",
    ]

    # fmt: on
    for lora in adapters.values():
        cmd.append("--lora")
        cmd.append(os.path.join(root, "adapters", lora))

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
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_termination)
    signal.signal(signal.SIGTERM, handle_termination)

    posix_kwargs = {"start_new_session": True} if os.name == "posix" else {}

    with open("llama_server.log", "w") as log_file:
        server_process = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            **posix_kwargs,
        )

        while True:
            time.sleep(1)
            if server_process.poll() is not None:
                print("llama.cpp terminated unexpectedly. Restarting...")
                server_process = subprocess.Popen(
                    cmd,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    **posix_kwargs,
                )


if __name__ == "__main__":
    main()
