from typing import Iterable, TypeVar

T = TypeVar("T")


def filter_none(iterable: Iterable[T | None]) -> list[T]:
    return [item for item in iterable if item is not None]
