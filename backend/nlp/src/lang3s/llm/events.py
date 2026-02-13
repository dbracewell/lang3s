from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import (
    Any,
    TypeVar,
)

from pydantic import BaseModel

from .tools import ToolCall

T = TypeVar("T", bound=BaseModel)


class LLMEventType(StrEnum):
    TEXT_DELTA = "TEXT_DELTA"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"
    PARSE_ERROR = "PARSE_ERROR"
    TOOL_CALL_START = "TOOL_CALL_START"
    TOOL_CALL_DELTA = "TOOL_CALL_DELTA"
    TOOL_CALL_COMPLETE = "TOOL_CALL_COMPLETE"


@dataclass
class LLMEvent[T]:
    type: LLMEventType
    content: str | None = field(default=None)
    finish_reason: str | None = field(default=None)
    exception: Exception | None = field(default=None)
    total_tokens: int | None = field(default=None)
    parsed: T | None = field(default=None)
    tool_call_delta: ToolCallDelta | None = field(default=None)
    tool_call: ToolCall | None = field(default=None)


@dataclass
class ToolCallDelta:
    id: str
    arguments: str = field(default="")
    name: str | None = field(default=None)
