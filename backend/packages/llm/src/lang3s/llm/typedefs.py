from __future__ import annotations

import json
import re
from collections.abc import Generator
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import (
    Any,
    Callable,
    Generic,
    Literal,
    TypeVar,
)

from openai.types.chat import (
    ChatCompletionFunctionToolParam,
)
from pydantic import BaseModel

from lang3s.core.async_extras import run_sync
from lang3s.core.decorators import async_retry, retry

T_co = TypeVar("T_co", bound=BaseModel, covariant=True)


@dataclass
class ToolResult:
    tool_call_id: str
    content: str
    name: str
    raw_result: Any  # pyright: ignore[reportExplicitAny]
    is_empty: bool

    def to_message(self):
        return {
            "role": "tool",
            "tool_call_id": self.tool_call_id,
            "content": self.content,
            "name": self.name,
        }


@dataclass
class ToolCall:
    name: str
    tool_call_id: str
    arguments: dict[str, Any]  # pyright: ignore[reportExplicitAny]
    arguments_type: type[BaseModel]
    is_async: bool
    function: Callable[..., Any]  # pyright: ignore[reportExplicitAny]

    def to_dict(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        return {
            "id": self.tool_call_id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self.arguments),
            },
        }

    def _parse_result(self, raw_result: Any) -> ToolResult:  # pyright: ignore[reportExplicitAny]
        is_empty = False
        if isinstance(raw_result, BaseModel):
            content = raw_result.model_dump_json()
        elif isinstance(raw_result, (dict, list)):
            content = json.dumps(raw_result)
            is_empty = len(raw_result) == 0
        elif isinstance(raw_result, (int, float, bool)):
            content = json.dumps({"result": raw_result})
        elif isinstance(raw_result, str):
            content = json.dumps({"result": raw_result})
            is_empty = len(raw_result) == 0
        elif raw_result is None:
            content = json.dumps({"result": None})
            is_empty = True
        else:
            content = json.dumps({"result": str(raw_result)})
            is_empty = len(str(raw_result)) == 0

        return ToolResult(
            tool_call_id=self.tool_call_id,
            content=content,
            name=self.name,
            raw_result=raw_result,
            is_empty=is_empty,
        )

    def invoke(self, max_retries: int = 3) -> ToolResult:
        @retry(
            max_retries=max_retries,
            on_exceed_attempts=lambda last_exception: Exception(
                f"Tool '{self.name}' failed after {max_retries} attempts.\n"
                f"Arguments: {self.arguments}\n"
                f"Error: {last_exception}",
            ),
        )
        def call_tool():
            try:
                arguments = self.arguments_type.model_validate(self.arguments)
            except Exception as e:
                raise RuntimeError(e)

            if self.is_async:
                raw_result = run_sync(self.function(**arguments.model_dump()))
            else:
                raw_result = self.function(**arguments.model_dump())

            return self._parse_result(raw_result)

        return call_tool()

    async def async_invoke(self, max_retries: int = 3) -> ToolResult:
        @async_retry(
            max_retries=max_retries,
            on_exceed_attempts=lambda last_exception: Exception(
                f"Tool '{self.name}' failed after {max_retries} attempts.\n"
                f"Arguments: {self.arguments}\n"
                f"Error: {last_exception}",
            ),
        )
        async def call_tool():
            try:
                arguments = self.arguments_type.model_validate(self.arguments)
            except Exception as e:
                raise RuntimeError(e)

            if self.is_async:
                raw_result = await self.function(**arguments.model_dump())
            else:
                raw_result = self.function(**arguments.model_dump())

            return self._parse_result(raw_result)

        return await call_tool()


@dataclass(frozen=True)
class ArgDesc:
    description: str


@dataclass
class Content:
    type: Literal["text", "image_url"]
    text: str | None = None
    image_url: dict[str, Any] | None = None  # pyright: ignore[reportExplicitAny]


@dataclass
class Message:
    role: Literal["assistant", "user", "system", "tool"]
    content: str | list[Content]
    tool_calls: list[ToolCall] = field(default_factory=list)
    pruned_at: datetime | None = field(default=None)
    extra_data: dict[str, Any] = field(default_factory=dict)  # pyright: ignore[reportExplicitAny]

    def __init__(
        self,
        role: Literal["assistant", "user", "system", "tool"],
        content: str | list[Content],
        tool_calls: list[ToolCall] | None = None,
        pruned_at: datetime | None = None,
        **kwargs,
    ):
        self.role = role
        self.content = content
        self.tool_calls = tool_calls or []
        self.pruned_at = pruned_at
        self.extra_data = kwargs or {}

    def convert_content(
        self,
        injected_content: str | None = None,
    ) -> str | list[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
        if isinstance(self.content, list):
            output = []
            has_text = False
            for item in self.content:
                c: dict[str, Any] = {"type": item.type}  # pyright: ignore[reportExplicitAny]
                if item.type == "text":
                    has_text = True
                    if injected_content:
                        c["text"] = f"{injected_content}{item.text}"
                    else:
                        c["text"] = item.text
                else:
                    c["image_url"] = item.image_url
                output.append(c)

            if injected_content and not has_text:
                output.append({"type": "text", "text": injected_content})

            return output

        if injected_content:
            return f"{injected_content}{self.content}"
        return self.content

    def to_dict(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        if self.role == "tool":
            return {
                "role": self.role,
                "content": self.content,
                "tool_call_id": self.tool_calls[0].tool_call_id,
                "name": self.tool_calls[0].name,
            }

        if self.role == "assistant":
            data: dict[str, Any] = {"role": "assistant"}  # pyright: ignore[reportExplicitAny]
            if self.content:
                data["content"] = self.content
            if self.tool_calls:
                data["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
            return data

        if not self.content:
            raise RuntimeError(f"Invalid message: {self}")

        return {"role": self.role, "content": self.convert_content()}

    @classmethod
    def user(
        cls,
        content: str | list[Content],
        **kwargs: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    ) -> Message:
        return cls(role="user", content=content, **kwargs)

    @classmethod
    def assistant(
        cls,
        content: str,
        tool_calls: list[ToolCall] | None = None,
    ) -> Message:
        return cls(
            role="assistant",
            content=content,
            tool_calls=tool_calls or [],
        )

    @classmethod
    def system(cls, content: str) -> Message:
        return cls(role="system", content=content)

    @classmethod
    def tool(
        cls,
        tool_call: ToolCall,
        content: str = "",
    ) -> Message:
        return cls(
            role="tool",
            tool_calls=[tool_call],
            content=content,
        )


class LLMEventType(StrEnum):
    TEXT_DELTA = "TEXT_DELTA"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"
    PARSE_ERROR = "PARSE_ERROR"
    TOOL_CALL_START = "TOOL_CALL_START"
    TOOL_CALL_DELTA = "TOOL_CALL_DELTA"
    TOOL_CALL_COMPLETE = "TOOL_CALL_COMPLETE"


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


@dataclass
class LLMTool:
    name: str
    is_async: bool
    schema: ChatCompletionFunctionToolParam
    arg_validator: type[BaseModel]
    function: Callable[..., Any]  # pyright: ignore[reportExplicitAny]


class AvailableTools:
    def __init__(self, tools: list[Callable[..., Any]] | None):  # pyright: ignore[reportExplicitAny]
        self._tool_definitions: dict[str, LLMTool] = dict()
        if tools:
            for func in tools:
                if not isinstance(func, Callable) or not hasattr(func, "tool"):
                    raise ValueError(
                        "tool must be a function and must have the tool decorator"
                    )
                else:
                    self._tool_definitions[func.tool.name] = func.tool  # type: ignore

    def items(self):
        return self._tool_definitions.items()

    def __getitem__(self, tool_name: str) -> LLMTool:
        return self._tool_definitions[tool_name]

    @staticmethod
    def _parse_tool_call_arguments(arguments: str) -> dict[str, Any]:
        if not arguments:
            return {}

        try:
            arguments = re.sub("'$", "", re.sub(r"^'", "", arguments)).strip()
            return json.loads(arguments)
        except json.JSONDecodeError:
            return {"raw_arguments": arguments}

    def prepare_tool_calls[T: BaseModel](
        self,
        tool_calls: list[dict[str, Any]],  # pyright: ignore[reportExplicitAny]
    ) -> Generator[LLMEvent[T], None, None]:
        if not tool_calls:
            return
        for tc in tool_calls or []:
            llm_tool = self._tool_definitions[tc["name"]]
            yield LLMEvent(
                type=LLMEventType.TOOL_CALL_COMPLETE,
                tool_call=ToolCall(
                    tool_call_id=tc["id"],
                    name=tc["name"],
                    arguments=AvailableTools._parse_tool_call_arguments(
                        tc["arguments"]
                    ),
                    arguments_type=llm_tool.arg_validator,
                    is_async=llm_tool.is_async,
                    function=llm_tool.function,
                ),
            )
