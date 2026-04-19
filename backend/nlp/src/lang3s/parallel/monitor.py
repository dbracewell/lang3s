import multiprocessing as mp
import threading
import time
from typing import Callable

from lang3s.parallel.core import safe_process
from lang3s.utils.logger import get_logger

logger = get_logger("PROCESS_MONITOR")


class ThreadMonitor:
    def __init__(self):
        self._threads: list[threading.Thread] = []
        self._running = False
        self._stop_event = threading.Event()

    def add(self, func: Callable, args: tuple):
        thread = threading.Thread(
            target=self._wrap,
            args=(func, args),
            name=f"worker-{len(self._threads)}",
            daemon=True,
        )
        self._threads.append(thread)

        if self._running:
            thread.start()

    def _wrap(self, func, args):
        try:
            func(self._stop_event, *args)
        except Exception as e:
            print(f"[ERROR] {threading.current_thread().name}: {e}")

    def start(self):
        self._running = True
        for thread in self._threads:
            if not thread.is_alive():
                thread.start()

    def status(self):
        return [(t.name, t.is_alive()) for t in self._threads]

    def shutdown(self, timeout=None):
        self._stop_event.set()
        for t in self._threads:
            t.join(timeout=timeout)


class ProcessMonitor:
    def __init__(self):
        self._processes: list[mp.Process] = []
        self._calls = []

    def add(self, func: Callable, args: tuple):
        self._calls.append((func, args))
        self._processes.append(safe_process(func, args))

    def start(self):
        for p in self._processes:
            p.start()

    def keep_alive(self):
        while True:
            time.sleep(5)
            for i, p in enumerate(self._processes):
                if not p.is_alive():
                    logger.warn(f"Process {p.pid} died, restarting...")
                    self._processes[i] = safe_process(
                        self._calls[i][0], self._calls[i][1]
                    )
                    self._processes[i].start()

    def shutdown(self):
        for p in self._processes:
            if p.is_alive():
                p.join()
