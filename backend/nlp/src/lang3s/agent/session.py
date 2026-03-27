from __future__ import annotations

import json
import traceback
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

import shortuuid

from lang3s import config
from lang3s.llm import LLMClient, Message, ToolCall
from lang3s.llm.token_estimator import estimate_tokens

from ..utils.logger import get_logger

if TYPE_CHECKING:
    from .events import AgentEvent
    from .middleware.base import Middleware


@dataclass
class State:
    task: str = field(default="")
    messages: list[Message] = field(default_factory=list)
    progress: int = field(default=0)
    max_progress: int = field(default=0)
    cache: dict[str, Any] = field(default_factory=dict)
    terminated: bool = field(default=False)
    model_name: str = field(default=config.LLM_MODEL)

    def remove_messages_if(self, filter_fn: Callable[[Message], bool]):
        self.messages = [m for m in self.messages if not filter_fn(m)]

    @property
    def total_token_count(self) -> int:
        return estimate_tokens(self.model_name, self.messages)

    def add_user_message(self, content: str, **kwargs) -> None:
        self.messages.append(Message.user(content=content, **kwargs))

    def add_assistant_message(
        self,
        content: str,
        tool_calls: list[ToolCall] | None = None,
    ) -> None:
        self.messages.append(Message.assistant(content=content, tool_calls=tool_calls))

    def add_system_message(self, content: str) -> None:
        self.messages.append(Message.system(content=content))

    def add_tool_call(
        self,
        content: str,
        tool_call: ToolCall,
    ) -> None:
        self.messages.append(Message.tool(content=content, tool_call=tool_call))


DEFAULT_SYSTEM_MESSAGE = "You are a helpful agent."

logger = get_logger("AGENT_SESSION")


@dataclass
class Session:
    session_id: str = field(default_factory=lambda: shortuuid.uuid())
    model_name: str = field(default=config.LLM_MODEL)
    system_message: str = field(default=DEFAULT_SYSTEM_MESSAGE)
    context_window: int = field(default=config.LLM_CONTEXT_WINDOW)
    max_history: int = field(default=50)
    available_tools: list[Callable[..., Any]] | None = field(default=None)
    _state: State | None = field(default=None, init=False)
    client: LLMClient = field(init=False)
    middleware: list[Middleware] = field(default_factory=list)
    initial_messages: list[Message] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.client = LLMClient(self.model_name)

    @property
    def state(self):
        if self._state is None:
            self._state = State(model_name=self.model_name)
            self._state.add_system_message(content=self.system_message)
            self._state.messages.extend(self.initial_messages)
        return self._state

    @classmethod
    def load(
        cls,
        data: dict[str, Any],
        available_tools: list[Callable[..., Any]] | None = None,
        middleware: list[Middleware] | None = None,
    ) -> Session:
        state = data.pop("_state", None)
        new_session = cls(
            **data, available_tools=available_tools, middleware=middleware or []
        )
        new_session._state = state
        return new_session

    def forward_event(self, event: AgentEvent):
        for middleware in self.middleware:
            middleware(event, self.state)

    def save(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data.pop("_state", {})
        data.pop("response_model", [])
        data.pop("available_tools", None)
        data.pop("client", None)
        data.pop("middleware", [])
        return data

    def reset_state(self) -> None:
        self._state = None

    def compact(self) -> None:
        if self._state is None:
            return
        state = self.state
        total_tokens = self.state.total_token_count

        while (
            total_tokens >= (0.8 * self.context_window)
            or len(state.messages) > self.max_history
        ):
            to_summarize = self.state.messages[1:-4]
            keep_recent = self.state.messages[-4:]
            response = self.client.sync_chat_completion_last_event(
                max_tokens=int(self.context_window * 0.75),
                messages=[
                    Message.system(
                        content="""
    You are a Memory Compaction module. Your goal is to condense a conversation history while preserving:
    User Intent: What was the user trying to achieve?
    Tool Findings: Specific data returned by tools (weather, dates, database IDs).
    State: Changes in the user's preferences or the task progress.
    Constraint: Convert JSON tool outputs into concise factual statements. Example: Instead of {"temp": 72, "unit": "f"}, write "The weather in Dallas is 72°F."
    Output Format: A single paragraph titled "CONVERSATION SUMMARY".
    """
                    ),
                    Message.user(
                        content=json.dumps(
                            [msg.content for msg in to_summarize if msg.content != ""]
                        )
                    ),
                ],
            )

            if response is None or response.exception:
                logger.error(response.content, exc_info=True)
                traceback.print_exc()
                response.content = "\n".join(
                    [msg.content for msg in to_summarize[-3:] if msg.content != ""]
                )

            first_message = (
                self.state.messages[0]
                if self.state.messages[0].role == "system"
                else None
            )
            self.state.messages = [
                Message.system(
                    content=f"{first_message.content + '\n\n' if first_message else ''}{response.content}",
                ),
                *keep_recent,
            ]

            total_tokens = self.state.total_token_count
