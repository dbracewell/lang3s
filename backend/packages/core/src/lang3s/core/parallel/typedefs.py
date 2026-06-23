from abc import ABC, abstractmethod
from typing import Any, Callable, Concatenate, Generator, Optional, ParamSpec, TypeVar

from pydantic import BaseModel, ConfigDict, computed_field

from lang3s.core.typing_extras import ShutdownEvent

PayloadType = TypeVar("PayloadType")
P = ParamSpec("P")
type SubmittableTask = Callable[Concatenate[ShutdownEvent, ...], Any]


class Event[T](BaseModel):
    payload: Optional[T] = None

    @computed_field
    @property
    def is_terminated(self) -> bool:
        return False


class JobCompleteEvent(Event):
    model_config = ConfigDict(frozen=True)
    job_id: int
    payload: None = None

    @computed_field
    @property
    def is_terminated(self) -> bool:
        return False


class StopEvent(Event[str]):
    model_config = ConfigDict(frozen=True)
    payload: str = "STOP"

    @computed_field
    @property
    def is_terminated(self) -> bool:
        return True


class QueueSource[T](ABC):
    def __init__(self, workers: int) -> None:
        self._workers = workers

    @abstractmethod
    def put(self, item: Event[T]) -> None:
        pass

    @abstractmethod
    def get(self, timeout: Optional[float] = None) -> Event[T]:
        pass

    def broadcast(self, item: Event[T]) -> None:
        for _ in range(self._workers):
            self.put(item)

    def stop(self) -> None:
        self.broadcast(StopEvent())

    def job_complete(self, job_id: int) -> None:
        self.broadcast(JobCompleteEvent(job_id=job_id))

    @abstractmethod
    def empty(self) -> bool:
        pass


class BaseManager(ABC):
    def __init__(self, workers: int) -> None:
        self._workers = workers

    @property
    def num_workers(self) -> int:
        return self._workers

    @abstractmethod
    def create_queue(self, maxsize: int = 0) -> QueueSource[Any]: ...

    @abstractmethod
    def submit(self, target: SubmittableTask, *args, **kwargs) -> None: ...


class BaseSyncManager(BaseManager, ABC):
    def __init__(self, workers: int) -> None:
        super().__init__(workers)

    @abstractmethod
    def shutdown(self) -> None: ...

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()

    @abstractmethod
    def imap(
        self,
        func: Callable[[Event[PayloadType]], Event[PayloadType]],
        source_queue: QueueSource[PayloadType],
        init_worker: Optional[Callable[..., Any]] = None,
        init_worker_args: tuple = (),
        on_job_complete: Callable[[JobCompleteEvent], None] | None = None,
    ) -> Generator[Event, None, None]: ...
