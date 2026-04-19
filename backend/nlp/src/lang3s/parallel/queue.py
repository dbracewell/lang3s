from __future__ import annotations

import asyncio
import enum
import json
import multiprocessing as mp
import queue
import time
from abc import ABC, abstractmethod
from multiprocessing.managers import SyncManager
from typing import Any, AsyncGenerator, Generator, Iterable, TypeVar

import pydantic

from lang3s.parallel.core import Event
from lang3s.services.client.redis_client import RedisAsyncClient, RedisClient
from lang3s.utils.async_helper import get_async_event_loop


class TerminationSignal(dict):
    def __init__(self, kv: dict | None = None):
        super().__init__()
        self.update(kv or {})


class QueueSource[T](ABC):
    @abstractmethod
    def _get_one(self, timeout: float = 0) -> Event[T] | None:
        pass

    @abstractmethod
    async def _async_get_one(self, timeout: float = 0) -> Event[T] | None:
        pass

    def fetch(self) -> Generator[Event[T], None, None]:
        """Fetches the tasks from the queue"""
        while True:
            item = self._get_one(timeout=0.5)
            if not item:
                time.sleep(0.5)
                continue

            yield item
            if item.is_shutdown():
                break

    async def async_fetch(self) -> AsyncGenerator[Event[T], None]:
        """Fetches the tasks from the queue"""
        while True:
            item = await self._async_get_one(timeout=0.5)
            if not item:
                await asyncio.sleep(0.5)
                continue

            yield item
            if item.is_shutdown():
                break
            await asyncio.sleep(0.5)

    def fetch_batch(
        self,
        batch_size: int,
        timeout: int = 10,
    ) -> Generator[Event[list[T]], None, None]:
        while True:
            batch: list[T] = []
            start_time = time.perf_counter()
            while (
                len(batch) < batch_size and (time.perf_counter() - start_time) < timeout
            ):
                item = self._get_one(timeout=0.5)
                if not item:
                    continue

                if item.is_shutdown():
                    if batch:
                        yield Event.create_data_event(batch)
                    yield item
                    return

                batch.append(item.data)

            if batch:
                yield Event.create_data_event(batch)

    async def async_fetch_batch(
        self,
        batch_size: int,
        timeout: int = 10,
    ) -> AsyncGenerator[Event[list[T]], None]:
        while True:
            batch: list[T] = []
            deadline = time.perf_counter() + timeout
            while len(batch) < batch_size:
                now = time.perf_counter()
                if now >= deadline:
                    break

                item = await self._async_get_one(timeout=0.5)
                if not item:
                    if batch:
                        break
                    await asyncio.sleep(0.1)
                    continue

                if item.is_shutdown():
                    if batch:
                        yield Event.create_data_event(batch)
                    yield item
                    return

                batch.append(item.data)

            if batch:
                yield Event.create_data_event(batch)
            else:
                await asyncio.sleep(0.1)

    @abstractmethod
    def shutdown(self):
        """Performs any necessary operations to shut down the queue"""
        pass

    @abstractmethod
    def put(self, item: T):
        """Method for the parent to feed the queue."""
        pass

    @abstractmethod
    async def async_shutdown(self):
        """Performs any necessary operations to shut down the queue"""
        pass

    @abstractmethod
    async def async_put(self, item: T):
        """Method for the parent to feed the queue."""
        pass

    def signal_done(self):
        """Producers call this when they are finished."""
        self.put(Event.create_shutdown_event())

    async def async_signal_done(self):
        """Producers call this when they are finished."""
        await self.async_put(Event.create_shutdown_event())

    def signal_job_complete(
        self,
        job_id: int,
        job_payload: dict[str, Any] | None = None,
    ):
        self.put(
            Event.create_job_complete_event(
                job_id,
                job_payload,
            )
        )

    async def async_signal_job_complete(
        self,
        job_id: int,
        job_payload: dict[str, Any] | None = None,
    ):
        await self.async_put(
            Event.create_job_complete_event(
                job_id,
                job_payload,
            )
        )


class SyncQueue[T](QueueSource[T], ABC):
    async def async_shutdown(self):
        self.shutdown()

    async def async_put(self, item: T):
        self.put(item)

    async def async_signal_done(self):
        self.signal_done()

    async def async_signal_job_complete(
        self,
        job_id: int,
        job_payload: dict[str, Any] | None = None,
    ):
        self.signal_job_complete(job_id, job_payload)

    async def _async_get_one(self, timeout: float = 0) -> Event[T] | None:
        return self._get_one(timeout)


class InMemorySyncQueue[T](SyncQueue[T]):
    def __init__(
        self,
        maxsize: int = 100,
    ):
        self._queue = queue.Queue(maxsize)

    def _get_one(self, timeout: float = 0) -> Event[T] | None:
        try:
            item = self._queue.get(timeout=timeout)
            self._queue.task_done()
            if isinstance(item, Event):
                return item
            return Event.create_data_event(item)
        except queue.Empty:
            return None
        except TimeoutError:
            return None

    def put(self, item: Any):
        while True:
            try:
                self._queue.put(item, timeout=1)
                return
            except TimeoutError:
                continue
            except queue.Full:
                continue

    def shutdown(self):
        self.signal_done()


class AsyncQueue[T](QueueSource[T]):
    def __init__(self, maxsize: int = 100):
        super().__init__()
        self._loop = get_async_event_loop()
        self._queue = asyncio.Queue(maxsize)

    def _get_one(self, timeout: float = 0) -> Event[T] | None:
        try:
            item = self._queue.get_nowait()
            self._queue.task_done()
            if isinstance(item, Event):
                return item
            return Event.create_data_event(item)
        except asyncio.queues.QueueEmpty:
            time.sleep(timeout)
            return None

    async def _async_get_one(self, timeout: float = 0.5) -> Event[T] | None:
        try:
            item = await asyncio.wait_for(self._queue.get(), timeout=timeout)
            self._queue.task_done()
            if isinstance(item, Event):
                return item
            return Event.create_data_event(item)
        except queue.Empty:
            return None

    def shutdown(self):
        self._loop.call_soon_threadsafe(
            self._queue.put_nowait, Event.create_shutdown_event()
        )

    def signal_done(self):
        self._loop.call_soon_threadsafe(
            self._queue.put_nowait, Event.create_shutdown_event()
        )

    def signal_job_complete(
        self,
        job_id: int,
        job_payload: dict[str, Any] | None = None,
    ):
        self._loop.call_soon_threadsafe(self._queue.put_nowait, job_id, job_payload)

    def put(self, item: T):
        while True:
            running_loop = None
            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

            if running_loop == self._loop:
                self._queue.put_nowait(item)
                return
            else:
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.async_put(item), self._loop
                    )
                    future.result(timeout=2)
                    return
                except (asyncio.TimeoutError, TimeoutError):
                    continue

    async def async_shutdown(self):
        await self.async_put(Event.create_shutdown_event())

    async def async_put(self, item: T):
        while True:
            try:
                await asyncio.wait_for(self._queue.put(item), timeout=0.5)
                return
            except TimeoutError:
                continue
            except asyncio.queues.QueueFull:
                continue


QueueItemType = TypeVar("QueueItemType")


class QueueType(enum.Enum):
    MULTIPROCESSING = enum.auto()
    IN_MEMORY_SYNC = enum.auto()
    IN_MEMORY_ASYNC = enum.auto()
    REDIS = enum.auto()


class _QueueFactory:
    def __init__(self):
        self.multiprocessing_manager: SyncManager | None = None
        self._queues: list[QueueSource] = []

    def __call__(
        self,
        queue_type: QueueType,
        queue_name: str | None = None,
        maxsize: int = 100,
        **kwargs,
    ) -> QueueSource[QueueItemType]:
        if queue_type == QueueType.MULTIPROCESSING:
            if self.multiprocessing_manager is None:
                self.multiprocessing_manager = mp.get_context("spawn").Manager()
            queue = MultiProcessingQueue[QueueItemType](
                self.multiprocessing_manager.Queue(maxsize)  # type:ignore
            )
            self._queues.append(queue)
            return queue

        if queue_type == QueueType.IN_MEMORY_SYNC:
            queue = InMemorySyncQueue[QueueItemType](maxsize)  # type:ignore
            self._queues.append(queue)
            return queue

        if queue_type == QueueType.REDIS:
            queue = RedisQueue[QueueItemType](queue_name)  # type:ignore
            self._queues.append(queue)
            return queue

        if queue_type == QueueType.IN_MEMORY_ASYNC:
            queue = AsyncQueue[QueueItemType](maxsize)
            self._queues.append(queue)
            return queue

        raise ValueError("Invalid Queue Type")

    def shutdown(self):
        if self.multiprocessing_manager:
            self.multiprocessing_manager.shutdown()
        for q in self._queues:
            q.shutdown()


class QueueFactory:
    def __init__(self):
        self._factory = None

    def __enter__(self) -> _QueueFactory:
        self._factory = _QueueFactory()
        return self._factory

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._factory:
            try:
                self._factory.shutdown()
            except (FileNotFoundError, EOFError, ConnectionError):
                pass
            finally:
                self._factory = None


class MultiProcessingQueue[T](SyncQueue[T]):
    def __init__(self, raw_queue: mp.Queue):
        self._queue = raw_queue

    def shutdown(self):
        try:
            self.signal_done()  # The put() call
        except (FileNotFoundError, EOFError, ConnectionError):
            pass

    def put(self, item: Any):
        while True:
            try:
                self._queue.put(item, timeout=1)
                return
            except TimeoutError:
                continue
            except queue.Full:
                continue

    def _get_one(self, timeout: float = 0) -> Event[T] | None:
        try:
            item = self._queue.get(timeout=timeout)
            if isinstance(item, Event):
                return item
            return Event.create_data_event(item)
        except queue.Empty:
            return None
        except TimeoutError:
            return None


class RedisQueue[T](QueueSource[T]):
    def __init__(
        self,
        queue_name: str,
    ):
        self._client = None
        self._async_client = None
        self._queue_name = queue_name

    @property
    def client(self):
        if self._client is None:
            self._client = RedisClient()
        return self._client

    @property
    def async_client(self):
        if self._async_client is None:
            self._async_client = RedisAsyncClient()
        return self._async_client

    def shutdown(self):
        if self._client:
            self._client.close()
        if self._async_client:
            self._async_client.close()

    async def async_shutdown(self):
        if self._async_client:
            await self._async_client.close()
        if self._client:
            self._client.close()

    def put(self, item: T):
        self.client.enqueue(self._queue_name, item)

    async def async_put(self, item: T):
        await self.async_client.enqueue(self._queue_name, item)

    def _get_one(self, timeout: float = 0.5) -> Event[T] | None:
        item = self.client.dequeue(self._queue_name, timeout=timeout)
        if item is None:
            return None
        item = json.loads(item)
        try:
            return Event.model_validate(item)
        except pydantic.ValidationError:
            return Event.create_data_event(item)

    async def _async_get_one(self, timeout: float = 0.5) -> Event[T] | None:
        item = await self.async_client.dequeue(self._queue_name, timeout=timeout)
        if item is None:
            return None
        item = json.loads(item)
        try:
            return Event.model_validate(item)
        except pydantic.ValidationError:
            return Event.create_data_event(item)


class IterableQueue[T](SyncQueue[T]):
    def __init__(self, generator: Iterable[T]):
        self._generator = iter(generator)

    def _get_one(self, timeout: float = 0) -> Event[T] | None:
        try:
            item = next(self._generator)
            if isinstance(item, Event):
                return item
            return Event.create_data_event(item)
        except StopIteration:
            return Event.create_shutdown_event()

    def shutdown(self):
        pass

    def put(self, item: T):
        raise NotImplementedError()
