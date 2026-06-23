import logging
import queue
import sys
import threading

from uvicorn.logging import DefaultFormatter


class AsyncQueueHandler(logging.Handler):
    """Threaded async-safe logging via queue."""

    def __init__(self):
        super().__init__()
        self.queue = queue.Queue()
        self.handler = logging.StreamHandler(sys.stdout)
        self.handler.setLevel(logging.DEBUG)
        self.handler.setFormatter(
            DefaultFormatter(
                fmt="%(levelprefix)s %(asctime)s | %(name)s | %(message)s",
                use_colors=True,
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        self.listener = threading.Thread(target=self._listen, daemon=True)
        self.listener.start()

    def _listen(self):
        while True:
            record = self.queue.get()
            if record is None:
                continue
            self.handler.emit(record)

    def emit(self, record):
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            pass  # drop logger if overloaded

    def close(self):
        self.queue.put(None)
        super().close()
