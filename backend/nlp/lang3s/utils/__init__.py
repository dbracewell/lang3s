from typing import Awaitable, Generator, List, TypeVar, cast

from sentence_transformers import util

T = TypeVar("T")


def partition(array: List[T], size: int) -> Generator[List[T], None, None]:
    for i in range(0, len(array), size):
        yield array[i : i + size]


def cosine_similarity(a1: List[float], a2: List[float]) -> float:
    return util.cos_sim(a1, a2).item()


async def get_value(v: T | Awaitable[T | None] | None, default_value: T) -> T:
    if v is None:
        return default_value
    if hasattr(v, "__await__"):
        temp = await cast(Awaitable[T | None], v)
        return temp or default_value
    return cast(T, v)
