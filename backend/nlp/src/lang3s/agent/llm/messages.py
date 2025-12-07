from typing import (
    Any,
    Dict,
    Optional,
)
from typing import (
    Literal,
    cast, )

from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam


def to_message(
    role: Literal["assistant", "user", "system", "tool"],
    content: Optional[str] = None,
    tool_call_id: Optional[str] = None,
    name: Optional[str] = None,
    **kwargs,
) -> ChatCompletionMessageParam:
    """
    Helper to build messages compatible with openai.types chat params.
    """
    base: Dict[str, Any] = {"role": role}
    if content is not None:
        base["content"] = content
    if role == "tool":
        if tool_call_id is None:
            raise ValueError("tool_call_id is required for tool messages")
        base["tool_call_id"] = tool_call_id
    else:
        if name is not None:
            base["name"] = name
    return cast(ChatCompletionMessageParam, cast(object, base))
