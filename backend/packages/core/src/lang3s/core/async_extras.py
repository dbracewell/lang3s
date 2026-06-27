import asyncio
import concurrent.futures
import queue
import threading
from typing import Any, AsyncGenerator, Callable, Coroutine, Generator, TypeVar

_ReturnType = TypeVar("_ReturnType")
T = TypeVar("T")

_async_loop = asyncio.new_event_loop()


def _start_background_loop(loop: asyncio.AbstractEventLoop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


_loop_thread = threading.Thread(
    target=_start_background_loop,
    args=(_async_loop,),
    daemon=True,
)
_loop_thread.start()


def run_sync(
    coro: Coroutine[Any, Any, _ReturnType],
) -> _ReturnType:
    return asyncio.run_coroutine_threadsafe(coro, _async_loop).result()


def get_async_event_loop():
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def async_generator_to_sync(
    gen_factory: Callable[[], AsyncGenerator[T, None]],
) -> Generator[T, None, None]:
    q = queue.Queue()

    def async_runner():
        loop = get_async_event_loop()

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
