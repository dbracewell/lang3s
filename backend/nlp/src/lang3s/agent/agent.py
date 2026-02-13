from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, overload

from pydantic import BaseModel

from lang3s.utils.async_helper import run_sync

from .events import AgentEvent
from .session import Session
from .strategy.one_shot import OneShotStrategy

if TYPE_CHECKING:
    from .strategy.strategy import (
        STRATEGY_RESPONSE_TYPE,
        Strategy,
        StrategyResult,
    )


class Agent[AGENT_PARSED_TYPE]:
    def __init__(
        self,
        session: Session | None = None,
    ) -> None:
        self._session = session if session is not None else Session()

    @overload
    async def run(
        self, task: str, strategy: None = None
    ) -> StrategyResult[BaseModel]: ...

    @overload
    async def run(
        self, task: str, strategy: Strategy[STRATEGY_RESPONSE_TYPE]
    ) -> StrategyResult[STRATEGY_RESPONSE_TYPE]: ...

    async def run(
        self,
        task: str,
        strategy: Optional[Strategy[Any]] = None,
    ) -> StrategyResult[Any]:
        self._session.state.task = task

        self._session.forward_event(AgentEvent.start_event())
        strategy = strategy if strategy is not None else OneShotStrategy()

        error = None
        try:
            result = await strategy.run(session=self._session)
        except Exception as e:
            error = e
            result = StrategyResult.from_agent_event(AgentEvent.error_event(e))

        self._session.forward_event(
            AgentEvent.end_event(
                total_tokens=self._session.state.total_token_count,
                exception=error,
            )
        )

        return result

    @overload
    def sync_run(
        self, task: str, strategy: None = None
    ) -> StrategyResult[BaseModel]: ...

    @overload
    def sync_run(
        self, task: str, strategy: Strategy[STRATEGY_RESPONSE_TYPE]
    ) -> StrategyResult[STRATEGY_RESPONSE_TYPE]: ...

    def sync_run(
        self,
        task: str,
        strategy: Optional[Strategy[Any]] = None,
    ) -> StrategyResult[Any]:
        result = run_sync(self.run(task=task, strategy=strategy))
        return result

    def reset(self):
        self._session.reset_state()
