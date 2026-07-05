import argparse
import os
import subprocess
import time
from typing import Optional

os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTHONUNBUFFERED"] = "1"
os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.0"

subprocess_env = os.environ.copy()
scripts = []


def start_process(i: int):
    cmd = ["python", "-u", "-m", scripts[i][0]]
    cmd.extend(scripts[i][1])
    return subprocess.Popen(
        cmd,
        text=True,
        bufsize=1,
        env=subprocess_env,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--num_workers",
        help="The number of worker processes to use",
        default=1,
        type=int,
    )
    parser.add_argument(
        "--batch_size",
        help="The number of documents to process in each worker process",
        default=150,
        type=int,
    )
    args = parser.parse_args()
    scripts.append(
        (
            "lang3s.services.worker.annotation_worker",
            [
                "--num_workers",
                str(args.num_workers),
                "--batch_size",
                str(args.batch_size),
            ],
        )
    )
    # scripts.append(("lang3s.services.local_llm_app", []))
    # scripts.append(("lang3s.services.worker.claim_extraction_worker", []))
    scripts.append(("lang3s.services.app", []))
    # scripts.append(("lang3s.services.analytics_app", []))

    processes: list[Optional[subprocess.Popen[str]]] = [None] * len(scripts)
    try:
        for i in range(len(scripts)):
            processes[i] = start_process(i)

        while True:
            time.sleep(5)
            for i, p in enumerate(processes):
                if p.poll() is not None:
                    print(f"{scripts[i]} terminated unexpectedly. Restarting...")
                    processes[i] = start_process(i)
                    print(scripts[i], processes[i].pid)

    except KeyboardInterrupt:
        print("Ctrl+C detected. Terminating all subprocesses...")
        for p in processes:
            if p and p.poll() is None:
                p.terminate()
        time.sleep(2)
        for p in processes:
            if p and p.poll() is None:
                p.kill()
        print("All subprocesses terminated.")


if __name__ == "__main__":
    main()
