from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator, Generic, Type, TypeVar, Unpack

from pydantic import BaseModel

from lang3s.agent.ref.events import AgentEvent, AgentEventType
from lang3s.agent.ref.session import Session
from lang3s.llm.client import ChatCompletionParams
from lang3s.llm.events import (
    LLMEventType,
)
from lang3s.llm.tools import ToolCall, ToolResult

STRATEGY_RESPONSE_TYPE = TypeVar("STRATEGY_RESPONSE_TYPE", bound=BaseModel)


@dataclass
class StrategyResult(Generic[STRATEGY_RESPONSE_TYPE]):
    content: list[str] = field(default_factory=list)
    parsed: list[STRATEGY_RESPONSE_TYPE] = field(default_factory=list)
    exception: Exception | None = field(default=None)

    @staticmethod
    def from_exception(exception: Exception) -> StrategyResult[STRATEGY_RESPONSE_TYPE]:
        strategy_result = StrategyResult()
        strategy_result.exception = exception
        return strategy_result

    @staticmethod
    def from_agent_event(
        agent_event: AgentEvent,
    ) -> StrategyResult[STRATEGY_RESPONSE_TYPE]:
        strategy_result = StrategyResult()
        strategy_result.update(agent_event)
        return strategy_result

    def update(self, agent_event: AgentEvent) -> None:
        if agent_event.content:
            self.content.append(agent_event.content)
        if agent_event.parsed:
            self.parsed.append(agent_event.parsed)
        if agent_event.exception:
            self.exception = agent_event.exception


class Strategy(ABC, Generic[STRATEGY_RESPONSE_TYPE]):
    def __init__(
        self, response_model: Type[STRATEGY_RESPONSE_TYPE] | None = None
    ) -> None:
        self._response_model: Type[STRATEGY_RESPONSE_TYPE] | None = response_model

    @abstractmethod
    async def run(self, session: Session) -> StrategyResult[STRATEGY_RESPONSE_TYPE]:
        raise NotImplementedError()

    @staticmethod
    def convert_tools(response: list[AgentEvent | ToolCall]) -> list[ToolCall]:
        tool_calls = []
        for tool_call in response:
            if isinstance(tool_call, ToolCall):
                tool_calls.append(tool_call)
            elif tool_call.type == AgentEventType.TOOL_CALL_COMPLETE:
                tool_calls.append(tool_call.tool_call)
        return tool_calls

    async def _async_run_tools(
        self, session: Session, response: list[AgentEvent | ToolCall]
    ) -> list[ToolResult]:
        tool_calls = self.convert_tools(response)
        if not tool_calls:
            return []

        # Add the tool call messages
        session.state.add_assistant_message(content="", tool_calls=tool_calls)
        session.state.max_progress += len(tool_calls)

        async def handle_tool_call(tool_call: ToolCall) -> ToolResult:
            tool_response = await tool_call.async_invoke()
            session.state.progress += 1
            session.state.add_tool_call(
                tool_call=tool_call,
                content=json.dumps(tool_response.__dict__),
            )
            session.forward_event(AgentEvent.tool_call_result_event(tool_response))
            return tool_response

        tasks = [handle_tool_call(tc) for tc in tool_calls]
        tool_call_responses = list(await asyncio.gather(*tasks))
        return tool_call_responses

    async def _chat_to_completion(
        self, session: Session, **kwargs: Unpack[ChatCompletionParams]
    ) -> AgentEvent[STRATEGY_RESPONSE_TYPE]:
        result = None
        async for event in self._async_chat(session, **kwargs):
            if event.type == AgentEventType.TEXT_COMPLETE:
                result = event
            elif event.type == AgentEventType.ERROR:
                return event
        return result

    async def _chat_for_tools(
        self, session: Session, **kwargs: Unpack[ChatCompletionParams]
    ) -> list[ToolCall] | AgentEvent[STRATEGY_RESPONSE_TYPE]:
        tool_calls = []
        async for event in self._async_chat(session, **kwargs):
            if event.type == AgentEventType.TOOL_CALL_COMPLETE:
                tool_calls.append(event.tool_call)
            elif event.type == AgentEventType.ERROR:
                return event
        return tool_calls

    async def _async_chat(
        self,
        session: Session,
        force_tool_call: bool = False,
        use_tools: bool = False,
        **kwargs: Unpack[ChatCompletionParams],
    ) -> AsyncGenerator[AgentEvent[STRATEGY_RESPONSE_TYPE], None]:
        async for event in session.client.chat_completion(
            messages=session.state.messages,
            stream=True,
            tools=session.available_tools if use_tools else None,
            response_model=self._response_model if not use_tools else None,
            force_tool_call=force_tool_call,
            **kwargs,
        ):
            agent_event = None
            if event.type == LLMEventType.TOOL_CALL_START:
                if not event.tool_call:
                    continue
                agent_event = AgentEvent.tool_call_start_event(event.tool_call)
            if event.type == LLMEventType.TOOL_CALL_COMPLETE:
                if not event.tool_call:
                    continue
                agent_event = AgentEvent.tool_call_complete_event(event.tool_call)
            elif event.type == LLMEventType.TEXT_DELTA:
                agent_event = AgentEvent.text_delta_event(event.content)
            elif event.type == LLMEventType.COMPLETE:
                agent_event = AgentEvent.text_complete_event(
                    event.content, event.parsed
                )
                if event.content:
                    session.state.add_assistant_message(content=event.content)
            elif (
                event.type == LLMEventType.ERROR
                or event.type == LLMEventType.PARSE_ERROR
            ):
                agent_event = AgentEvent.error_event(event.exception)

            if agent_event:
                session.forward_event(agent_event)
                yield agent_event
