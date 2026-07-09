import queue
import threading
from typing import (
    Any,
    Callable,
    Generator,
    Optional,
    TypeVar,
)

from lang3s.core.parallel.typedefs import (
    BaseSyncManager,
    Event,
    JobCompleteEvent,
    QueueSource,
    StopEvent,
    SubmittableTask,
)


class BasicQueueSource[T](QueueSource[T]):
    def __init__(self, workers: int, maxsize: int) -> None:
        super().__init__(workers)
        self._queue: queue.Queue[T] = queue.Queue(maxsize=maxsize)

    def put(self, item: Event[T]) -> None:
        self._queue.put(item)

    def get(self, timeout: Optional[float] = None) -> Event[T]:
        return self._queue.get(timeout=timeout)

    def empty(self) -> bool:
        return self._queue.empty()


PayloadType = TypeVar("PayloadType")


class ThreadingManager(BaseSyncManager):
    def __init__(
        self,
        workers: int,
    ) -> None:
        super().__init__(workers)
        self._threads: list[threading.Thread] = []
        self._stop_event = threading.Event()

    def create_queue(self, maxsize: int = 0) -> QueueSource[Any]:
        return BasicQueueSource(workers=self._workers, maxsize=maxsize)

    def submit(self, target: SubmittableTask, *args, **kwargs) -> None:
        thread = threading.Thread(
            target=target,
            args=(self._stop_event, *args),
            kwargs=kwargs,
        )
        thread.daemon = True
        self._threads.append(thread)
        thread.start()

    def imap(
        self,
        func: Callable[[Event[PayloadType]], Event | None],
        source_queue: QueueSource[PayloadType],
        init_worker: Optional[Callable[..., Any]] = None,
        init_worker_args: tuple = (),
        on_job_complete: Callable[[JobCompleteEvent], None] | None = None,
    ) -> Generator[Event, None, None]:
        if init_worker is not None:
            init_worker(*init_worker_args)
        result_queue = self.create_queue()
        barrier = threading.Barrier(self._workers)
        for _ in range(self._workers):
            self.submit(
                ThreadingManager._worker_loop,  # type:ignore
                source_queue,
                result_queue,
                func,
                barrier,
                on_job_complete,
            )

        active_workers = self._workers
        while active_workers > 0:
            try:
                res = result_queue.get(timeout=1.0)
                if isinstance(res, StopEvent):
                    print("RECEIVED STOP EVENT")
                    active_workers -= 1
                    continue
                yield res
            except queue.Empty:
                pass
            except KeyboardInterrupt:
                print("\nInterrupt received. Shutting down generator.")
                return

    def shutdown(self) -> None:
        self._stop_event.set()
        for thread in self._threads:
            thread.join(timeout=2.0)
            if thread.is_alive():
                print(f"Warning: Thread {thread.name} refused to die.")

    @staticmethod
    def _worker_loop(
        shutdown_event: threading.Event,
        in_q: QueueSource,
        out_q: QueueSource,
        map_func: Callable[..., Any],
        barrier: Any,
        on_job_complete: Callable[..., Any] | None,
    ):
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
                    if rank == 0:
                        if on_job_complete:
                            on_job_complete(item)
                    barrier.wait()
                    continue

                if not isinstance(item, Event):
                    item = Event(payload=item)

                result = map_func(item)
                if result is not None:
                    out_q.put(result)

            except queue.Empty:
                continue
            except KeyboardInterrupt:
                shutdown_event.set()
                break
