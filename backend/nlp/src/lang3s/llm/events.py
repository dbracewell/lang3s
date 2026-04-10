from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Generic, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from .tools import ToolCall


class LLMEventType(StrEnum):
    TEXT_DELTA = "TEXT_DELTA"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"
    PARSE_ERROR = "PARSE_ERROR"
    TOOL_CALL_START = "TOOL_CALL_START"
    TOOL_CALL_DELTA = "TOOL_CALL_DELTA"
    TOOL_CALL_COMPLETE = "TOOL_CALL_COMPLETE"


T_co = TypeVar("T_co", bound=BaseModel, covariant=True)


@dataclass
class LLMEvent(Generic[T_co]):
    type: LLMEventType
    content: str | None = field(default=None)
    finish_reason: str | None = field(default=None)
    exception: Exception | None = field(default=None)
    total_tokens: int | None = field(default=None)
    parsed: T_co | None = field(default=None)
    tool_call_delta: ToolCallDelta | None = field(default=None)
    tool_call: ToolCall | None = field(default=None)


@dataclass
class ToolCallDelta:
    id: str
    arguments: str = field(default="")
    name: str | None = field(default=None)
