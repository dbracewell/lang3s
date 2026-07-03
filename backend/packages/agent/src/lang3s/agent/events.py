from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from lang3s.llm import ToolCall, ToolResult


class AgentEventType(StrEnum):
    START = "AGENT_START"
    END = "AGENT_END"
    ERROR = "AGENT_ERROR"

    TEXT_DELTA = "TEXT_DELTA"
    TEXT_COMPLETE = "TEXT_COMPLETE"

    TOOL_CALL_START = "TOOL_CALL_START"
    TOOL_CALL_COMPLETE = "TOOL_CALL_COMPLETE"
    TOOL_CALL_RESULT = "TOOL_CALL_RESULT"


AGENT_PARSED_TYPE = TypeVar("AGENT_PARSED_TYPE", bound=BaseModel)


@dataclass
class AgentEvent[AGENT_PARSED_TYPE]:
    type: AgentEventType
    content: str | None = field(default=None)
    parsed: AGENT_PARSED_TYPE | None = field(default=None)
    exception: Exception | None = field(default=None)
    tool_call: ToolCall | None = field(default=None)
    tool_result: ToolResult | None = field(default=None)
    total_tokens: int | None = field(default=None)
    event_time: datetime = field(default_factory=datetime.now)

    @classmethod
    def start_event(cls) -> AgentEvent[AGENT_PARSED_TYPE]:
        return cls(type=AgentEventType.START)

    @classmethod
    def end_event(
        cls,
        total_tokens: int | None = None,
        exception: Exception | None = None,
    ) -> AgentEvent[AGENT_PARSED_TYPE]:
        return cls(
            type=AgentEventType.END,
            total_tokens=total_tokens,
            exception=exception,
        )

    @classmethod
    def error_event(
        cls,
        exception: Exception,
    ) -> AgentEvent[AGENT_PARSED_TYPE]:
        return cls(type=AgentEventType.ERROR, exception=exception)

    @classmethod
    def text_delta_event(
        cls,
        content: str,
    ) -> AgentEvent[AGENT_PARSED_TYPE]:
        return cls(
            type=AgentEventType.TEXT_DELTA,
            content=content,
        )

    @classmethod
    def text_complete_event(
        cls,
        content: str,
        parsed: BaseModel | None = None,
    ) -> AgentEvent[AGENT_PARSED_TYPE]:
        return cls(type=AgentEventType.TEXT_COMPLETE, content=content, parsed=parsed)

    @classmethod
    def tool_call_start_event(
        cls,
        result: ToolCall,
    ) -> AgentEvent[AGENT_PARSED_TYPE]:
        return cls(
            type=AgentEventType.TOOL_CALL_START,
            tool_call=result,
        )

    @classmethod
    def tool_call_complete_event(
        cls,
        result: ToolCall,
    ) -> AgentEvent[AGENT_PARSED_TYPE]:
        return cls(
            type=AgentEventType.TOOL_CALL_COMPLETE,
            tool_call=result,
        )

    @classmethod
    def tool_call_result_event(
        cls,
        result: ToolResult,
    ) -> AgentEvent[AGENT_PARSED_TYPE]:
        return cls(
            type=AgentEventType.TOOL_CALL_RESULT,
            tool_result=result,
        )
