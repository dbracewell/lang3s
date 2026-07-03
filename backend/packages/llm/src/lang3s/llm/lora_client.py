from typing import Any, AsyncGenerator, Callable, Type, TypeVar, Unpack

from pydantic import BaseModel

from .client import ChatCompletionParams, LLMClient
from .typedefs import LLMEvent, Message

adapters = {"claim": "claim_extraction.gguf"}
adapter_ids = {v: i for i, v in enumerate(adapters.values())}
T = TypeVar("T", bound=BaseModel)


class LoRaClient(LLMClient):
    def __init__(self):
        super().__init__(
            model_name="Llama.cpp",
            api_key="no-key",
            llm_host="http://localhost:23002/v1",
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

    async def chat(
        self,
        messages: list[Message],
        stream: bool = False,
        tools: list[Callable[..., Any]] | None = None,
        response_model: Type[T] | None = None,
        adapter_name: str | None = None,
        **kwargs: Unpack[ChatCompletionParams],
    ) -> AsyncGenerator[LLMEvent[T], None]:

        kwargs["extra_body"] = self._extend_extra_body(
            kwargs.get("extra_body", {}), adapter_name
        )
        async for event in super().chat(
            messages=messages,
            tools=tools,
            stream=stream,
            response_model=response_model,
            **kwargs,
        ):
            yield event

    async def chat_last_event(
        self,
        messages: list[Message],
        tools: list[Callable[..., Any]] | None = None,
        response_model: Type[T] | None = None,
        adapter_name: str | None = None,
        **kwargs: Unpack[ChatCompletionParams],
    ) -> LLMEvent[T]:
        kwargs["extra_body"] = self._extend_extra_body(
            kwargs.get("extra_body", {}), adapter_name
        )
        return await super().chat_last_event(
            messages=messages,
            response_model=response_model,
            **kwargs,
        )

    def sync_chat_last_event(
        self,
        messages: list[Message],
        tools: list[Callable[..., Any]] | None = None,
        response_model: Type[T] | None = None,
        adapter_name: str | None = None,
        **kwargs: Unpack[ChatCompletionParams],
    ) -> LLMEvent[T]:
        kwargs["extra_body"] = self._extend_extra_body(
            kwargs.get("extra_body", {}), adapter_name
        )
        return super().sync_chat_last_event(
            messages=messages,
            response_model=response_model,
            **kwargs,
        )
