from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import (
    Any,
    Dict,
    Literal,
    Optional,
)

from lang3s import config

from .tools import ToolCall


@dataclass
class Message:
    role: Literal["assistant", "user", "system", "tool"]
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    pruned_at: datetime | None = field(default=None)
    extra_data: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        role: Literal["assistant", "user", "system", "tool"],
        content: str,
        tool_calls: list[ToolCall] | None = None,
        pruned_at: datetime | None = None,
        **kwargs,
    ):
        self.role = role
        self.content = content
        self.tool_calls = tool_calls or []
        self.pruned_at = pruned_at
        self.extra_data = kwargs or {}

    def to_dict(self) -> dict[str, Any]:
        if self.role == "tool":
            return {
                "role": self.role,
                "content": self.content,
                "tool_call_id": self.tool_calls[0].tool_call_id,
                "name": self.tool_calls[0].name,
            }

        if self.role == "assistant":
            data: dict[str, Any] = {"role": "assistant"}
            if self.content:
                data["content"] = self.content
            if self.tool_calls:
                data["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
            return data

        if not self.content:
            raise RuntimeError(f"Invalid message: {self}")

        return {"role": self.role, "content": self.content}

    @classmethod
    def user(cls, content: str, **kwargs) -> Message:
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


def format_messages_for_model(messages: list[Message]) -> list[dict[str, Any]]:
    if config.LLM_SUPPORTS_SYSTEM_PROMPT and config.LLM_NATIVE_TOOL_SUPPORT:
        return [msg.to_dict() for msg in messages]
    formatted = []
    tool_buffer = []
    system_content = ""

    for msg in messages:
        if msg.role == "system":
            system_content = msg.content
            break

    def flush_tool_buffer():
        if tool_buffer:
            combined_content = "\n\n".join(tool_buffer)
            formatted.append(
                {
                    "role": "user",
                    "content": f"### SYSTEM OBSERVATIONS\n{combined_content}",
                }
            )
            tool_buffer.clear()

    for msg in messages:
        if msg.role == "system":
            if config.LLM_SUPPORTS_SYSTEM_PROMPT:
                formatted.append(msg.to_dict())
            continue

        if msg.role == "tool":
            if config.LLM_NATIVE_TOOL_SUPPORT:
                formatted.append(msg.to_dict())
            else:
                tool_result = f"**Source:** {msg.tool_calls[0].name} (ID: {msg.tool_calls[0].tool_call_id})\n**Result:** {msg.content}"
                tool_buffer.append(tool_result)

        else:
            flush_tool_buffer()

            if msg.role == "user":
                # If this is the FIRST user message, attach the system rules
                if not config.LLM_SUPPORTS_SYSTEM_PROMPT and not any(
                    m["role"] == "user" for m in formatted
                ):
                    content = (
                        f"SYSTEM RULES:\n{system_content}\n\nUSER TASK:\n{msg.content}"
                    )
                else:
                    content = msg.content
                formatted.append({"role": "user", "content": content})

            elif msg.role == "assistant":
                msg_copy = msg.to_dict()
                msg_copy["content"] = msg_copy.get("content", "Processing...")
                formatted.append(msg_copy)

    flush_tool_buffer()
    return formatted


def to_message(
    role: Literal["assistant", "user", "system", "tool"],
    content: Optional[str] = None,
    tool_call_id: Optional[str] = None,
    name: Optional[str] = None,
    tool_calls: list[dict[str, Any]] | None = None,
    **kwargs,
) -> dict[str, Any]:
    """
    Helper to build messages compatible with openai.types chat params.
    """
    base: Dict[str, Any] = {"role": role}
    if content is not None:
        base["content"] = content
    if tool_calls:
        base["tool_calls"] = tool_calls
    if role == "tool":
        if tool_call_id is None:
            raise ValueError("tool_call_id is required for tool messages")
        base["tool_call_id"] = tool_call_id
        base["name"] = name
    else:
        if name is not None:
            base["name"] = name
    # return cast(ChatCompletionMessageParam, cast(object, base))
    return base
