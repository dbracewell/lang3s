import logging
import queue
import threading


class AsyncQueueHandler(logging.Handler):
    """Threaded async-safe logging via queue."""

    def __init__(self, handler: logging.Handler):
        super().__init__()
        self.queue = queue.Queue()
        self.handler = handler

        self.listener = threading.Thread(
            target=self._listen, daemon=True
        )
        self.listener.start()

    def _listen(self):
        while True:
            record = self.queue.get()
            if record is None:
                break
            self.handler.emit(record)

    def emit(self, record):
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            pass  # drop logs if overloaded

    def close(self):
        self.queue.put(None)
        super().close()
