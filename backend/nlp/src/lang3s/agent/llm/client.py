import asyncio
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Generator,
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
from lang3s.agent.llm.chat_completion_events import (
    ChatCompletionEvent,
    ChatCompletionEventType,
    TokenCompletionUsage,
    ToolCall,
    ToolCallDelta,
    parse_tool_call_arguments,
)
from lang3s.agent.llm.tools import LLMTool
from lang3s.utils.async_helper import async_generator_to_sync
from lang3s.utils.decorators import retry_async_gen

T = TypeVar("T", bound=BaseModel)


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


class LlmClient:
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
        return AsyncOpenAI(
            api_key=config.LLM_API_KEY,
            base_url=f"{config.LLM_HOST}/v1/",
        )

    @staticmethod
    def _error_to_event(e: Exception) -> ChatCompletionEvent:
        text: str = str(e)
        if isinstance(e, APIError):
            text = "API Error: " + text
        elif isinstance(e, APIConnectionError):
            text = "API Connection Error: " + text
        elif isinstance(e, RateLimitError):
            text = "Rate Limit Error: " + text

        return ChatCompletionEvent(
            type=ChatCompletionEventType.ERROR,
            error=text,
        )

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[Callable[..., Any]] | None = None,
        force_tool_call: bool = False,
        stream: bool = False,
        response_model: Type[T] | None = None,
        **kwargs: Unpack[ChatCompletionParams],
    ) -> AsyncGenerator[ChatCompletionEvent[T], None]:
        client = self._get_client()
        available_tools = LlmClient._prepare_tools(tools)

        completion_args: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "stream": stream,
            "stream_options": {"include_usage": True},
            **kwargs,
        }

        if available_tools:
            completion_args["tools"] = [t.schema for _, t in available_tools.items()]
            completion_args["tool_choice"] = "required" if force_tool_call else "auto"

        if response_model:
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

        @retry_async_gen(
            on_exceed_attempts=lambda e: self._error_to_event(e),
            no_retry=[APIError],
            max_retries=self.max_retries,
            decay_base=3,
        )
        async def chat():
            if stream:
                async for chunk in self._stream_completion(
                    client=client,
                    tools=available_tools,
                    response_model=response_model,
                    **completion_args,
                ):
                    yield chunk
            else:
                async for chunk in self._no_stream_completion(
                    client=client,
                    tools=available_tools,
                    response_model=response_model,
                    **completion_args,
                ):
                    yield chunk
            return

        async for event in chat():
            yield event

        await client.close()
        return

    @staticmethod
    def _parse_response(
        response_model: Type[T] | None, content: str | None
    ) -> T | Exception | None:
        if content and response_model:
            try:
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
    ) -> Generator[ChatCompletionEvent[T], None, None]:
        for tc in tool_calls:
            llm_tool = tools[tc["name"]]
            yield ChatCompletionEvent(
                type=ChatCompletionEventType.TOOL_CALL_COMPLETE,
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
        response_model: Type[T] | None,
        final_response: str,
        finish_reason: str,
        usage: CompletionUsage | None,
    ) -> Generator[ChatCompletionEvent[T], None, None]:
        parsed = LlmClient._parse_response(response_model, final_response)
        if parsed and isinstance(parsed, Exception):
            yield ChatCompletionEvent[T](
                content=final_response,
                finish_reason=finish_reason,
                error=str(parsed),
                parsed=None,
                type=ChatCompletionEventType.PARSE_ERROR,
            )
        yield ChatCompletionEvent[T](
            content=final_response,
            finish_reason=finish_reason,
            parsed=parsed if parsed and not isinstance(parsed, Exception) else None,
            usage=TokenCompletionUsage(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )
            if usage
            else None,
            type=ChatCompletionEventType.COMPLETE,
        )

    @staticmethod
    async def _stream_completion(
        client: AsyncOpenAI,
        tools: dict[str, LLMTool],
        response_model: Type[T] | None = None,
        **kwargs,
    ):
        response = await client.chat.completions.create(**kwargs)
        finish_reason: str | None = None
        final_response: str = ""
        tool_calls: dict[int, dict[str, Any]] = {}
        usage: CompletionUsage | None = None

        async for chunk in response:  # type:ignore
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
                yield ChatCompletionEvent[T](
                    content=content,
                    type=ChatCompletionEventType.TEXT_DELTA,
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
                            yield ChatCompletionEvent[T](
                                type=ChatCompletionEventType.TOOL_CALL_START,
                                tool_call_delta=ToolCallDelta(**tool_calls[idx]),
                            )

                        if tool_delta.function.arguments:
                            tool_calls[idx]["arguments"] += (
                                tool_delta.function.arguments
                            )
                            yield ChatCompletionEvent[T](
                                type=ChatCompletionEventType.TOOL_CALL_DELTA,
                                tool_call_delta=ToolCallDelta(**tool_calls[idx]),
                            )

        for tool_call_event in LlmClient._prepare_tool_calls(
            tools, list(tool_calls.values())
        ):
            yield tool_call_event

        for event in LlmClient._finish_structured_outputs(
            response_model=response_model,
            final_response=final_response,
            finish_reason=finish_reason,
            usage=usage,
        ):
            yield event

    @staticmethod
    async def _no_stream_completion(
        client: AsyncOpenAI,
        tools: dict[str, LLMTool],
        response_model: Type[T] | None = None,
        **kwargs,
    ):
        event = await client.chat.completions.create(**kwargs)
        choice = event.choices[0]
        message = choice.message

        for tool_call_event in LlmClient._prepare_tool_calls(tools, message.tool_calls):
            yield tool_call_event

        for event in LlmClient._finish_structured_outputs(
            response_model=response_model,
            final_response=message.content,
            finish_reason=choice.finish_reason,
            usage=event.usage,
        ):
            yield event

    def sync_chat_completion(
        self,
        messages: list[dict[str, Any]],
        stream: bool = False,
        response_model: Type[T] | None = None,
        **kwargs: Unpack[ChatCompletionParams],
    ) -> Generator[ChatCompletionEvent[T], None, None]:
        for event in async_generator_to_sync(
            lambda: self.chat_completion(
                messages=messages,
                stream=stream,
                response_model=response_model,
                **kwargs,
            )
        ):
            yield event


async def main():
    client = LlmClient(model_name="")
    for event in client.sync_chat_completion(
        messages=[
            {
                "role": "user",
                "content": "Please greet Sam Wise.",
            }
        ],
        # tools=[get_message],
        stream=True,
    ):
        print(event)


if __name__ == "__main__":
    asyncio.run(main())
    # main()
