import itertools
import math
from typing import (
    Any,
    Awaitable,
    Generator,
    List,
    Optional,
    TypeVar,
    cast,
)

T = TypeVar("T")


def flatten(a: List[List[T]]) -> List[T]:
    return list(a for a in itertools.chain(*a))


def partition_generator(
    generator: Generator[T, Any, Any], size: int
) -> Generator[List[T], None, None]:
    it = iter(generator)
    while True:
        chunk = list(itertools.islice(it, size))
        if not chunk:
            break
        yield chunk


def partition(
    array: List[T],
    size: Optional[int] = None,
    max_size: Optional[int] = None,
) -> Generator[List[T], None, None]:
    if size is None and max_size is None:
        raise Exception("size or max_size must be specified")
    array_length = len(array)
    if size is None:
        size = (
            array_length
            if array_length < cast(int, max_size)
            else math.ceil(array_length / cast(int, max_size))
        )
    for i in range(0, array_length, size):
        yield array[i : i + size]


async def get_value(v: T | Awaitable[T | None] | None, default_value: T) -> T:
    if v is None:
        return default_value
    if hasattr(v, "__await__"):
        temp = await cast(Awaitable[T | None], v)
        return temp or default_value
    return cast(T, v)
