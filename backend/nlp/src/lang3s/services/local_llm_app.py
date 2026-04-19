import os
import subprocess
import time

from lang3s.config import config
from lang3s.utils.logger import get_logger

logger = get_logger("LOCAL_LLM")

MODEL_NAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
adapters = {"claim": "claim_extraction.gguf"}
adapter_ids = {v: i for i, v in enumerate(adapters.values())}


def main():
    root = os.path.join(config.MODELS_DIR, "locallm")
    model_path = os.path.join(root, MODEL_NAME)

    parallel_factor = 4
    context_window = 4000

    # fmt: off
    cmd = [
        "llama-server",
        "--model", model_path,
        "--host", "0.0.0.0",
        "--port", str(config.LOCAL_LLM_PORT),

        "-np", str(parallel_factor),
        "-c", str(parallel_factor*context_window),
        "-b", "1024",

        "--verbosity", "1", # only log errors

        "-ngl", "-1",
        "--no-mmap",
        "-t", "8",
        "--chat-template", "chatml",
        "--lora-init-without-apply",

        "--repeat_last_n", "1.2",

        # 8 bit kv-cache quantization
        # "--cache-type-k", "q8_0",
        # "--cache-type-v", "q8_0",
    ]

    # fmt: on
    for lora in adapters.values():
        cmd.append("--lora")
        cmd.append(os.path.join(root, "adapters", lora))

    logger.info(f"Server is starting at http://localhost:{config.LOCAL_LLM_PORT}")

    with open("llama_server.log", "w") as log_file:
        server_process = subprocess.Popen(
            cmd, stdout=log_file, stderr=subprocess.STDOUT
        )

        try:
            while True:
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("\nReceived exit signal. Shutting down the llama.cpp server...")
            server_process.terminate()
            server_process.wait()
            logger.info("Server stopped cleanly.")


if __name__ == "__main__":
    main()
