import asyncio
import inspect
import logging
import multiprocessing as mp
import os
import threading
import time
from abc import ABC, abstractmethod
from concurrent.futures import Future
from concurrent.futures.thread import ThreadPoolExecutor
from functools import partial
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Generator,
    Iterable,
    Protocol,
    TypeVar,
)

from lang3s.parallel.core import Event, _worker_init, safe_process
from lang3s.parallel.queue import IterableQueue, QueueSource
from lang3s.utils.async_helper import (
    async_generator_to_sync,
    get_async_event_loop,
)
from lang3s.utils.logger import get_logger

ItemType = TypeVar("ItemType")
ReturnValue = TypeVar("ReturnValue")


class SubmittableFunction(Protocol):
    def __call__(self, stop_event, *args: Any, **kwargs: Any) -> Any: ...


class BaseRunner(ABC):
    def __init__(self, logger: logging.Logger | None = None, **kwargs):
        self._logger = logger or get_logger(f"{self.__class__.__name__.upper()}_LOGGER")

    @property
    def num_workers(self) -> int:
        raise NotImplementedError()

    @abstractmethod
    def shutdown(self):
        pass

    async def async_shutdown(self):
        self.shutdown()

    async def _wrapped_task(self, func: Callable, *args):
        try:
            if inspect.iscoroutinefunction(func):
                return await func(*args)
            else:
                return await asyncio.to_thread(func, *args)
        except Exception as e:
            import traceback

            self._logger.error(e)
            traceback.print_exc()

    @abstractmethod
    def map(
        self,
        func: Callable[[ItemType], ReturnValue],
        source: QueueSource[ItemType] | Iterable[ItemType],
        chunksize: int = 1,
    ) -> Generator[Event[ReturnValue], None, None]:
        pass

    async def async_map(
        self,
        func: Callable[[ItemType], Awaitable[ReturnValue]],
        source: QueueSource[ItemType] | Iterable[ItemType],
    ) -> AsyncGenerator[Event[ReturnValue], None]:
        pending = set()
        it = source if isinstance(source, QueueSource) else IterableQueue(source)
        async for item in it.async_fetch():
            if item.is_shutdown():
                break

            pending.add(
                get_async_event_loop().create_task(self._wrapped_task(func, item))
            )

            if len(pending) >= self.num_workers:
                done, pending = await asyncio.wait(
                    pending,
                    return_when=asyncio.FIRST_COMPLETED,
                )
            else:
                done, pending = await asyncio.wait(pending, timeout=0.1)

            for r in done:
                yield r.result()

        if pending:
            done, _ = await asyncio.wait(pending, return_when=asyncio.ALL_COMPLETED)
            for r in done:
                yield r.result()

    @abstractmethod
    def batch_map(
        self,
        func: Callable[[list[ItemType]], list[ReturnValue]],
        source: QueueSource[ItemType] | Iterable[ItemType],
        batch_size: int,
        timeout: int = 10,
    ) -> Generator[Event[list[ReturnValue]], None, None]:
        pass

    async def async_batch_map(
        self,
        func: Callable[[list[ItemType]], Awaitable[list[ReturnValue]]],
        source: QueueSource[ItemType] | Iterable[ItemType],
        batch_size: int,
        timeout: int = 10,
    ) -> AsyncGenerator[Event[list[ReturnValue]], None]:
        it = source if isinstance(source, QueueSource) else IterableQueue(source)
        pending = set()
        async for item in it.async_fetch_batch(batch_size, timeout):
            if item.is_shutdown():
                break
            pending.add(
                get_async_event_loop().create_task(self._wrapped_task(func, item))
            )
            if len(pending) >= self.num_workers:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                for r in done:
                    yield r.result()

        if pending:
            done, _ = await asyncio.wait(pending, return_when=asyncio.ALL_COMPLETED)
            for r in done:
                yield r.result()

    @abstractmethod
    def submit(self, func: SubmittableFunction, args: tuple):
        pass

    def async_submit(self, func: SubmittableFunction, args: tuple):
        self.submit(func, args)


class AsyncRunner(BaseRunner):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        workers = kwargs.get("workers", 100)
        initializer = kwargs.get("initializer")
        initargs = kwargs.get("initargs", ())
        if initializer:
            initializer(*initargs)
        self._workers = workers
        self._stop_event = asyncio.Event()

    @property
    def num_workers(self) -> int:
        return self._workers

    def shutdown(self):
        if not self._stop_event.is_set():
            self._stop_event.set()

    async def async_shutdown(self):
        if not self._stop_event.is_set():
            self._stop_event.set()

    def map(
        self,
        func: Callable[[ItemType], ReturnValue],
        source: QueueSource[ItemType] | Iterable[ItemType],
        chunksize: int = 1,
    ) -> Generator[Event[ReturnValue], None, None]:
        gen_func = partial(self.map, func=func, source=source, chunksize=chunksize)
        for item in async_generator_to_sync(gen_func):
            yield item

    def batch_map(
        self,
        func: Callable[[list[ItemType]], list[ReturnValue]],
        source: QueueSource[ItemType] | Iterable[ItemType],
        batch_size: int,
        timeout: int = 10,
    ) -> Generator[Event[list[ReturnValue]], None, None]:
        gen_func = partial(
            self.batch_map,
            func=func,
            source=source,
            batch_size=batch_size,
            timeout=timeout,
        )
        for item in async_generator_to_sync(gen_func):
            yield item

    def submit(self, func: SubmittableFunction, args: tuple):
        self.async_submit(func, args)

    def async_submit(self, func: SubmittableFunction, args: tuple):
        args = (self._stop_event, *args)
        get_async_event_loop().create_task(self._wrapped_task(func, *args))


class MultiprocessRunner(BaseRunner):
    def __init__(
        self,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._stop_event = mp.Event()
        self._parent_pid = os.getpid()
        self._maxtasksperchild = kwargs.get("maxtasksperchild", None)
        self._context = mp.get_context("spawn")
        self._processes: list[mp.Process] = []
        self._workers = kwargs.get("workers", 1)
        self._pool = self._context.Pool(
            processes=self._workers,
            initializer=_worker_init,
            initargs=(kwargs.get("initializer"), kwargs.get("initargs", ())),
            maxtasksperchild=self._maxtasksperchild,
        )

    @property
    def num_workers(self) -> int:
        return self._workers

    @staticmethod
    def _wrapper(args, func, logger):
        try:
            return func(args)
        except KeyboardInterrupt:
            return None
        except Exception as e:
            import traceback

            logger.error(e)
            traceback.print_exc()
            return None

    def map(
        self,
        func: Callable[[ItemType], ReturnValue],
        source: QueueSource[ItemType] | Iterable[ItemType],
        chunksize: int = 1,
    ) -> Generator[Event[ReturnValue], None, None]:
        partial_func = partial(
            MultiprocessRunner._wrapper,
            func=func,
            logger=self._logger,
        )
        it = (
            source.fetch()
            if isinstance(source, QueueSource)
            else IterableQueue(source).fetch()
        )
        r: Event[ReturnValue]
        for r in self._pool.imap_unordered(partial_func, it, chunksize=chunksize):
            if r.is_shutdown():
                return
            yield r

    def batch_map(
        self,
        func: Callable[[list[ItemType]], list[ReturnValue]],
        source: QueueSource[ItemType] | Iterable[ItemType],
        batch_size: int,
        timeout: int = 10,
    ) -> Generator[Event[list[ReturnValue]], None, None]:
        partial_func = partial(
            MultiprocessRunner._wrapper,
            func=func,
            logger=self._logger,
        )
        if isinstance(source, QueueSource):
            it = source.fetch_batch(batch_size, timeout)
        else:
            it = IterableQueue(source).fetch_batch(batch_size, timeout)
        r: Event[list[ReturnValue]]
        for r in self._pool.imap_unordered(partial_func, it):
            if r.is_shutdown():
                return
            yield r

    def submit(self, func: SubmittableFunction, args: tuple):
        process = safe_process(target=func, args=(self._stop_event, *args))
        self._processes.append(process)
        self._logger.info("Submitting job")
        process.start()

    def shutdown(self):
        if not self._stop_event.is_set():
            self._stop_event.set()
        self._pool.close()
        self._pool.join()
        for p in self._processes:
            p.join()


class ThreadedRunner(BaseRunner):
    def __init__(
        self,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._stop_event = threading.Event()
        self._workers: list[threading.Thread] = []
        self._pool = ThreadPoolExecutor(
            max_workers=kwargs.get("workers", 1),
            thread_name_prefix=kwargs.get("worker_prefix", "worker"),
        )

    @property
    def num_workers(self) -> int:
        return self._pool._max_workers

    def _process_map(self, func, it: Iterable[Event[Any]]):
        futures: list[Future] = []
        while not self._stop_event.is_set():
            start_time = time.perf_counter()
            for item in it:
                if item.is_shutdown():
                    self._stop_event.set()
                    for f in futures:
                        yield f.result()
                    return

                futures.append(self._pool.submit(func, (item,)))
                current_elapsed = time.perf_counter() - start_time
                if current_elapsed > 30 or len(futures) >= self._pool._max_workers:
                    break

            new_futures = []
            for f in futures:
                try:
                    if not f.done():
                        new_futures.append(f)
                        continue
                    yield f.result(timeout=0.1)
                except TimeoutError:
                    new_futures.append(f)
            futures = new_futures

    def _wrapper(self, args, func):
        try:
            return func(*args)
        except Exception as e:
            import traceback

            self._logger.error(e)
            traceback.print_exc()
            return None

    def map(
        self,
        func: Callable[[ItemType], ReturnValue],
        source: QueueSource[ItemType] | Iterable[ItemType],
        chunksize: int = 100,
    ) -> Generator[Event[ReturnValue], None, None]:
        partial_func = partial(self._wrapper, func=func)
        it = (
            source.fetch()
            if isinstance(source, QueueSource)
            else IterableQueue(source).fetch()
        )
        for r in self._process_map(partial_func, it):
            yield r

    def batch_map(
        self,
        func: Callable[[list[ItemType]], list[ReturnValue]],
        source: QueueSource[ItemType] | Iterable[ItemType],
        batch_size: int,
        timeout: int = 1,
    ) -> Generator[Event[list[ReturnValue]], None, None]:
        partial_func = partial(self._wrapper, func=func)
        if isinstance(source, QueueSource):
            it = source.fetch_batch(batch_size, timeout)
        else:
            it = IterableQueue(source).fetch_batch(batch_size, timeout)
        for r in self._process_map(partial_func, it):
            yield r

    def submit(self, func: SubmittableFunction, args: tuple):
        t = threading.Thread(
            target=func,
            args=(
                self._stop_event,
                *args,
            ),
            daemon=True,
            name=f"worker-{len(self._workers) + 1}",
        )
        self._workers.append(t)
        t.start()

    def shutdown(self):
        if not self._stop_event.is_set():
            self._stop_event.set()
        self._pool.shutdown(wait=True)
        for t in self._workers:
            t.join()


class SingleThreadedRunner(BaseRunner):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._stop_event = threading.Event()

    @property
    def num_workers(self) -> int:
        return 1

    def shutdown(self):
        if not self._stop_event.is_set():
            self._stop_event.set()

    def map(
        self,
        func: Callable[[ItemType], ReturnValue],
        source: QueueSource[ItemType] | Iterable[ItemType],
        chunksize: int = 1,
    ) -> Generator[Event[ReturnValue], None, None]:
        it = (
            source.fetch()
            if isinstance(source, QueueSource)
            else IterableQueue(source).fetch()
        )
        for item in it:
            yield item

    def batch_map(
        self,
        func: Callable[[list[ItemType]], list[ReturnValue]],
        source: QueueSource[ItemType] | Iterable[ItemType],
        batch_size: int,
        timeout: int = 10,
    ) -> Generator[Event[list[ReturnValue]], None, None]:
        it = (
            source.fetch_batch(batch_size, timeout)
            if isinstance(source, QueueSource)
            else IterableQueue(source).fetch_batch(batch_size, timeout)
        )
        for item in it:
            yield item

    def submit(self, func: SubmittableFunction, args: tuple):
        func(self._stop_event, *args)
