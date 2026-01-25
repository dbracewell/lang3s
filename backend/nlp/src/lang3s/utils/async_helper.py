import asyncio
import queue
import threading
from typing import AsyncGenerator, Callable, Generator, TypeVar


def run_sync(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


T = TypeVar("T")


def async_generator_to_sync(
    gen_factory: Callable[[], AsyncGenerator[T, None]],
) -> Generator[T, None, None]:
    q = queue.Queue()

    def async_runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def iterate():
            try:
                async for item in gen_factory():
                    q.put(item)
            finally:
                q.put(None)

        try:
            loop.run_until_complete(iterate())
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            loop.close()

    t = threading.Thread(target=async_runner)
    t.start()

    while True:
        item = q.get()
        if item is None:
            break
        yield item

    t.join()
