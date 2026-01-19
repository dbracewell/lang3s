import asyncio
import queue
import threading
from typing import AsyncGenerator, Generator, TypeVar


def run_sync(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


T = TypeVar("T")


def async_generator_to_sync(
    generator: AsyncGenerator[T, None],
) -> Generator[T, None, None]:
    q = queue.Queue()

    def async_runner():
        async def iterate():
            try:
                async for item in generator:
                    q.put(item)
            finally:
                q.put(None)

        asyncio.run(iterate())

    t = threading.Thread(target=async_runner)
    t.start()

    while True:
        item = q.get()
        if item is None:
            break
        yield item

    t.join()
