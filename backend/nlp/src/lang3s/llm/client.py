import re
import textwrap
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Generator,
    Literal,
    NotRequired,
    Sequence,
    Type,
    TypedDict,
    TypeVar,
    Unpack,
)

from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError
from openai.types import CompletionUsage, ReasoningEffort
from openai.types.chat import (
    ChatCompletionMessageCustomToolCall,
    ChatCompletionMessageFunctionToolCall,
)
from openai.types.chat.chat_completion_chunk import ChoiceDeltaToolCall
from openai.types.shared_params import ResponseFormatJSONSchema
from openai.types.shared_params.response_format_json_schema import JSONSchema
from pydantic import BaseModel

from lang3s import config
from lang3s.utils.async_helper import async_generator_to_sync
from lang3s.utils.decorators import retry_async_gen

from ..services.local_llm_app import adapter_ids
from .events import (
    LLMEvent,
    LLMEventType,
    ToolCallDelta,
)
from .formatters import to_structured_format
from .messages import Message, format_messages_for_model
from .tools import LLMTool, ToolCall, parse_tool_call_arguments


class ChatCompletionParams(TypedDict):
    tools: NotRequired[list[Callable[..., Any]]]
    reasoning_effort: NotRequired[ReasoningEffort]
    max_tokens: NotRequired[int]
    temperature: NotRequired[float]
    top_p: NotRequired[float]
    frequency_penalty: NotRequired[float]
    presence_penalty: NotRequired[float]
    seed: NotRequired[int]
    stop: NotRequired[str | Sequence[str]]
    extra_body: NotRequired[dict[str, Any]]
    tool_choice: NotRequired[Literal["required", "auto", "none"]]


T = TypeVar("T", bound=BaseModel)


class LLMClient:
    def __init__(
        self,
        model_name: str = config.LLM_MODEL,
        api_key: str = config.LLM_API_KEY,
        llm_host: str = config.LLM_HOST,
    ):
        self.max_retries: int = 3
        self.api_key: str = api_key
        self.base_url: str = f"{llm_host}/v1/"
        self.model_name: str = model_name

    def _get_client(self):
        return AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    @staticmethod
    def _error_to_event(e: Exception) -> LLMEvent:
        text: str = str(e)
        if isinstance(e, APIError):
            text = "API Error: " + text
        elif isinstance(e, APIConnectionError):
            text = "API Connection Error: " + text
        elif isinstance(e, RateLimitError):
            text = "Rate Limit Error: " + text

        return LLMEvent(
            type=LLMEventType.ERROR,
            content=text,
            exception=e,
        )

    async def chat_completion(
        self,
        messages: list[Message],
        tools: list[Callable[..., Any]] | None = None,
        stream: bool = False,
        response_model: Type[T] | None = None,
        **kwargs: Unpack[ChatCompletionParams],
    ) -> AsyncGenerator[LLMEvent[T], None]:
        available_tools = LLMClient._prepare_tools(tools)
        if not messages:
            return

        max_completion_tokens = kwargs.pop("max_tokens", None)
        completion_args: dict[str, Any] = {
            "model": self.model_name,
            "stream": stream,
            "max_completion_tokens": max_completion_tokens,
            **kwargs,
        }

        if available_tools:
            completion_args["tools"] = [t.schema for _, t in available_tools.items()]

        if response_model:
            if (
                config.LLM_SUPPORTS_STRUCTURED_OUTPUT
                and "gpt-oss" not in self.model_name.lower()
            ):
                raw = response_model.model_json_schema()
                description = raw.pop("description", None)
                completion_args["response_format"] = ResponseFormatJSONSchema(
                    json_schema=JSONSchema(
                        name=response_model.__name__,
                        strict=False,
                        description=description,
                        schema=raw,
                    ),
                    type="json_schema",
                )
            else:
                last_message = messages[-1]
                if last_message.role not in ("user", "system"):
                    raise ValueError(
                        "Cannot set response format for a non system or user message"
                    )
                messages = messages[:-1]
                messages.append(
                    Message(
                        role=last_message.role,
                        content=textwrap.dedent(f"""{last_message.content}
                    Respond only in JSON. The output must strictly follow this structure:
                    {to_structured_format(response_model)}
                    Do not include any preamble, thinking blocks, or markdown code fences."""),
                    )
                )

        completion_args["messages"] = format_messages_for_model(messages)

        @retry_async_gen(
            on_exceed_attempts=lambda e: self._error_to_event(e),
            no_retry=[APIError],
            max_retries=self.max_retries,
            decay_base=3,
        )
        async def perform_chat(
            async_client: AsyncOpenAI,
        ) -> AsyncGenerator[LLMEvent[T], None]:
            method = self._stream_completion if stream else self._no_stream_completion
            async for chunk in method(
                client=async_client,
                tool_map=available_tools,
                response_model=response_model,
                **completion_args,
            ):
                yield chunk
            return

        client = self._get_client()
        try:
            async for event in perform_chat(async_client=client):
                yield event
        finally:
            await client.close()
        return

    @staticmethod
    def _parse_response(
        response_model: Type[T] | None, content: str | None
    ) -> T | Exception | None:
        if content and response_model:
            try:
                content: str = re.sub(r"^(```[a-z]+\n|')", "", content.strip())
                content = re.sub(r"(```|')$", "", content.strip()).strip()
                return response_model.model_validate_json(content)
            except Exception as e:
                return e
        return None

    @staticmethod
    def _prepare_tools(tools: list[Callable[..., Any]] | None) -> dict[str, LLMTool]:
        tool_definitions: dict[str, LLMTool] = dict()
        if tools:
            for func in tools:
                if not isinstance(func, Callable) or not hasattr(func, "tool"):
                    raise ValueError(
                        "tool must be a callable or a function and must have the tool decorator"
                    )
                else:
                    tool_definitions[func.tool.name] = func.tool  # type: ignore
        return tool_definitions

    @staticmethod
    def _prepare_tool_calls(
        tools: dict[str, LLMTool],
        tool_calls: list[
            ChatCompletionMessageFunctionToolCall
            | ChatCompletionMessageCustomToolCall
            | dict[str, Any]
        ],
    ) -> Generator[LLMEvent[T], None, None]:
        for tc in tool_calls or []:
            llm_tool = tools[tc["name"]]
            yield LLMEvent(
                type=LLMEventType.TOOL_CALL_COMPLETE,
                tool_call=ToolCall(
                    tool_call_id=tc["id"],
                    name=tc["name"],
                    arguments=parse_tool_call_arguments(tc["arguments"]),
                    arguments_type=llm_tool.arg_validator,
                    is_async=llm_tool.is_async,
                    function=llm_tool.function,
                ),
            )

    @staticmethod
    def _finish_structured_outputs(
        response_model: type[T] | None,
        final_response: str,
        finish_reason: str,
        usage: CompletionUsage | None,
    ):
        parsed = LLMClient._parse_response(response_model, final_response)
        if parsed and isinstance(parsed, Exception):
            yield LLMEvent[T](
                content=final_response,
                finish_reason=finish_reason,
                exception=parsed,
                parsed=None,
                type=LLMEventType.PARSE_ERROR,
                total_tokens=usage.total_tokens if usage else None,
            )
        yield LLMEvent[T](
            content=final_response,
            finish_reason=finish_reason,
            parsed=parsed if parsed and not isinstance(parsed, Exception) else None,  # type: ignore
            type=LLMEventType.COMPLETE,
            total_tokens=usage.total_tokens if usage else None,
        )

    @staticmethod
    async def _stream_completion(
        client: AsyncOpenAI,
        tool_map: dict[str, LLMTool],
        response_model: Type[T] | None = None,
        **kwargs,
    ):
        response = await client.chat.completions.create(**kwargs)
        finish_reason: str | None = None
        final_response: str | T = ""
        tool_calls: dict[int, dict[str, Any]] = {}
        usage: CompletionUsage | None = None

        async for chunk in response:  # type:ignore
            if response_model and issubclass(type(chunk), response_model):
                final_response = chunk

            if chunk.usage:
                usage = chunk.usage

            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            delta = choice.delta

            if choice.finish_reason:
                finish_reason = choice.finish_reason

            if delta.content:
                content = delta.content
                final_response += content
                yield LLMEvent[T](
                    content=content,
                    type=LLMEventType.TEXT_DELTA,
                )

            if delta.tool_calls:
                tool_delta: ChoiceDeltaToolCall
                for tool_delta in delta.tool_calls:
                    idx = tool_delta.index
                    if idx not in tool_calls:
                        tool_calls[idx] = {
                            "id": tool_delta.id,
                            "name": "",
                            "arguments": "",
                        }

                    if tool_delta.function:
                        if tool_delta.function.name:
                            tool_calls[idx]["name"] = tool_delta.function.name
                            yield LLMEvent[T](
                                type=LLMEventType.TOOL_CALL_START,
                                tool_call_delta=ToolCallDelta(**tool_calls[idx]),
                            )

                        if tool_delta.function.arguments:
                            tool_calls[idx]["arguments"] += (
                                tool_delta.function.arguments
                            )
                            yield LLMEvent[T](
                                type=LLMEventType.TOOL_CALL_DELTA,
                                tool_call_delta=ToolCallDelta(**tool_calls[idx]),
                            )

        for tool_call_event in LLMClient._prepare_tool_calls(
            tool_map, list(tool_calls.values())
        ):
            yield tool_call_event

        for event in LLMClient._finish_structured_outputs(
            response_model=response_model,
            final_response=final_response,
            finish_reason=finish_reason or "unknown",
            usage=usage,
        ):
            yield event

    @staticmethod
    async def _no_stream_completion(
        client: AsyncOpenAI,
        tool_map: dict[str, LLMTool],
        response_model: Type[T] | None = None,
        **kwargs,
    ):
        event = await client.chat.completions.create(**kwargs)
        choice = event.choices[0]
        message = choice.message

        for tool_call_event in LLMClient._prepare_tool_calls(
            tool_map,
            message.tool_calls,  # type: ignore
        ):
            yield tool_call_event

        for event in LLMClient._finish_structured_outputs(
            response_model=response_model,
            final_response=message.content or "",
            finish_reason=choice.finish_reason,
            usage=event.usage,
        ):
            yield event

    def sync_chat_completion_last_event(
        self,
        messages: list[Message],
        response_model: type[T] | None = None,
        **kwargs: Unpack[ChatCompletionParams],
    ) -> LLMEvent[T]:
        result: LLMEvent[T] | None = None

        for event in self.sync_chat_completion(
            messages=messages,
            stream=False,
            response_model=response_model,
            **kwargs,
        ):
            if event.type == LLMEventType.COMPLETE:
                result = event
            elif (
                event.type == LLMEventType.ERROR
                or event.type == LLMEventType.PARSE_ERROR
            ):
                return event
        if result:
            return result
        return LLMEvent[T](
            type=LLMEventType.ERROR, exception=Exception("LLM did not complete")
        )

    async def chat_completion_last_event(
        self,
        messages: list[Message],
        response_model: type[T] | None = None,
        stream: bool = False,
        **kwargs: Unpack[ChatCompletionParams],
    ) -> LLMEvent[T]:
        result: LLMEvent[T] | None = None

        async for event in self.chat_completion(
            messages=messages, stream=stream, response_model=response_model, **kwargs
        ):
            if event.type == LLMEventType.COMPLETE:
                result = event
            elif (
                event.type == LLMEventType.ERROR
                or event.type == LLMEventType.PARSE_ERROR
            ):
                return event
        if result:
            return result
        return LLMEvent[T](
            type=LLMEventType.ERROR, exception=Exception("LLM did not complete")
        )

    def sync_chat_completion(
        self,
        messages: list[Message],
        stream: bool = False,
        response_model: Type[T] | None = None,
        **kwargs: Unpack[ChatCompletionParams],
    ) -> Generator[LLMEvent[T], None, None]:
        for event in async_generator_to_sync(
            lambda: self.chat_completion(
                messages=messages,
                stream=stream,
                response_model=response_model,
                **kwargs,
            )
        ):
            yield event


class LoRaClient(LLMClient):
    def __init__(self):
        super().__init__(
            model_name="LoraModel",
            api_key="no-key",
            llm_host=config.PROXY_HOST,
        )

    def _extend_extra_body(
        self,
        extra_body: dict[str, Any],
        adapter_name: str | None,
    ) -> dict[str, Any]:
        extra_body.update(
            {
                "cache_prompt": False,
                "slot_id": -1,
            }
        )
        if adapter_name and adapter_name in adapter_ids:
            extra_body["lora"] = [{"id": adapter_ids[adapter_name], "scale": 1.0}]
        return extra_body

    async def chat_completion(
        self,
        messages: list[Message],
        tools: list[Callable[..., Any]] | None = None,
        stream: bool = False,
        response_model: Type[T] | None = None,
        adapter_name: str | None = None,
        **kwargs: Unpack[ChatCompletionParams],
    ) -> AsyncGenerator[LLMEvent[T], None]:
        kwargs["extra_body"] = self._extend_extra_body(
            kwargs.get("extra_body", {}), adapter_name
        )
        async for event in super().chat_completion(
            messages=messages,
            tools=tools,
            stream=stream,
            response_model=response_model,
            **kwargs,
        ):
            yield event

    def sync_chat_completion_last_event(
        self,
        messages: list[Message],
        response_model: type[T] | None = None,
        adapter_name: str | None = None,
        **kwargs: Unpack[ChatCompletionParams],
    ) -> LLMEvent[T]:
        kwargs["extra_body"] = self._extend_extra_body(
            kwargs.get("extra_body", {}), adapter_name
        )
        return super().sync_chat_completion_last_event(
            messages=messages,
            response_model=response_model,
            **kwargs,
        )

    async def chat_completion_last_event(
        self,
        messages: list[Message],
        response_model: type[T] | None = None,
        adapter_name: str | None = None,
        **kwargs: Unpack[ChatCompletionParams],
    ) -> LLMEvent[T]:
        kwargs["extra_body"] = self._extend_extra_body(
            kwargs.get("extra_body", {}), adapter_name
        )
        return await super().chat_completion_last_event(
            messages=messages, response_model=response_model, **kwargs
        )

    def sync_chat_completion(
        self,
        messages: list[Message],
        stream: bool = False,
        response_model: Type[T] | None = None,
        adapter_name: str | None = None,
        **kwargs: Unpack[ChatCompletionParams],
    ) -> Generator[LLMEvent[T], None, None]:
        kwargs["extra_body"] = self._extend_extra_body(
            kwargs.get("extra_body", {}), adapter_name
        )
        for event in super().sync_chat_completion(
            messages=messages,
            stream=stream,
            response_model=response_model,
            **kwargs,
        ):
            yield event
