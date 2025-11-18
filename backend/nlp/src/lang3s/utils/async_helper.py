import asyncio


def run_sync(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()
