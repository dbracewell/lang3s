from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass(kw_only=True)
class ParseResult[T]:
    content: T
    metadata: dict[str, Any] = field(default_factory=dict)


class Parser[R: ParseResult[Any]](abc.ABC):
    @abc.abstractmethod
    def parse(self, text: str | bytes, encoding: str | None = None) -> R:
        raise NotImplementedError
