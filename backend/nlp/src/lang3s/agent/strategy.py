from typing import Optional, TYPE_CHECKING, List, Tuple

from lang3s.agent.llm import ChatModelResponse
from lang3s.agent.middleware import Middleware
from lang3s.agent.shared_types import AgentResult, AgentState

if TYPE_CHECKING:
    from .agent import Agent

from lang3s.utils.async_helper import run_sync


class Strategy:
    """A strategy for executing tasks with an Agent.

    This abstract base class defines the interface that concrete strategies must
    implement to run a task using an Agent instance.  The primary goal is to
    provide both asynchronous and synchronous entry points, as well as helper
    methods that interact directly with the underlying language model.  A
    strategy may perform preprocessing of the task prompt, configure tool
    usage, or otherwise influence how the Agent communicates with its model.
    """

    def __init__(self):
        self._middleware: List[Middleware] = []

    def set_middleware(self, middleware: List[Middleware]):
        self._middleware = middleware

    async def async_run(self,
                        agent: "Agent",
                        state: AgentState) -> AgentResult:
        """
        Runs the agent asynchronously with a specified task and optional persona mode.

        Parameters
        ----------
        agent : Agent
            The agent to execute the task.
        state: AgentState
            The state of the agent to execute the task.

        Returns
        -------
        AgentResult
            Result of executing the agent task.
        """
        raise NotImplementedError()

    def run(self,
            agent: "Agent",
            state: AgentState) -> AgentResult:
        """
        Runs the agent synchronously with a specified task and optional persona mode.

        Parameters
        ----------
        agent : Agent
            The agent instance to execute the task.
        state: AgentState
            The state of the agent to execute the task.

        Returns
        -------
        AgentResult
            The result object produced by executing the task synchronously.
        """
        return run_sync(self.async_run(agent=agent, state=state))

    def _run_middleware(self, func: str, **kwargs) -> bool:
        for middleware in self._middleware:
            method = getattr(middleware, func, None)
            if method is None:
                raise AttributeError(f"{middleware} has no method '{func}'")
            method(**kwargs)
        return kwargs["state"].terminated

    async def _async_chat(self,
                          agent: "Agent",
                          state: AgentState,
                          progress: AgentResult,
                          force_tool_call: bool = False,
                          use_tools: bool = False,
                          ) -> Tuple[bool, Optional[ChatModelResponse]]:

        if self._run_middleware("before_model",
                                agent=agent,
                                state=state,
                                progress=progress):
            return True, None

        result = await agent.model.async_chat(messages=state.messages,
                                              tools=state.tools if use_tools else None,
                                              response_model=state.output_format if not use_tools else None,
                                              max_tokens=state.max_output_tokens,
                                              force_tool_call=force_tool_call,
                                              temperature=state.temperature)
        if result.content:
            state.update({"role": "assistant", "content": result.content})

        if self._run_middleware("after_model",
                                agent=agent,
                                state=state,
                                result=result,
                                progress=progress):
            return True, None

        progress.update(chat_model_response=result, messages=state.messages)
        if self._run_middleware("on_progress_update",
                                agent=agent,
                                state=state,
                                progress=progress):
            return True, None

        return False, result

    def chat(self,
             agent: "Agent",
             state: AgentState,
             progress: AgentResult,
             force_tool_call: bool = False,
             use_tools: bool = False,
             ) -> Tuple[bool, Optional[ChatModelResponse]]:

        if self._run_middleware("before_model",
                                agent=agent,
                                state=state,
                                progress=progress):
            return True, None

        result = agent.model.chat(messages=state.messages,
                                  tools=state.tools if use_tools else None,
                                  response_model=state.output_format if not use_tools else None,
                                  max_tokens=state.max_output_tokens,
                                  force_tool_call=force_tool_call,
                                  temperature=state.temperature)

        if result.content:
            state.update({"role": "assistant", "content": result.content})

        if self._run_middleware("after_model",
                                agent=agent,
                                state=state,
                                result=result,
                                progress=progress):
            return True, None

        progress.update(chat_model_response=result, messages=state.messages)
        if self._run_middleware("on_progress_update",
                                agent=agent,
                                state=state,
                                progress=progress):
            return True, None

        return False, result

    @staticmethod
    def _add_task_prompt(agent: "Agent",
                         state: AgentState,
                         task: str):
        if state.persona and state.persona_mode:
            state.update({"role": "user",
                          "content": state.persona.build_prompt(mode=state.persona_mode, task=task)})
        else:
            state.update({"role": "user", "content": task})


DEFAULT_PLANNING_PROMPT = """USER QUESTION: {task}

            Respond with either:
            1. Provide a tool_call to that will aid you answering the question.
            or
            2. "NO TOOL CALL NEEDED" if no tool call is needed to answer the question."""


class PlanningStrategy(Strategy):
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
        If None, a default prompt asking for either a tool call or “NO TOOL CALL NEEDED” is used.
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

    def __init__(self,
                 custom_prompt: Optional[str] = None,
                 no_tool_call_response: Optional[str] = None):
        super().__init__()
        self.custom_prompt: str = custom_prompt or DEFAULT_PLANNING_PROMPT
        self.no_tool_call_response: str = no_tool_call_response or "NO TOOL CALL NEEDED"

    async def async_run(self,
                        agent: "Agent",
                        state: AgentState) -> AgentResult:
        try:
            result = AgentResult()
            planning_prompt = self.custom_prompt.format(planning=DEFAULT_PLANNING_PROMPT).format(
                task=state.task).strip()
            state.update(
                {"role": "user",
                 "content": planning_prompt,
                 "is_plan": True},
            )

            is_terminated, response = await self._async_chat(agent, state, use_tools=True, progress=result)
            if is_terminated or not response:
                return result

            if response.tool_calls:
                for tool_call in response.tool_calls:
                    if self._run_middleware("before_tool_call",
                                            agent=agent,
                                            state=state,
                                            tool=tool_call,
                                            progress=result):
                        return result

                    tool_response = await tool_call.async_invoke()
                    state.update(tool_response)

                    if self._run_middleware("after_tool_call",
                                            agent=agent,
                                            state=state,
                                            tool=tool_call,
                                            tool_result=tool_response,
                                            progress=result):
                        return result

                if state.persona and state.persona_mode:
                    state.update({"role": "user",
                                  "content": state.persona.build_prompt(mode=state.persona_mode,
                                                                        task=state.task)})

                state.remove_messages_if(lambda msg: msg.get("is_plan", False))
                await self._async_chat(agent, state, use_tools=False, progress=result)
                return result

            elif response.content is not None and response.content.startswith(self.no_tool_call_response):

                state.remove_messages_if(lambda msg: msg.get("is_plan", False))
                Strategy._add_task_prompt(agent, state, task=state.task)

                await self._async_chat(agent, state, use_tools=False, progress=result)
                return result

            else:
                return result

        except Exception as e:

            return AgentResult(success=False, exception=e)


class OneShotStrategy(Strategy):
    """DefaultStrategy

    The DefaultStrategy class implements a simple strategy for executing an agent's task.
    This strategy is intended for scenarios where a straightforward agent run is
    sufficient, without advanced error handling or retry logic.
    """

    async def async_run(self,
                        agent: "Agent",
                        state: AgentState) -> AgentResult:
        try:
            result = AgentResult()
            Strategy._add_task_prompt(agent, state, task=state.task)
            await self._async_chat(agent, state, use_tools=False, progress=result)
            return result
        except Exception as e:
            return AgentResult(success=False, exception=e)


class IterativeStrategy(Strategy):
    """
    Iteratively calls a sub-strategy or a per-iteration LLM step.
    Useful for generating many items when you can only emit one per call.
    """

    def __init__(self,
                 iterations: int,
                 iteration_task: str = "",
                 substrategy: Optional[Strategy] = None):
        super().__init__()
        self.iterations: int = iterations
        self.substrategy: Optional[Strategy] = substrategy
        self.iteration_task_supplement: str = iteration_task

    def set_middleware(self, middleware: List[Middleware]):
        super().set_middleware(middleware)
        if self.substrategy is not None:
            self.substrategy.set_middleware(middleware)

    async def async_run(
        self,
        agent: "Agent",
        state: AgentState
    ) -> AgentResult:
        try:
            results: AgentResult = AgentResult()

            for i in range(self.iterations):
                iteration_task_parts = [
                    "Overall User Task:",
                    state.task,
                    "",
                    "Current Iteration:",
                    f"You are on iteration {i + 1} of {self.iterations}. ",
                    "",
                ]

                if self.iteration_task_supplement:
                    iteration_task_parts.extend([
                        "Iteration Task:",
                        self.iteration_task_supplement,
                        ""])

                if len(results.content) > 0:
                    iteration_task_parts.extend([
                        "Previous Output:",
                        "\n".join(results.content),
                        ""])

                iteration_task = "\n".join(iteration_task_parts).strip()

                if self.substrategy is not None:
                    old_task = state.task
                    state.task = iteration_task
                    result = await self.substrategy.async_run(agent, state)
                    state.task = old_task
                    results.merge(result)
                    if state.terminated:
                        return results
                    if self._run_middleware("on_progress_update",
                                            agent=agent,
                                            state=state,
                                            progress=results):
                        return results

                else:
                    state.remove_messages_if(lambda msg: msg.get("is_plan", False))
                    self._add_task_prompt(agent, state, task=iteration_task)
                    is_terminated, response = await self._async_chat(agent, state, use_tools=False, progress=results)
                    if is_terminated or not response:
                        return results

                state.truncate(agent.token_estimator)

            return results
        except Exception as e:
            return AgentResult(success=False, exception=e)


class PipelineStrategy(Strategy):

    def __init__(self, steps: List[Strategy | str]):
        super().__init__()
        self.steps: List[Strategy | str] = steps

    def set_middleware(self, middleware: List[Middleware]):
        super().set_middleware(middleware)
        for step in self.steps:
            if isinstance(step, Strategy):
                step.set_middleware(middleware)

    async def async_run(self, agent: "Agent",
                        state: AgentState) -> AgentResult:
        try:
            results: AgentResult = AgentResult()
            for step in self.steps:
                step_task = [
                    "Overall User Task:",
                    state.task,
                    "",
                ]

                if isinstance(step, str):
                    step_task.extend([
                        "Current Task:",
                        step
                    ])
                    state.remove_messages_if(lambda msg: msg.get("is_plan", False))
                    self._add_task_prompt(agent, state, task="\n".join(step_task).strip())
                    is_terminated, response = await self._async_chat(agent, state, use_tools=False, progress=results)
                    if is_terminated or not response:
                        return results

                elif isinstance(step, Strategy):
                    old_task = state.task
                    state.task = "\n".join(step_task).strip()
                    result = await step.async_run(agent, state)
                    state.task = old_task
                    results.merge(result)
                    if state.terminated:
                        return results
                    if self._run_middleware("on_progress_update",
                                            agent=agent,
                                            state=state,
                                            progress=results):
                        return results

                state.truncate(agent.token_estimator)

            return results
        except Exception as e:
            return AgentResult(success=False, exception=e)
