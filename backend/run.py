import os
import subprocess
import time
from typing import List, Optional, cast

os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTHONUNBUFFERED"] = "1"

WORKER_COUNT = int(os.environ.get("WORKER_COUNT", 3))

subprocess_env = os.environ.copy()

scripts = ["lang3s.services.nlp_worker"] * WORKER_COUNT
scripts.append("lang3s.services.app")

processes: List[Optional[subprocess.Popen[str]]] = [None] * len(scripts)


def start_process(i: int):
    return subprocess.Popen(
        ["python", "-m", scripts[i]], text=True, bufsize=1, env=subprocess_env
    )


try:
    for i in range(len(scripts)):
        processes[i] = start_process(i)

    while True:
        time.sleep(1)
        for i, p in enumerate(processes):
            if cast(subprocess.Popen[str], p).poll() is not None:
                print(f"{scripts[i]} terminated unexpectedly. Restarting...")
                processes[i] = start_process(i)
                print(scripts[i], cast(subprocess.Popen[str], processes[i]).pid)

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
