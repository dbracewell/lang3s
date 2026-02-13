from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING, Type, TypeVar, Unpack

from pydantic import BaseModel

from lang3s.llm.client import ChatCompletionParams

from .strategy import Strategy, StrategyResult

if TYPE_CHECKING:
    from ..session import Session

T = TypeVar("T", bound=BaseModel)


class OneShotStrategy(Strategy[T]):
    def __init__(
        self,
        prompt: str | None = None,
        response_model: Type[T] | None = None,
        **kwargs: Unpack[ChatCompletionParams],
    ) -> None:
        super().__init__(response_model=response_model)
        self._prompt = prompt
        self._kwargs: Unpack[ChatCompletionParams] = kwargs

    async def run(self, session: Session) -> StrategyResult[T]:
        effective_prompt = session.state.task
        if self._prompt:
            effective_prompt = textwrap.dedent(f"""
            Overall User Task:\n
            {session.state.task}
            
            Current Task:\n
            {effective_prompt}
            """).strip()
        session.state.add_user_message(effective_prompt)
        session.state.max_progress += 1
        session.response_model = self._response_model
        response = await self._chat_to_completion(session, **self._kwargs)
        session.state.progress += 1
        return StrategyResult.from_agent_event(response)
