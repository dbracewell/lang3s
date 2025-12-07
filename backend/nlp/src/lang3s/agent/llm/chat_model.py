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
from openai.types.chat.chat_completion_message_function_tool_call import ChatCompletionMessageFunctionToolCall
from openai.types.shared.reasoning_effort import ReasoningEffort
from pydantic import BaseModel

from lang3s import config
from lang3s.agent.llm.messages import to_message
from .tools import LLMTool, ToolCall

T = TypeVar("T", bound=BaseModel)


@dataclass
class ChatModelResponse(Generic[T]):
    tool_calls: Optional[List[ToolCall]]
    content: Optional[str]
    audio: Optional[ChatCompletionAudio]
    parsed: Optional[T] = None
    exception: Optional[Exception] = None


class ChatModel:

    def __init__(self,
                 model_name: str):
        self.model = model_name
        self.sync_client = openai.OpenAI(
            api_key=config.LLM_API_KEY,
            base_url=f"{config.LLM_HOST}/v1/",
        )
        self.async_client = openai.AsyncOpenAI(
            api_key=config.LLM_API_KEY,
            base_url=f"{config.LLM_HOST}/v1/",
        )

    @staticmethod
    def _prepare_tools(tools: Optional[List[Callable[..., Any]]]):
        tool_definitions: Dict[str, LLMTool] = dict()
        if tools:
            for func in tools:
                if not isinstance(func, Callable) or not hasattr(func, 'tool'):
                    raise ValueError("tool must be a callable or a function and must have the tool decorator")
                else:
                    tool_definitions[func.tool.name] = func.tool  # type: ignore
        return tool_definitions

    def _prepare_payload(self,
                         messages: List[Dict[str, Any]],
                         tools: Optional[List[LLMTool]] = None,
                         response_model: Optional[Type[BaseModel]] = None,
                         force_tool_call: bool = False,
                         **kwargs, ) -> Dict[str, Any]:

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [to_message(**m) for m in messages],
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
                    "strict": True,
                    "schema": raw
                }
            }
        return payload

    @staticmethod
    def _parse_response(response,
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
                        tool_calls.append(ToolCall(
                            name=function.name,
                            tool_call_id=tc.id,
                            is_async=definition.is_async,
                            arguments_type=definition.arg_validator,
                            function=definition.function,
                            arguments=json.loads(function.arguments),
                        ))

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

    def chat(self, *,
             messages: List[Dict[str, Any]],
             tools: Optional[List[Callable[..., Any]]] = None,
             response_model: Optional[Type[T]] = None,
             force_tool_call: bool = False,
             reasoning_effort: Optional[ReasoningEffort] = None,
             max_tokens: Optional[int] = None,
             temperature: Optional[float] = None,
             ) -> ChatModelResponse[T]:
        tool_definitions = ChatModel._prepare_tools(tools=tools)
        payload: Dict[str, Any] = self._prepare_payload(messages=messages,
                                                        tools=list(tool_definitions.values()),
                                                        response_model=response_model,
                                                        force_tool_call=force_tool_call,
                                                        reasoning_effort=reasoning_effort,
                                                        max_completion_tokens=max_tokens,
                                                        temperature=temperature)
        response = self.sync_client.chat.completions.create(**payload)
        return ChatModel._parse_response(response, response_model, tool_definitions)

    async def async_chat(self, *,
                         messages: List[Dict[str, Any]],
                         tools: Optional[List[Callable[..., Any]]] = None,
                         response_model: Optional[Type[T]] = None,
                         force_tool_call: bool = False,
                         reasoning_effort: Optional[ReasoningEffort] = None,
                         max_tokens: Optional[int] = None,
                         temperature: Optional[float] = None
                         ) -> ChatModelResponse[T]:

        tool_definitions = ChatModel._prepare_tools(tools=tools)
        payload: Dict[str, Any] = self._prepare_payload(messages=messages,
                                                        tools=list(tool_definitions.values()),
                                                        response_model=response_model,
                                                        force_tool_call=force_tool_call,
                                                        reasoning_effort=reasoning_effort,
                                                        max_completion_tokens=max_tokens,
                                                        temperature=temperature)
        response = await self.async_client.chat.completions.create(**payload)
        return ChatModel._parse_response(response, response_model, tool_definitions)
