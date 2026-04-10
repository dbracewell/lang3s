import os
import subprocess
import sys
import time

from lang3s.config import config

MODEL_NAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
adapters = {"claim": "claim_extraction.gguf"}
adapter_ids = {v: i for i, v in enumerate(adapters.values())}


def main():
    root = os.path.join(config.MODELS_DIR, "locallm")
    model_path = os.path.join(root, MODEL_NAME)

    # fmt: off
    cmd = [
        "llama-server",
        "--model", model_path,
        "--host", "0.0.0.0",
        "--port", str(config.LOCAL_LLM_PORT),

        "-np", "10",     # Allow 10 parallel requests
        "-c", "80000",   # 80k total context (gives 80k / 10 = 8k context per slot)
        "-b", "1024",

        "-ngl", "99",
        "--chat-template", "chatml",
        "--lora-init-without-apply",

        # 8 bit kv-cache quantization
        "--cache-type-k", "q8_0",
        "--cache-type-v", "q8_0",
    ]

    # fmt: on
    for lora in adapters.values():
        cmd.append("--lora")
        cmd.append(os.path.join(root, "adapters", lora))

    print(f"Server is starting at http://localhost:{config.LOCAL_LLM_PORT}")

    with open("llama_server.log", "w") as log_file:
        server_process = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

        try:
            print(
                "Server is running in the background. Check llama_server.log for details."
            )
            print("Press Ctrl+C to stop the server.")

            while True:
                time.sleep(1)

        except KeyboardInterrupt:
            print("\nReceived exit signal. Shutting down the llama.cpp server...")
            server_process.terminate()
            server_process.wait()
            print("Server stopped cleanly.")


if __name__ == "__main__":
    main()
