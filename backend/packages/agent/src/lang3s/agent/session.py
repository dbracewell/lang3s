from __future__ import annotations

import textwrap
import traceback
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

import shortuuid

from lang3s.core import config
from lang3s.core.logger import get_logger
from lang3s.llm import LLMClient, Message, ToolCall
from lang3s.llm.token_estimator import estimate_tokens

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
            self._state.add_system_message(content=self.system_message)  # type: ignore
            self._state.messages.extend(self.initial_messages)  # type: ignore
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
            middleware(event, self.state)  # type: ignore

    def save(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data.pop("_state", {})
        data.pop("response_model", [])
        data.pop("available_tools", None)
        data.pop("client", None)
        data.pop("middleware", [])
        return data

    def reset_state(self) -> None:
        self._state = State()

    async def compact(self) -> None:
        state = self._state
        if state is None:
            return

        total_tokens = state.total_token_count()
        max_tokens = int(self.context_window * 0.75)

        if total_tokens < max_tokens:
            return

        system_message = self.system_message
        summarize_start = 1 if system_message else 0

        messages = []
        current_tool_ids = set()
        tool_call_content: str = ""
        messages_processed = 0
        for msg in state.messages[summarize_start:]:
            messages_processed += 1
            if msg.role == "tool":
                current_tool_ids.remove(msg.tool_calls[0].tool_call_id)
                tool_call_content += f"{msg.tool_calls[0].name}: {msg.content}\n\n"
            elif msg.tool_calls:
                if current_tool_ids:
                    raise RuntimeError(
                        f"Invalid Compaction State "
                        f"current_tool_ids={current_tool_ids}, "
                        f"trying to add {msg.tool_calls}"
                    )
                if tool_call_content:
                    messages.append(
                        Message.user(
                            f"The following tools have been called:\n"
                            f"{tool_call_content.strip()}"
                        )
                    )
                    tool_call_content = ""
                for tool_call in msg.tool_calls:
                    current_tool_ids.add(tool_call.tool_call_id)
            elif msg.content:
                if current_tool_ids:
                    raise RuntimeError(
                        f"Invalid Compaction State "
                        f"current_tool_ids={current_tool_ids}, "
                        f"trying to add message {msg}"
                    )
                if tool_call_content:
                    messages.append(
                        Message.user(
                            f"The following tools have been called:\n"
                            f"{tool_call_content.strip()}"
                        )
                    )
                    tool_call_content = ""
                messages.append(msg)

        summarize_end = max(summarize_start + 1, len(messages) // 2)

        while summarize_end < len(messages):
            token_count = estimate_tokens(self.model_name, messages[summarize_end:])
            effective_tokens = max_tokens - token_count
            if effective_tokens >= max(500, (0.40 * self.context_window)):
                max_tokens -= token_count
                break
            summarize_end += 1

        if summarize_end >= len(messages):
            to_keep = []
            keep_token_count = 0
        else:
            to_keep = messages[summarize_end:]
            keep_token_count = estimate_tokens(self.model_name, to_keep)

        logger.info(
            f"summarization_end={summarize_end}, "
            f"max_tokens={int(self.context_window * 0.75)}, "
            f"summarzation_tokens={max_tokens}, "
            f"previous_message_tokens={keep_token_count}, "
            f"new_context_size={max_tokens + keep_token_count}"
        )

        to_summarize = []
        for i in range(summarize_start, summarize_end):
            msg = messages[i]
            if not msg.content:
                continue
            if isinstance(msg.content, str):
                to_summarize.append(msg.content)
            else:
                to_summarize.extend(
                    [content.text for content in msg.content if content.type == "text"]
                )

        response = await self.client.chat_last_event(
            max_completion_tokens=max(500, max_tokens),
            messages=[
                Message.system(
                    content=f"""
You are the Memory Management Component of an autonomous agent. 
Your task is to compress the provided conversation history 
into a "Long-Term Memory Block."
You can generate {max(500, max_tokens)} tokens.
Keep ALL key information so that you will be able to use this information later.

### OBJECTIVES
1.  **Current Goal:** State the user's active objective in one sentence.
2.  **Established Facts:** List specific data found (names, IDs, tool outputs, dates). 
    DO NOT generalize; keep the hard data.
3.  **Negative Constraints:** Note what has been tried and failed (e.g., "Economy query 
    returned no relevant data").
4.  **User Preferences:** Any formatting or stylistic requests made by the user.

### OUTPUT FORMAT
[ACTIVE GOAL]: <goal>
[KNOWLEDGE BASE]:
- <fact 1>
- <fact 2>
[DISCARDED PATHS]: <what didn't work>
[PREFERENCES]: <formatting/tone>
"""
                ),
                Message.user(content="\n".join(to_summarize)),
            ],
        )

        if response.exception:
            logger.error(response.exception, exc_info=True)
            traceback.print_exc()
            response.content = "\n".join(
                [msg for msg in to_summarize[-3:] if msg != ""]  # type: ignore
            )

        new_system_message = textwrap.dedent(f"""
{system_message + "\n\n" if system_message else ""}
### LONG-TERM MEMORY
{response.content}
""").strip()

        self.state.messages = [
            Message.system(content=new_system_message),
            *to_keep,
        ]

        logger.info(
            f"Compaction attempt: previous_token_count={total_tokens} "
            f"new_token_count={self.state.total_token_count()}"
        )
