from __future__ import annotations

import textwrap
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Literal,
    Set,
    Type,
    Union,
    get_args,
    get_origin,
)

from pydantic import BaseModel

from lang3s.core import config

if TYPE_CHECKING:
    from .typedefs import Message


def _get_type_name(annotation) -> str:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _to_structured_format(annotation)

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is Literal:
        return " | ".join(repr(a) for a in args)

    if origin is Union:
        return " | ".join(_get_type_name(a) for a in args)

    if origin is not None:
        type_args = [_get_type_name(a) for a in args]
        if origin in (list, set, List, Set):
            return f"{type_args[0]}[]"
        if origin in (dict, Dict):
            return f"{{[key: {type_args[0]}]: {type_args[1]}}}"

        name = getattr(origin, "__name__", str(origin))
        return f"{name}[{', '.join(type_args)}]"

    if hasattr(annotation, "__name__"):
        return annotation.__name__

    return str(annotation).replace("typing.", "")


def _to_structured_format(model: Type[BaseModel]) -> str:
    fields = [
        f'"{name}": {_get_type_name(field.annotation)}'
        for name, field in model.model_fields.items()
    ]
    return "{" + ", ".join(fields) + "}"


def format_messages_for_model(
    messages: list[Message],
    response_model=None,
) -> list[dict[str, Any]]:
    # LLM Supports everything so we just need to convert to a dict normally
    if (
        config.LLM_SUPPORTS_SYSTEM_PROMPT
        and config.LLM_NATIVE_TOOL_SUPPORT
        and config.LLM_SUPPORTS_STRUCTURED_OUTPUT
    ):
        return [msg.to_dict() for msg in messages]

    formatted = []
    tool_buffer = []
    system_content = ""

    # Build up the system prompt
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

    found_user_prompt = False
    for msg in messages:
        if msg.role == "system":
            # System prompt is supported so keep it
            if config.LLM_SUPPORTS_SYSTEM_PROMPT:
                formatted.append(msg.to_dict())
            continue

        if msg.role == "tool":
            if config.LLM_NATIVE_TOOL_SUPPORT:
                # Native tool calling to add it
                formatted.append(msg.to_dict())
            else:
                # Non-native tool call so we need to build
                # up a buffer of tool results
                tool_result = (
                    f"**Source:** {msg.tool_calls[0].name} "
                    f"(ID: {msg.tool_calls[0].tool_call_id})\n"
                    f"**Result:** {msg.content}"
                )
                tool_buffer.append(tool_result)

        else:
            flush_tool_buffer()

            if msg.role == "user":
                # If this is the FIRST user message, attach the system rules
                if not config.LLM_SUPPORTS_SYSTEM_PROMPT and found_user_prompt:
                    content = msg.convert_content(
                        f"SYSTEM RULES:\n{system_content}\n\nUSER TASK:\n"
                    )
                else:
                    content = msg.convert_content()

                found_user_prompt = True
                formatted.append({"role": "user", "content": content})

            elif msg.role == "assistant":
                msg_copy = msg.to_dict()
                msg_copy["content"] = msg_copy.get("content", "Processing...")
                formatted.append(msg_copy)

    if not config.LLM_SUPPORTS_STRUCTURED_OUTPUT:
        last_message = formatted[-1]
        if last_message.role not in ("user", "system"):
            raise ValueError(
                "Cannot set response format for a non system or user message"
            )
        formatted = formatted[:-1]
        messages.append(
            Message(
                role=last_message.role,
                content=textwrap.dedent(f"""{last_message.content}
                            Respond only in JSON. The output must strictly follow this structure:
                            {_to_structured_format(response_model)}
                            Do not include any preamble, thinking blocks, or markdown code fences."""),  # noqa: E501
            )
        )

    flush_tool_buffer()
    return formatted
