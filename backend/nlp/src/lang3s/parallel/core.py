from __future__ import annotations

import multiprocessing as mp
import os
import threading
import time
from enum import Enum, auto
from typing import Any, Callable, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Engine(Enum):
    SYNC = auto()
    ASYNC = auto()
    THREADING = auto()
    MULTIPROCESSING = auto()


class Event(BaseModel, Generic[T]):
    event_type: Literal["Data", "JobComplete", "Shutdown"]
    data_content: T | None = Field(default=None, alias="data")
    job_id_value: int | None = Field(default=None, alias="job_id")
    payload_value: dict[str, Any] | None = None

    model_config = ConfigDict(
        # This allows you to use the field name OR the alias in the constructor
        populate_by_name=True
    )

    @classmethod
    def create_data_event(cls, data: T) -> Event[T]:
        return cls(event_type="Data", data_content=data)

    @classmethod
    def create_shutdown_event(cls) -> Event[T]:
        return cls(event_type="Shutdown")

    @classmethod
    def create_job_complete_event(
        cls, job_id: int, payload: dict[str, Any] | None = None
    ) -> Event[T]:
        return cls(event_type="JobComplete", job_id_value=job_id, payload_value=payload)

    @property
    def job_id(self) -> int:
        if not self.is_job_complete():
            raise ValueError("Event is not a JobComplete Event")
        if self.job_id_value is None:
            raise ValueError("Null Job Id")
        return self.job_id_value

    @property
    def job_payload(self) -> dict[str, Any]:
        if not self.is_job_complete():
            raise ValueError("Event is not a JobComplete Event")
        return self.payload_value or {}

    @property
    def data(self) -> T:
        if not self.is_data():
            raise ValueError("Event is not a Data Event")
        return self.data_content

    def is_data(self):
        return self.event_type == "Data"

    def is_shutdown(self):
        return self.event_type == "Shutdown"

    def is_job_complete(self):
        return self.event_type == "JobComplete"


def _heartbeat():
    """
    Check if the parent process is still alive.
    If the parent dies, the child exits immediately.
    """
    while True:
        try:
            if os.getppid() == 1:
                print(
                    f"Child {os.getpid()} detected orphaned state. Shutting down.",
                    flush=True,
                )
                os._exit(0)
            time.sleep(2)
        except KeyboardInterrupt:
            os._exit(0)


def _worker_init(
    initializer: Callable,
    initargs: tuple,
):
    """
    Runs once per process creation. Initializes heavy objects and
    starts a daemon thread to watch the parent process.
    """

    watcher = threading.Thread(target=_heartbeat, daemon=True)
    watcher.start()

    if initializer:
        args = initargs or ()
        initializer(*args)


def _function_wrapper(
    target_func: Callable,
    args: tuple,
):
    """
    The actual function run by the process.
    This handles heartbeat, initialization, and task execution.
    """
    t = threading.Thread(target=_heartbeat, daemon=True)
    t.start()
    target_func(*args)


def safe_process(
    target: Callable,
    args: tuple = (),
) -> mp.Process:
    """
    Framework utility to create a process wrapped with a heartbeat.
    """
    return mp.Process(target=_function_wrapper, args=(target, args))
