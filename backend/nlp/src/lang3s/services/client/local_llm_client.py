import json
import re
from dataclasses import dataclass
from typing import Any, Literal

import instructor
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion
from pydantic import BaseModel

from lang3s import config
from lang3s.llm import Message
from lang3s.llm.messages import format_messages_for_model
from lang3s.llm.tools import LLMTool, ToolCall, parse_tool_call_arguments
from lang3s.services.local_llm_app import adapter_ids
from lang3s.utils.async_helper import run_sync
from lang3s.utils.decorators import retry
from lang3s.utils.logger import get_logger

logger = get_logger("LOCAL_LLM_CLIENT")


@dataclass
class LocalLLMClientResult[T]:
    content: str | None = None
    parsed: T | None = None
    tool_calls: list[ToolCall] | None = None


class LocalLLMClient:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=f"{config.PROXY_HOST}/v1",
            api_key="sk-no-key",
        )
        self.structured_client = instructor.from_openai(
            self.client,
            mode=instructor.Mode.JSON_SCHEMA,
        )

    def sync_generate[T: BaseModel](
        self,
        messages: list[Message],
        temperature: float = 0.2,
        max_tokens: int | None = None,
        response_model: type[T] | None = None,
        tools: list[LLMTool] | None = None,
        adapter_name: str | None = None,
        parse_response_as_json: bool = False,
        tool_choice: Literal["auto", "required"] | dict[str, Any] | None = None,
    ) -> LocalLLMClientResult[T]:
        return run_sync(
            self.generate(
                messages,
                temperature,
                max_tokens,
                response_model,
                tools,
                adapter_name,
                parse_response_as_json,
                tool_choice,
            )
        )

    async def generate[T: BaseModel](
        self,
        messages: list[Message],
        temperature: float = 0.2,
        max_tokens: int | None = None,
        response_model: type[T] | None = None,
        tools: list[LLMTool] | None = None,
        adapter_name: str | None = None,
        parse_response_as_json: bool = False,
        tool_choice: Literal["auto", "required"] | dict[str, Any] | None = None,
    ) -> LocalLLMClientResult[T]:
        completion_args: dict[str, Any] = {
            "model": "locallm",
            "stream": False,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": format_messages_for_model(messages),
        }

        extra_body = None
        if adapter_name and adapter_name in adapter_ids:
            extra_body = {"lora": [{"id": adapter_ids[adapter_name], "scale": 1.0}]}

        if response_model:
            parsed_response = await self.structured_client.chat.completions.create(
                **completion_args,
                response_model=response_model,
                extra_body=extra_body,
            )
            return LocalLLMClientResult(parsed=parsed_response)

        if tools:
            completion_args["tools"] = [t.schema for t in tools]
            completion_args["tool_choice"] = tool_choice

        response: ChatCompletion = await self.client.chat.completions.create(  # type:ignore
            **completion_args,
            extra_body=extra_body,
        )

        message = response.choices[0].message

        if tools and message.tool_calls:
            parsed_tool_calls = []
            for tc in message.tool_calls:
                llm_tool = next((t for t in tools if t.name == tc.function.name), None)
                if not llm_tool:
                    continue

                parsed_tool_calls.append(
                    ToolCall(
                        tool_call_id=tc.id,
                        name=tc.function.name,
                        arguments=parse_tool_call_arguments(tc.function.arguments),
                        arguments_type=llm_tool.arg_validator,
                        is_async=llm_tool.is_async,
                        function=llm_tool.function,
                    )
                )
            return LocalLLMClientResult(tool_calls=parsed_tool_calls)

        if message.content and parse_response_as_json:
            content = re.sub(
                r"^```json\s*",
                "",
                message.content.strip(),
                flags=re.MULTILINE,
            )
            content = re.sub(r"```$", "", content.strip()).strip()
            return LocalLLMClientResult(parsed=json.loads(content))

        return LocalLLMClientResult(content=message.content)
