import asyncio
import atexit
import threading
from concurrent.futures import Future
from typing import Any, AsyncGenerator, Coroutine, TypeVar


class BackgroundAsyncRunner:
    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._start_background_loop, daemon=True)
        self._thread.start()

        # Ensure the loop shuts down gracefully when the program exits
        atexit.register(self.shutdown)

    def _start_background_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

        # Clean up pending tasks when run_forever() stops
        pending = asyncio.all_tasks(self._loop)
        for task in pending:
            task.cancel()

        # Run the loop briefly to allow cancellations to process
        self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        self._loop.close()

    def submit(self, coro) -> Future:
        """Thread-safe way to schedule a coroutine."""
        if not self._loop.is_running():
            raise RuntimeError("Background event loop is not running.")
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def run(self, coro, force_sync=False):
        try:
            asyncio.get_running_loop()
            is_async = True
        except RuntimeError:
            is_async = False

        if is_async and not force_sync:
            return coro

        future = self.submit(coro)
        return future.result()

    def shutdown(self):
        """Stops the loop and joins the thread cleanly."""
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=5.0)


runner = BackgroundAsyncRunner()

_ReturnType = TypeVar("_ReturnType")
T = TypeVar("T")


def run_sync(
    coro: Coroutine[Any, Any, _ReturnType],
) -> _ReturnType:
    return runner.run(coro, force_sync=True)


def async_generator_to_sync(
    async_gen: AsyncGenerator[T, None],
):
    try:
        while True:
            try:
                yield runner.run(anext(async_gen), force_sync=True)
            except StopAsyncIteration:
                break
    finally:
        runner.run(async_gen.aclose())
