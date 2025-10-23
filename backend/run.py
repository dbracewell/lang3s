import os
import subprocess
import time
from typing import List, Optional, cast

os.environ["TRANSFORMERS_VERBOSITY"] = "error"

scripts = ["lang3s.workers.nlp_worker", "lang3s.services.embedding_server"]
processes: List[Optional[subprocess.Popen[str]]] = [None] * len(scripts)


def start_process(i: int):
    return subprocess.Popen(["python", "-m", scripts[i]], text=True)


try:
    for i in range(len(scripts)):
        processes[i] = start_process(i)
        print(scripts[i], cast(subprocess.Popen[str], processes[i]).pid)

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
