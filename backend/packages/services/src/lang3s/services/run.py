import argparse
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional

os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTHONUNBUFFERED"] = "1"
os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.0"

subprocess_env = os.environ.copy()


@dataclass
class Task:
    cmd: str
    arguments: list[str] = field(default_factory=list)
    process: Optional[subprocess.Popen[str]] = None


def start_process(task: Task):
    cmd = ["python", "-u", "-m", task.cmd]
    cmd.extend(task.arguments)
    task.process = subprocess.Popen(
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
    scripts: list[Task] = [
        Task("lang3s.services.apps.main"),
        Task("lang3s.services.apps.analytics"),
        Task(
            "lang3s.services.apps.nlp",
            [
                "--num_workers",
                str(args.num_workers),
                "--batch_size",
                str(args.batch_size),
            ],
        ),
    ]

    try:
        for task in scripts:
            start_process(task)

        while True:
            time.sleep(5)
            for task in scripts:
                if task.process is None or task.process.poll() is not None:
                    print(f"{task.cmd} terminated unexpectedly. Restarting...")
                    start_process(task)

    except KeyboardInterrupt:
        for task in scripts:
            if task.process and task.process.poll() is None:
                task.process.send_signal(signal.SIGINT)
        time.sleep(2)
        for task in scripts:
            if task.process and task.process.poll() is None:
                task.process.terminate()
                task.process.wait()
        return


if __name__ == "__main__":
    main()
