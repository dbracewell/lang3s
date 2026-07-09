from __future__ import annotations

from typing import TYPE_CHECKING, Type, TypeVar

from pydantic import BaseModel

from lang3s.agent.events import AgentEvent, AgentEventType

from .strategy import Strategy, StrategyResult

if TYPE_CHECKING:
    from ..session import Session

DEFAULT_PLANNING_PROMPT = """USER QUESTION: {task}
Respond with either:
1. Provide a tool_call to that will aid you answering the question.
or
2. "NO TOOL CALL NEEDED" if no tool call is needed to answer the question."""

T = TypeVar("T", bound=BaseModel)


class ToolCallingStrategy(Strategy[T]):
    """ToolCallingStrategy

    A strategy that guides an agent to determine whether a tool call is necessary
    for a given task and executes the required calls.

    The strategy first formats a prompt asking the language model to either
    invoke a suitable tool or declare that no tool call is needed.
    If a tool call is returned, the strategy invokes it asynchronously,
    updates the agent’s memory with the result, and then performs a final
    model query without tools to produce the answer.  If the response
    indicates “NO TOOL CALL NEEDED”, the strategy skips tool invocation
    and directly obtains an answer from the model.

    The class can be configured with custom prompt text or a different
    string that signals no tool usage.

    Parameters
    ----------
    custom_prompt : Optional[str]
        Prompt template used to ask the language model whether a tool is needed.
        Prompt template should have a placeholder for {task} or {planning} to include
        the default prompt as part of your template
        If None, a default prompt asking for either a tool call or “NO TOOL CALL NEEDED”
        is used.
    no_tool_call_response : Optional[str]
        Prefix string that identifies when the model has decided no tool is required.
        Defaults to "NO TOOL CALL NEEDED".

    Returns
    -------
    AgentResult
        An object containing the model’s final response, any messages produced,
        and success status.  If an exception occurs during processing,
        the result will indicate failure and include the exception.

    Raises
    ------
    None

    """

    def __init__(
        self,
        response_model: Type[T] | None = None,
        custom_prompt: str | None = None,
        no_tool_call_response: str | None = None,
    ):
        super().__init__(response_model=response_model)
        self.custom_prompt: str = custom_prompt or DEFAULT_PLANNING_PROMPT
        self.no_tool_call_response: str = no_tool_call_response or "NO TOOL CALL NEEDED"

    async def run(self, session: Session) -> StrategyResult[T]:
        session.state.max_progress += 2

        planning_prompt = self.custom_prompt.format(task=session.state.task).strip()
        session.state.add_user_message(content=planning_prompt, is_plan=True)

        response: AgentEvent[T] | None = None
        tool_calls = []

        async for event in self._async_chat(session, use_tools=True):
            if event.type == AgentEventType.TOOL_CALL_COMPLETE:
                tool_calls.append(event)
            elif event.type == AgentEventType.TEXT_COMPLETE:
                response = event
            elif event.type == AgentEventType.ERROR:
                response = event
        session.state.progress += 1

        if response is None:
            raise Exception("Unknown error")

        if response.exception:
            return StrategyResult.from_agent_event(response)

        if tool_calls:
            await self._async_run_tools(session, tool_calls)
            session.state.add_user_message(
                f"With the given results, now please answer {session.state.task}"
            )
            response = await self._chat_to_completion(session)
            if response is None:
                raise Exception("Unknown error")
            if response.exception:
                return StrategyResult.from_agent_event(response)
            session.state.progress += 1
            return StrategyResult.from_agent_event(response)

        elif response.content and response.content.startswith(
            self.no_tool_call_response
        ):
            session.state.add_user_message(content=session.state.task, use_tools=False)
            response = await self._chat_to_completion(session)
            if response is None:
                raise Exception("Unknown error")
            if response.exception:
                return StrategyResult.from_agent_event(response)
            session.state.progress += 1
            return StrategyResult.from_agent_event(response)

        else:
            raise Exception(
                f"No tool call was found and LLM did not response correctly "
                f"for {session.state.task}"
            )
