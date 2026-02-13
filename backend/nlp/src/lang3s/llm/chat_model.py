import json
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
)

import openai
from openai.types.chat.chat_completion_audio import ChatCompletionAudio
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)
from openai.types.shared.reasoning_effort import ReasoningEffort
from pydantic import BaseModel

from lang3s import config
from lang3s.llm.messages import to_message

from .tools import LLMTool, ToolCall

T = TypeVar("T", bound=BaseModel)


@dataclass
class ChatModelResponse(Generic[T]):
    tool_calls: Optional[List[ToolCall]]
    content: Optional[str]
    audio: Optional[ChatCompletionAudio]
    parsed: Optional[T] = None
    exception: Optional[Exception] = None


def format_messages_for_model(messages) -> List[Dict[str, Any]]:
    if config.LLM_SUPPORTS_SYSTEM_PROMPT and config.LLM_NATIVE_TOOL_SUPPORT:
        return [to_message(**msg) for msg in messages]
    formatted = []
    tool_buffer = []
    system_content = ""

    for msg in messages:
        if msg["role"] == "system":
            system_content = msg["content"]
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

    # 2. Process User/Assistant/Tool turns
    for msg in messages:
        if msg["role"] == "system":
            if config.LLM_SUPPORTS_SYSTEM_PROMPT:
                formatted.append(to_message(**msg))
            continue

        if msg["role"] == "tool":
            if config.LLM_NATIVE_TOOL_SUPPORT:
                formatted.append(to_message(**msg))
            else:
                tool_result = f"**Source:** {msg['name']} (ID: {msg['tool_call_id']})\n**Result:** {msg['content']}"
                tool_buffer.append(tool_result)

        else:
            flush_tool_buffer()

            if msg["role"] == "user":
                # If this is the FIRST user message, attach the system rules
                if not config.LLM_SUPPORTS_SYSTEM_PROMPT and not any(
                    m["role"] == "user" for m in formatted
                ):
                    content = f"SYSTEM RULES:\n{system_content}\n\nUSER TASK:\n{msg['content']}"
                else:
                    content = msg["content"]
                formatted.append({"role": "user", "content": content})

            elif msg["role"] == "assistant":
                msg_copy = msg.copy()
                msg_copy["content"] = msg_copy.get("content") or "Processing..."
                formatted.append(to_message(**msg_copy))

    flush_tool_buffer()
    return formatted


class ChatModel:
    def __init__(self, model_name: str):
        self.model = model_name
        self.base_url = f"{config.LLM_HOST}/v1/"
        self.sync_client = openai.OpenAI(
            api_key=config.LLM_API_KEY,
            base_url=f"{config.LLM_HOST}/v1/",
        )
        self.async_client = openai.AsyncOpenAI(
            api_key=config.LLM_API_KEY,
            base_url=f"{config.LLM_HOST}/v1/",
        )
        self.supports_tools = config.LLM_SUPPORTS_SYSTEM_PROMPT

    @staticmethod
    def _prepare_tools(tools: Optional[List[Callable[..., Any]]]):
        tool_definitions: Dict[str, LLMTool] = dict()
        if tools:
            for func in tools:
                if not isinstance(func, Callable) or not hasattr(func, "tool"):
                    raise ValueError(
                        "tool must be a callable or a function and must have the tool decorator"
                    )
                else:
                    tool_definitions[func.tool.name] = func.tool  # type: ignore
        return tool_definitions

    def _prepare_payload(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[LLMTool]] = None,
        response_model: Optional[Type[BaseModel]] = None,
        force_tool_call: bool = False,
        supports_tools: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        updated_messages = format_messages_for_model(
            messages,
        )

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": updated_messages,
            **kwargs,
        }

        if tools and len(tools) > 0:
            payload["tools"] = [t.schema for t in tools]
            payload["tool_choice"] = "required" if force_tool_call else "auto"
        elif response_model is not None:
            raw = response_model.model_json_schema()
            for prop in raw.get("properties", {}).values():
                prop.pop("title", None)
                prop.pop("description", None)
            raw.pop("title", None)
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "strict": False,
                    "schema": raw,
                },
            }
        return payload

    @staticmethod
    def _parse_response(
        response,
        response_model: Optional[Type[BaseModel]] = None,
        tool_definitions: Optional[Dict[str, LLMTool]] = None,
    ) -> ChatModelResponse:
        msg = response.choices[0].message
        tool_calls: Optional[List[ToolCall]] = None
        tool_definitions = tool_definitions or {}

        if msg.tool_calls:
            tool_calls = []
            for tc in msg.tool_calls:
                if isinstance(tc, ChatCompletionMessageFunctionToolCall):
                    function = tc.function
                    definition = tool_definitions.get(function.name, None)
                    if definition:
                        tool_calls.append(
                            ToolCall(
                                name=function.name,
                                tool_call_id=tc.id,
                                is_async=definition.is_async,
                                arguments_type=definition.arg_validator,
                                function=definition.function,
                                arguments=json.loads(function.arguments),
                            )
                        )

        exception = None
        parsed = getattr(msg, "parsed", None)
        if response_model is not None and parsed is None:
            try:
                parsed = response_model.model_validate_json(msg.content)
            except Exception as e:
                exception = e

        return ChatModelResponse(
            content=msg.content,
            audio=msg.audio,
            tool_calls=tool_calls,
            parsed=parsed,
            exception=exception,
        )

    def chat(
        self,
        *,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Callable[..., Any]]] = None,
        response_model: Optional[Type[T]] = None,
        force_tool_call: bool = False,
        reasoning_effort: Optional[ReasoningEffort] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> ChatModelResponse[T]:
        tool_definitions = ChatModel._prepare_tools(tools=tools)
        payload: Dict[str, Any] = self._prepare_payload(
            messages=messages,
            tools=list(tool_definitions.values()),
            response_model=response_model,
            force_tool_call=force_tool_call,
            reasoning_effort=reasoning_effort,
            max_completion_tokens=max_tokens,
            temperature=temperature,
            supports_tools=self.supports_tools,
        )
        response = self.sync_client.chat.completions.create(**payload)
        return ChatModel._parse_response(response, response_model, tool_definitions)

    async def async_chat(
        self,
        *,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Callable[..., Any]]] = None,
        response_model: Optional[Type[T]] = None,
        force_tool_call: bool = False,
        reasoning_effort: Optional[ReasoningEffort] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> ChatModelResponse[T]:
        tool_definitions = ChatModel._prepare_tools(tools=tools)
        payload: Dict[str, Any] = self._prepare_payload(
            messages=messages,
            tools=list(tool_definitions.values()),
            response_model=response_model,
            force_tool_call=force_tool_call,
            reasoning_effort=reasoning_effort,
            max_completion_tokens=max_tokens,
            temperature=temperature,
            supports_tools=self.supports_tools,
        )
        response = await self.async_client.chat.completions.create(**payload)
        return ChatModel._parse_response(response, response_model, tool_definitions)
