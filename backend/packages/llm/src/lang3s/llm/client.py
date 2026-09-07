import re
from collections.abc import AsyncGenerator, Generator, Sequence
from typing import (
    Any,
    Callable,
    Literal,
    NotRequired,
    Type,
    TypedDict,
    TypeVar,
    Unpack,
    cast,
)

from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError
from openai.lib.streaming.chat import ChatCompletionStreamEvent, ContentDeltaEvent
from openai.types import CompletionUsage
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessage,
    ParsedChatCompletion,
    ParsedChatCompletionMessage,
)
from openai.types.shared_params import ResponseFormatJSONSchema
from openai.types.shared_params.response_format_json_schema import JSONSchema
from pydantic import BaseModel

from lang3s.core import config
from lang3s.core.async_extras import async_generator_to_sync
from lang3s.core.decorators import async_retry, retry_async_gen

from .helpers import format_messages_for_model
from .typedefs import (
    AvailableTools,
    LLMEvent,
    LLMEventType,
    Message,
)


class ChatCompletionParams(TypedDict):
    reasoning_effort: NotRequired[Any]  # pyright: ignore[reportExplicitAny] # Assuming your ReasoningEffort type
    temperature: NotRequired[float]
    top_p: NotRequired[float]
    frequency_penalty: NotRequired[float]
    presence_penalty: NotRequired[float]
    seed: NotRequired[int]
    stop: NotRequired[str | Sequence[str]]
    extra_body: NotRequired[dict[str, Any]]  # pyright: ignore[reportExplicitAny]
    tool_choice: NotRequired[Literal["required", "auto", "none"] | dict[str, Any]]  # pyright: ignore[reportExplicitAny]
    max_completion_tokens: NotRequired[int]
    modalities: NotRequired[list[Literal["text", "audio"]]]
    audio: NotRequired[dict[str, Any]]  # pyright: ignore[reportExplicitAny]
    prediction: NotRequired[dict[str, Any]]  # pyright: ignore[reportExplicitAny]
    parallel_tool_calls: NotRequired[bool]
    stream_options: NotRequired[dict[str, Any]]  # pyright: ignore[reportExplicitAny] # E.g., {"include_usage": True}
    n: NotRequired[int]
    logit_bias: NotRequired[dict[str, int]]  #
    logprobs: NotRequired[bool]
    top_logprobs: NotRequired[int]
    extra_headers: NotRequired[dict[str, str]]
    extra_query: NotRequired[dict[str, Any]]  # pyright: ignore[reportExplicitAny]
    timeout: NotRequired[float | None]


T = TypeVar("T", bound=BaseModel)


class LLMClient:
    def __init__(
        self,
        model_name: str | None = None,
        api_key: str | None = None,
        llm_host: str | None = None,
    ):
        self.max_retries: int = 3
        self.api_key: str = api_key or config.LLM_API_KEY
        self.base_url: str = llm_host or config.LLM_HOST
        self.model_name: str = model_name or config.LLM_MODEL
        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=120.0,
        )

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

    def _prepare_completion_params(
        self,
        messages: list[Message],
        stream: bool,
        available_tools: AvailableTools,
        response_model: Type[T] | None = None,
        **kwargs: Unpack[ChatCompletionParams],
    ):
        if stream:
            stream_options = kwargs.pop("stream_options", None) or {}
            stream_options["include_usage"] = True
            kwargs["stream_options"] = stream_options
        else:
            kwargs.pop("stream_options", None)

        completion_args: dict[str, Any] = {
            "model": self.model_name,
            **kwargs,
        }

        if available_tools:
            completion_args["tools"] = [t.schema for _, t in available_tools.items()]

        if response_model and config.LLM_SUPPORTS_STRUCTURED_OUTPUT:

            def clean_schema(raw_schema: Any) -> Any:
                if isinstance(raw_schema, dict):
                    raw_schema.pop("title", None)
                    for key, value in list(raw_schema.items()):
                        if isinstance(value, (dict, list)):
                            clean_schema(value)
                elif isinstance(raw_schema, list):
                    for item in raw_schema:
                        clean_schema(item)
                return raw_schema

            sanitized_schema = clean_schema(response_model.model_json_schema())
            description = sanitized_schema.pop("description", "")
            completion_args["response_format"] = ResponseFormatJSONSchema(
                json_schema=JSONSchema(
                    name=response_model.__name__,
                    strict=True,
                    schema=sanitized_schema,
                    description=description,
                ),
                type="json_schema",
            )

        completion_args["messages"] = format_messages_for_model(messages)
        return completion_args

    @staticmethod
    def _parse_content_message(
        message: ParsedChatCompletionMessage | ChatCompletionMessage,
        usage: CompletionUsage | None,
        finish_reason: str,
        response_model: Type[T] | None = None,
    ):
        if message.content and response_model:
            try:
                content: str = re.sub(r"^(```[a-z]+\n|')", "", message.content.strip())
                content = re.sub(r"(```|')$", "", content.strip()).strip()
                parsed_result = response_model.model_validate_json(content)
                return LLMEvent[T](
                    content=message.content,
                    finish_reason=finish_reason,
                    parsed=parsed_result,
                    type=LLMEventType.COMPLETE,
                    total_tokens=usage.total_tokens if usage else None,
                )
            except Exception as e:
                return LLMEvent[T](
                    content=message.content,
                    finish_reason=finish_reason,
                    exception=e,
                    parsed=None,
                    type=LLMEventType.PARSE_ERROR,
                    total_tokens=usage.total_tokens if usage else None,
                )
        else:
            return LLMEvent[T](
                content=message.content,
                finish_reason=finish_reason,
                parsed=None,
                type=LLMEventType.COMPLETE,
                total_tokens=usage.total_tokens if usage else None,
            )

    async def chat(
        self,
        messages: list[Message],
        stream: bool = False,
        tools: list[Callable[..., Any]] | None = None,
        response_model: Type[T] | None = None,
        **kwargs: Unpack[ChatCompletionParams],
    ) -> AsyncGenerator[LLMEvent[T], None]:

        if not messages:
            return

        available_tools = AvailableTools(tools or [])
        completion_args = self._prepare_completion_params(
            messages,
            stream,
            available_tools,
            response_model,
            **kwargs,
        )

        if stream:

            @retry_async_gen(
                on_exceed_attempts=lambda e: self._error_to_event(e),
                no_retry=[APIError],
                max_retries=self.max_retries,
                delay_base=3,
            )
            async def async_chat(
                **chat_args,
            ) -> AsyncGenerator[
                ChatCompletionStreamEvent | ParsedChatCompletion[Any], None
            ]:
                async with self._client.chat.completions.stream(
                    **chat_args
                ) as response:
                    async for chunk in response:
                        yield chunk
                    yield await response.get_final_completion()

            async for chunk in async_chat(**completion_args):
                if isinstance(chunk, ChatCompletionStreamEvent):
                    event = cast(ChatCompletionStreamEvent, chunk)
                    if event.type == "content.delta":
                        delta = cast(ContentDeltaEvent, event)
                        yield LLMEvent(
                            type=LLMEventType.TEXT_DELTA,
                            content=delta.delta,
                        )
                elif isinstance(chunk, ParsedChatCompletion):
                    usage = chunk.usage
                    choice = chunk.choices[0]
                    message = choice.message
                    if message.tool_calls:
                        for tc_event in available_tools.prepare_tool_calls(
                            message.tool_calls
                        ):
                            yield tc_event
                    else:
                        yield self._parse_content_message(
                            message=message,
                            response_model=response_model,
                            usage=usage,
                            finish_reason=choice.finish_reason,
                        )
                    return

        else:

            @async_retry(
                on_exceed_attempts=lambda e: self._error_to_event(e),
                no_retry=[APIError],
                max_retries=self.max_retries,
                delay_base=3,
            )
            async def async_chat() -> ChatCompletion:
                return cast(
                    ChatCompletion,
                    await self._client.chat.completions.create(**completion_args),
                )

            final_response = await async_chat()
            usage = final_response.usage
            choice = final_response.choices[0]
            message = choice.message
            if message.tool_calls:
                for tc_event in available_tools.prepare_tool_calls(message.tool_calls):
                    yield tc_event
            else:
                yield self._parse_content_message(
                    message=message,
                    response_model=response_model,
                    usage=usage,
                    finish_reason=choice.finish_reason,
                )
            return

    async def chat_last_event(
        self,
        messages: list[Message],
        tools: list[Callable[..., Any]] | None = None,
        response_model: Type[T] | None = None,
        **kwargs: Unpack[ChatCompletionParams],
    ) -> LLMEvent[T]:
        response: LLMEvent[T] | None = None
        async for event in self.chat(
            messages=messages,
            tools=tools,
            stream=False,
            response_model=response_model,
            **kwargs,
        ):
            response = event
        if response is None:
            raise ValueError("No response")
        return response

    def sync_chat(
        self,
        messages: list[Message],
        stream: bool = False,
        tools: list[Callable[..., Any]] | None = None,
        response_model: Type[T] | None = None,
        **kwargs: Unpack[ChatCompletionParams],
    ) -> Generator[LLMEvent[T], None, None]:
        for event in async_generator_to_sync(
            self.chat(
                messages=messages,
                stream=stream,
                tools=tools,
                response_model=response_model,
                **kwargs,
            )
        ):
            yield event

    def sync_chat_last_event(
        self,
        messages: list[Message],
        tools: list[Callable[..., Any]] | None = None,
        response_model: Type[T] | None = None,
        **kwargs: Unpack[ChatCompletionParams],
    ) -> LLMEvent[T]:
        response: LLMEvent[T] | None = None
        for event in self.sync_chat(
            messages=messages,
            tools=tools,
            stream=False,
            response_model=response_model,
            **kwargs,
        ):
            response = event
        if response is None:
            raise ValueError("No response")
        return response
