import asyncio
import functools
import logging
import os
import time
from dataclasses import dataclass
from typing import Callable, Generic, Optional, Type, TypeVar

import psutil

from lang3s.utils.logger import get_logger

try:
    from typing import ParamSpec
except ImportError:
    from typing_extensions import ParamSpec

P = ParamSpec("P")
T = TypeVar("T")
ReturnType = TypeVar("ReturnType")


def trace_mem(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger("ROOT")
        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / (1024**2)  # Convert to MB
        logger.info(f"Entering {func.__name__} | Current: {mem_before:.2f} MB")

        result = func(*args, **kwargs)

        mem_after = process.memory_info().rss / (1024**2)
        logger.info(
            f"Exiting {func.__name__} | Delta: {mem_after - mem_before:+.2f} MB | Total: {mem_after:.2f} MB"
        )
        return result

    return wrapper


@dataclass
class Result(Generic[ReturnType]):
    value: Optional[ReturnType]
    error: Optional[Exception]

    @property
    def is_ok(self) -> bool:
        return self.error is None


DecoratedCallable = Callable[P, Result[ReturnType]]


def sneaky_throws(
    logger: logging.Logger | None,
    formatter: Callable[..., str] | None = None,
) -> Callable[[Callable[P, ReturnType]], Callable[P, Result[ReturnType]]]:
    final_logger = logger if logger else get_logger("ROOT")

    def decorator(
        func: Callable[P, ReturnType],
    ) -> DecoratedCallable[P, ReturnType]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Result[ReturnType]:
            try:
                result = func(*args, **kwargs)
                return Result(value=result, error=None)
            except Exception as e:
                if formatter:
                    final_logger.error(formatter(e, *args, **kwargs), exc_info=True)
                else:
                    final_logger.error(e, exc_info=True)
                return Result(value=None, error=e)

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.__module__ = func.__module__
        return wrapper

    return decorator


def retry(
    on_exceed_attempts: Callable[[Exception], ReturnType],
    no_retry: list[Type[Exception]] | None = None,
    max_retries=3,
    delay_base=2,
):
    def decorator(func) -> ReturnType:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if no_retry is not None:
                        for exception in no_retry:
                            if isinstance(e, exception):
                                return on_exceed_attempts(e)
                    if attempt == max_retries:
                        return on_exceed_attempts(e)
                    time.sleep(delay_base**attempt)

            raise Exception("Invalid Code Path")

        return wrapper

    return decorator


def async_retry(
    on_exceed_attempts: Callable[[Exception], ReturnType],
    no_retry: list[Type[Exception]] | None = None,
    on_exceed_throw_exception: bool = True,
    max_retries=3,
    delay_base=2,
):
    def decorator(func) -> ReturnType:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if no_retry is not None:
                        for exception in no_retry:
                            if isinstance(e, exception):
                                if on_exceed_throw_exception:
                                    raise on_exceed_attempts(e)
                                return on_exceed_attempts(e)
                    last_exception = e
                    if attempt < max_retries:
                        await asyncio.sleep(delay_base**attempt)

            if on_exceed_throw_exception:
                raise on_exceed_attempts(last_exception) from last_exception
            return on_exceed_attempts(last_exception)

        return wrapper

    return decorator


def retry_async_gen(
    on_exceed_attempts: Callable[[Exception], ReturnType],
    no_retry: list[Type[Exception]] | None = None,
    max_retries=3,
    decay_base=2.0,
):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    async for item in func(*args, **kwargs):
                        yield item
                    return  # Success: Generator finished without error
                except Exception as e:
                    last_exception = e
                    if no_retry is not None:
                        for exception in no_retry:
                            if isinstance(e, exception):
                                yield on_exceed_attempts(e)
                                return
                    if attempt < max_retries:
                        await asyncio.sleep(decay_base**attempt)

            yield on_exceed_attempts(last_exception)

        return wrapper

    return decorator
