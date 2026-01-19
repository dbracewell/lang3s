from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import (
    Any,
    TypeVar,
)

from pydantic import BaseModel

from lang3s.agent.llm import ToolCall

T = TypeVar("T", bound=BaseModel)


class ChatCompletionEventType(str, Enum):
    TEXT_DELTA = "TEXT_DELTA"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"
    PARSE_ERROR = "PARSE_ERROR"
    TOOL_CALL_START = "TOOL_CALL_START"
    TOOL_CALL_DELTA = "TOOL_CALL_DELTA"
    TOOL_CALL_COMPLETE = "TOOL_CALL_COMPLETE"


@dataclass
class TokenCompletionUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: TokenCompletionUsage):
        return TokenCompletionUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


@dataclass
class ToolCallDelta:
    id: str
    arguments: str = ""
    name: str | None = None


@dataclass
class ChatCompletionEvent[T]:
    type: ChatCompletionEventType
    content: str | None = None
    finish_reason: str | None = None
    error: str | None = None
    usage: TokenCompletionUsage | None = None
    parsed: T | None = None
    tool_call_delta: ToolCallDelta | None = None
    tool_call: ToolCall | None = None


def parse_tool_call_arguments(arguments: str) -> dict[str, Any]:
    if not arguments:
        return {}

    try:
        return json.loads(arguments)
    except json.JSONDecodeError:
        return {"raw_arguments": arguments}
