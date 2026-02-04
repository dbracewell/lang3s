from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Type

import shortuuid
from pydantic import BaseModel

from lang3s import config
from lang3s.agent.token_estimator import estimate_tokens


@dataclass
class State:
    task: str = field(default="")
    messages: list[dict[str, Any]] = field(default_factory=list)
    progress: int = field(default=0)
    max_progress: int = field(default=0)
    cache: dict[str, Any] = field(default_factory=dict)
    terminated: bool = field(default=False)


_DEFAULT_SYSTEM_MESSAGE = "You are a helpful agent."


@dataclass
class Session:
    session_id: str = field(default_factory=lambda: shortuuid.uuid())
    model_name: str = field(default=config.LLM_MODEL)
    system_message: str = field(default=_DEFAULT_SYSTEM_MESSAGE)
    max_tokens: int = field(default=5000)
    max_history: int = field(default=50)
    available_tools: list[Callable[..., Any]] | None = field(default=None)
    response_model: Type[BaseModel] | None = field(default=None)
    _state: State | None = field(default=None, init=False)

    @classmethod
    def load(
        cls,
        data: dict[str, Any],
        available_tools: list[Callable[..., Any]] | None = None,
        response_model: Type[BaseModel] | None = None,
    ) -> Session:
        state = data.pop("_state", None)
        new_session = cls(
            **data, available_tools=available_tools, response_model=response_model
        )
        new_session._state = state
        return new_session

    @property
    def state(self) -> State:
        if self._state is None:
            self._state = State(
                messages=[{"role": "system", "content": self.system_message}],
            )
        return self._state

    def save(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data.pop("_state", {})
        data.pop("response_model", [])
        data.pop("available_tools", None)
        if self._state is not None:
            data["_state"] = self._state.__dict__
        return data

    def update(self, message: dict[str, Any]) -> None:
        self.state.messages.append(message)
        self._compact()

    def reset_state(self) -> None:
        self._state = None

    def _compact(self) -> None:
        state = self.state
        total_tokens = estimate_tokens(self.model_name, state.messages)
        if total_tokens > self.max_tokens or len(state.messages) > self.max_history:
            pass
