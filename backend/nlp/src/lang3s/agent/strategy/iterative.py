from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Type, Unpack

from lang3s.llm.client import ChatCompletionParams

from .strategy import STRATEGY_RESPONSE_TYPE, Strategy, StrategyResult

if TYPE_CHECKING:
    from ..session import Session

type ResultCombiner[STRATEGY_RESPONSE_TYPE] = Callable[
    [STRATEGY_RESPONSE_TYPE, STRATEGY_RESPONSE_TYPE],
    StrategyResult[STRATEGY_RESPONSE_TYPE],
]


class IterativeStrategy(Strategy[STRATEGY_RESPONSE_TYPE]):
    """
    Iteratively calls a realtime-strategy or a per-iteration LLM step.
    Useful for generating many items when you can only emit one per call.
    """

    def __init__(
        self,
        iterations: int,
        iteration_task: str = "",
        substrategy: Strategy[STRATEGY_RESPONSE_TYPE] | None = None,
        response_model: Type[STRATEGY_RESPONSE_TYPE] | None = None,
        **kwargs: Unpack[ChatCompletionParams],
    ):
        super().__init__(response_model=response_model)
        self.iterations: int = iterations
        self.substrategy: Strategy[STRATEGY_RESPONSE_TYPE] | None = substrategy
        self.iteration_task_supplement: str = iteration_task
        self._kwargs: Unpack[ChatCompletionParams] = kwargs

    async def run(self, session: Session) -> StrategyResult[STRATEGY_RESPONSE_TYPE]:
        try:
            session.state.max_progress += self.iterations
            result_contents: list[str] = []
            result_parsed: list[STRATEGY_RESPONSE_TYPE] = []

            for i in range(self.iterations):
                iteration_task_parts = [
                    "Overall User Task:",
                    session.state.task,
                    "",
                    "Current Iteration:",
                    f"You are on iteration {i + 1} of {self.iterations}. ",
                    "",
                ]

                if self.iteration_task_supplement:
                    iteration_task_parts.extend(
                        ["Iteration Task:", self.iteration_task_supplement, ""]
                    )

                if result_contents:
                    iteration_task_parts.extend(
                        ["Previous Output:", "\n".join(result_contents), ""]
                    )

                iteration_task = "\n".join(iteration_task_parts).strip()

                if self.substrategy is not None:
                    old_task = session.state.task
                    session.state.task = iteration_task

                    new_result = await self.substrategy.run(session)
                    if new_result.exception:
                        return new_result

                    session.state.task = old_task

                    if new_result.content:
                        result_contents.extend(new_result.content)
                    if new_result.parsed:
                        result_parsed.extend(new_result.parsed)

                else:
                    # session.state.remove_messages_if(lambda msg: msg.get("is_plan", False))
                    session.state.add_user_message(iteration_task)
                    event = await self._chat_to_completion(session, **self._kwargs)
                    if event.exception:
                        return StrategyResult.from_agent_event(event)
                    if event.content:
                        result_contents.append(event.content)
                    if event.parsed:
                        result_parsed.append(event.parsed)

                session.compact()

            return StrategyResult(content=result_contents, parsed=result_parsed)
        except Exception as e:
            return StrategyResult.from_exception(e)
