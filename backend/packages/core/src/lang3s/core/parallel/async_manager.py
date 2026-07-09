import asyncio
import inspect
import queue
import signal
import sys
import threading
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Coroutine,
    Optional,
    ParamSpec,
    TypeVar,
)

from .threading_manager import BasicQueueSource
from .typedefs import (
    BaseManager,
    Event,
    JobCompleteEvent,
    QueueSource,
    StopEvent,
    SubmittableTask,
)

P = ParamSpec("P")
R = TypeVar("R")


class AsyncQueueSource[T](BasicQueueSource[T]):
    def job_complete(self, job_id: int) -> None:
        self.put(JobCompleteEvent(job_id=job_id))


class AsyncManager(BaseManager):
    def __init__(self, workers: int) -> None:
        super().__init__(workers)
        self._tasks: list[asyncio.Task] = []
        self._threads: list[threading.Thread] = []
        self.shutdown_event = asyncio.Event()
        self._register_signals()

    def _register_signals(self):
        loop = asyncio.get_running_loop()
        try:
            loop.add_signal_handler(signal.SIGINT, self._handle_sigint)  # type:ignore
            loop.add_signal_handler(signal.SIGTERM, self._handle_sigint)  # type:ignore
        except NotImplementedError:
            pass  # Windows fallback

    def _handle_sigint(self):
        if self.shutdown_event.is_set():
            sys.exit(1)
        self.shutdown_event.set()

    async def shutdown(self) -> None:
        self.shutdown_event.set()

        for task in self._tasks:
            task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        for thread in self._threads:
            await asyncio.to_thread(thread.join, timeout=2.0)
            if thread.is_alive():
                print(f"Warning: Thread {thread.name} refused to die.")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.shutdown()

    def create_queue(self, maxsize: int = 0) -> BasicQueueSource[Any]:
        return AsyncQueueSource(workers=self._workers, maxsize=maxsize)

    def submit(
        self,
        target: SubmittableTask,
        *args,
        **kwargs,
    ) -> None:
        t = threading.Thread(
            target=target,
            args=(self.shutdown_event, *args),
            kwargs=kwargs,
        )
        t.daemon = True
        t.start()
        self._threads.append(t)

    async def imap(
        self,
        func: Callable[P, Coroutine[Any, Any, Event[R]]],
        source_queue: QueueSource[Event[R]],
        init_worker: Optional[Callable[..., Any]] = None,
        init_worker_args: tuple = (),
        on_job_complete: Callable[[JobCompleteEvent], Coroutine[Any, Any, None]]
        | None = None,
    ) -> AsyncGenerator[Event, None]:
        if not inspect.iscoroutinefunction(func):
            raise TypeError(
                f"Expected an async function (async def), "
                f"but got a synchronous function: {func.__name__}"
            )
        if on_job_complete is not None and not inspect.iscoroutinefunction(func):
            raise TypeError(
                f"Expected an async function (async def), "
                f"but got a synchronous function: {on_job_complete.__name__}"
            )
        if init_worker is not None:
            init_worker(*init_worker_args)
        active_workers = self._workers
        while active_workers > 0 and not self.shutdown_event.is_set():
            try:
                if len(self._tasks) >= active_workers:
                    done, pending = await asyncio.wait(
                        self._tasks,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for result in done:
                        item = result.result()
                        if item is not None:
                            yield item
                    self._tasks = list(pending)
                elif self._tasks:
                    done, pending = await asyncio.wait(self._tasks, timeout=0.1)
                    for result in done:
                        item = result.result()
                        if item is not None:
                            yield item
                    self._tasks = list(pending)

                try:
                    item = await asyncio.to_thread(source_queue.get, timeout=0.5)
                except queue.Empty:
                    continue

                if item is None:
                    continue

                if isinstance(item, StopEvent):
                    active_workers -= 1
                    continue

                if isinstance(item, JobCompleteEvent):
                    if self._tasks:
                        done, pending = await asyncio.wait(
                            self._tasks,
                            return_when=asyncio.ALL_COMPLETED,
                        )
                        for task in done:
                            item = task.result()
                            if item is not None:
                                yield item
                        self._tasks = []
                    if on_job_complete:
                        await on_job_complete(item)  # type: ignore
                    continue

                if not isinstance(item, Event):
                    item = Event(payload=item)

                self._tasks.append(asyncio.get_running_loop().create_task(func(item)))

            except queue.Empty:
                await asyncio.sleep(0.1)
                continue
            except KeyboardInterrupt:
                # Fallback for Windows
                self.shutdown_event.set()
                break
