from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

T = TypeVar("T")


@dataclass(kw_only=True)
class ParseResult[T]:
    content: T
    metadata: dict[str, Any] = field(default_factory=dict)


type R = ParseResult[Any]
type ParseFn = Callable[[str | bytes, str | None], R]
