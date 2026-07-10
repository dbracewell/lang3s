import asyncio
import inspect
import multiprocessing as mp
from queue import Empty
from typing import Any, Awaitable, Callable, Coroutine, Generator, List, Optional

from lang3s.core.typing_extras import ShutdownEvent

from ..async_extras import run_sync
from .typedefs import (
    BaseSyncManager,
    Event,
    JobCompleteEvent,
    PayloadType,
    QueueSource,
    StopEvent,
    SubmittableTask,
)


class MultiprocessingQueueSource[T](QueueSource[T]):
    def __init__(
        self,
        context: mp.context.BaseContext,
        workers: int,
        maxsize: int = 0,
    ):
        super().__init__(workers)
        self._queue = context.Queue(maxsize)

    def put(self, item: Event[T]) -> None:
        self._queue.put(item)

    def get(self, timeout: Optional[float] = None) -> Event[T]:
        return self._queue.get(timeout=timeout)

    def empty(self) -> bool:
        return self._queue.empty()


class MultiprocessingManager(BaseSyncManager):
    def __init__(
        self,
        context_type: str = "spawn",
        workers: int = 1,
    ):
        super().__init__(workers)
        self.ctx = mp.get_context(context_type)
        self._stop_event = self.ctx.Event()
        self.processes: List[mp.Process] = []

    def create_queue(self, maxsize: int = 0) -> MultiprocessingQueueSource:
        """Creates a managed queue source."""
        return MultiprocessingQueueSource(
            self.ctx,
            workers=self._workers,
            maxsize=maxsize,
        )

    def submit(self, target: SubmittableTask, *args, **kwargs) -> mp.Process:
        def async_wrapper(func, *args, **kwargs):
            return asyncio.run(func(*args, **kwargs))

        """Submits a raw process and tracks it."""
        if inspect.iscoroutinefunction(target):
            process: mp.Process = self.ctx.Process(  # type: ignore
                target=async_wrapper,
                args=(target, self._stop_event, *args),
                kwargs=kwargs,
            )
        else:
            process: mp.Process = self.ctx.Process(  # type: ignore
                target=target,
                args=(self._stop_event, *args),
                kwargs=kwargs,
            )

        process.start()
        self.processes.append(process)
        return process

    @staticmethod
    def _worker_loop(
        shutdown_event: ShutdownEvent,
        in_q: QueueSource,
        out_q: QueueSource,
        map_func: Callable[[Event], Event] | Coroutine[Any, Event, Event],
        barrier: Any,
        init_worker: Optional[Callable[..., Any]] = None,
        init_worker_args: tuple = (),
        on_job_complete: Callable[[Event], None | Awaitable[None]] | None = None,
    ):
        if init_worker is not None:
            init_worker(*init_worker_args)

        """Top-level/Static method so it can be pickled by the spawn context."""
        while not shutdown_event.is_set():
            try:
                item = in_q.get(timeout=1.0)

                if item is None:
                    continue

                if isinstance(item, StopEvent):
                    out_q.put(item)
                    return

                if isinstance(item, JobCompleteEvent):
                    rank = barrier.wait()
                    if rank == 0 and on_job_complete is not None:
                        if inspect.iscoroutinefunction(on_job_complete):
                            run_sync(on_job_complete(item))
                        else:
                            on_job_complete(item)

                    barrier.wait()
                    continue

                if not isinstance(item, Event):
                    item = Event(payload=item)

                if inspect.iscoroutinefunction(map_func):
                    result = run_sync(map_func(item))
                else:
                    result = map_func(item)

                out_q.put(result)

            except Empty:
                continue
            except KeyboardInterrupt:
                shutdown_event.set()
                break

    def imap(
        self,
        func: Callable[
            [Event[PayloadType]], Event | None | Awaitable[Event[PayloadType] | None]
        ],
        source_queue: QueueSource,
        init_worker: Optional[Callable[..., Any]] = None,
        init_worker_args: tuple = (),
        on_job_complete: Callable[[JobCompleteEvent], None | Awaitable[None]]
        | None = None,
    ) -> Generator[Event, None, None]:
        try:
            result_queue = self.create_queue()
            barrier = self.ctx.Barrier(self._workers)
            for _ in range(self._workers):
                self.submit(
                    MultiprocessingManager._worker_loop,  # type:ignore
                    source_queue,
                    result_queue,
                    func,
                    barrier,
                    init_worker,
                    init_worker_args,
                    on_job_complete,
                )

            active_workers = self._workers
            while active_workers > 0 and not self._stop_event.is_set():
                try:
                    res = result_queue.get(timeout=1.0)
                    if isinstance(res, StopEvent):
                        active_workers -= 1
                        continue
                    yield res
                except Empty:
                    pass
                except KeyboardInterrupt:
                    self._stop_event.set()
                    break
        except KeyboardInterrupt:
            self._stop_event.set()

    def shutdown(self) -> None:
        self._stop_event.set()
        for process in self.processes:
            process.terminate()
