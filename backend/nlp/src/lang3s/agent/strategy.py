import traceback
from textwrap import dedent
from typing import TYPE_CHECKING, Callable, Counter, Dict, List, Optional, Tuple

from pydantic import BaseModel

from lang3s.agent.llm import ChatModelResponse
from lang3s.agent.llm.tools import LLMTool, ToolCall
from lang3s.agent.middleware import Middleware
from lang3s.agent.shared_types import AgentResult, AgentState
from lang3s.nlp.core_nlp import CoreLanguageProcessor
from lang3s.pipeline.langdetect import detect_language

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

    async def async_run(self, agent: "Agent", state: AgentState) -> AgentResult:
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

    def run(self, agent: "Agent", state: AgentState) -> AgentResult:
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

    async def _async_run_tools(
        self,
        agent: "Agent",
        state: "AgentState",
        progress: AgentResult,
        response: ChatModelResponse,
        priority: Optional[int] = None,
        include_no_results: bool = True,
    ) -> bool:
        state.max_progress += len(response.tool_calls or [])
        for tool_call in response.tool_calls or []:
            if self._run_middleware(
                "before_tool_call",
                agent=agent,
                state=state,
                tool=tool_call,
                progress=progress,
            ):
                return True

            tool_response = await tool_call.async_invoke()
            if not tool_response["is_empty"] or include_no_results:
                if priority is not None:
                    tool_response["_priority"] = priority
                state.update(tool_response)
            state.progress += 1

            if self._run_middleware(
                "after_tool_call",
                agent=agent,
                state=state,
                tool=tool_call,
                tool_result=tool_response,
                progress=progress,
            ):
                return True

        return False

    def _run_middleware(self, func: str, **kwargs) -> bool:
        for middleware in self._middleware:
            method = getattr(middleware, func, None)
            if method is None:
                raise AttributeError(f"{middleware} has no method '{func}'")
            method(**kwargs)
        return kwargs["state"].terminated

    async def _async_chat(
        self,
        agent: "Agent",
        state: AgentState,
        progress: AgentResult,
        force_tool_call: bool = False,
        use_tools: bool = False,
        ignore_content: Optional[Callable[[str], bool]] = None,
    ) -> Tuple[bool, Optional[ChatModelResponse]]:
        if self._run_middleware(
            "before_model", agent=agent, state=state, progress=progress
        ):
            return True, None

        result = await agent.model.async_chat(
            messages=state.messages,
            tools=state.tools if use_tools else None,
            response_model=state.output_format if not use_tools else None,
            max_tokens=state.max_output_tokens,
            force_tool_call=force_tool_call,
            temperature=state.temperature,
        )
        if result.content:
            state.update({"role": "assistant", "content": result.content})
        state.progress += 1

        if self._run_middleware(
            "after_model", agent=agent, state=state, result=result, progress=progress
        ):
            return True, None

        if result.tool_calls:
            progress.update(chat_model_response=result, messages=state.messages)
        if result.content and (
            not ignore_content or not ignore_content(result.content.strip())
        ):
            progress.update(chat_model_response=result, messages=state.messages)

        if self._run_middleware(
            "on_progress_update", agent=agent, state=state, progress=progress
        ):
            return True, None

        return False, result

    def _chat(
        self,
        agent: "Agent",
        state: AgentState,
        progress: AgentResult,
        force_tool_call: bool = False,
        use_tools: bool = False,
        ignore_content: Optional[Callable[[str], bool]] = None,
    ) -> Tuple[bool, Optional[ChatModelResponse]]:
        if self._run_middleware(
            "before_model", agent=agent, state=state, progress=progress
        ):
            return True, None

        result = agent.model.chat(
            messages=state.messages,
            tools=state.tools if use_tools else None,
            response_model=state.output_format if not use_tools else None,
            max_tokens=state.max_output_tokens,
            force_tool_call=force_tool_call,
            temperature=state.temperature,
        )

        if result.content:
            state.update({"role": "assistant", "content": result.content})
        state.progress += 1

        if self._run_middleware(
            "after_model", agent=agent, state=state, result=result, progress=progress
        ):
            return True, None

        if result.tool_calls:
            progress.update(chat_model_response=result, messages=state.messages)
        if result.content and (
            not ignore_content or not ignore_content(result.content.strip())
        ):
            progress.update(chat_model_response=result, messages=state.messages)

        if self._run_middleware(
            "on_progress_update", agent=agent, state=state, progress=progress
        ):
            return True, None

        return False, result

    @staticmethod
    def _add_task_prompt(agent: "Agent", state: AgentState, task: str):
        if state.persona and state.persona_mode:
            state.update(
                {
                    "role": "user",
                    "content": state.persona.build_prompt(
                        mode=state.persona_mode, task=task
                    ),
                }
            )
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

    def __init__(
        self,
        custom_prompt: Optional[str] = None,
        no_tool_call_response: Optional[str] = None,
    ):
        super().__init__()
        self.custom_prompt: str = custom_prompt or DEFAULT_PLANNING_PROMPT
        self.no_tool_call_response: str = no_tool_call_response or "NO TOOL CALL NEEDED"

    async def async_run(self, agent: "Agent", state: AgentState) -> AgentResult:
        try:
            state.max_progress += 2

            result = AgentResult()
            planning_prompt = self.custom_prompt.format(task=state.task).strip()
            state.update(
                {"role": "user", "content": planning_prompt, "is_plan": True},
            )

            is_terminated, response = await self._async_chat(
                agent, state, use_tools=True, progress=result
            )
            if is_terminated or not response:
                return result

            if response.tool_calls:
                if await self._async_run_tools(
                    agent=agent, state=state, progress=result, response=response
                ):
                    return result

                if state.persona and state.persona_mode:
                    state.update(
                        {
                            "role": "user",
                            "content": state.persona.build_prompt(
                                mode=state.persona_mode, task=state.task
                            ),
                        }
                    )
                else:
                    state.update(
                        {
                            "role": "user",
                            "content": f"With the given results, now please answer {state.task}",
                        }
                    )

                state.remove_messages_if(lambda msg: msg.get("is_plan", False))
                await self._async_chat(agent, state, use_tools=False, progress=result)
                return result

            elif response.content is not None and response.content.startswith(
                self.no_tool_call_response
            ):
                state.remove_messages_if(lambda msg: msg.get("is_plan", False))
                Strategy._add_task_prompt(agent, state, task=state.task)
                await self._async_chat(agent, state, use_tools=False, progress=result)
                return result

            else:
                state.progress += 1
                return result

        except Exception as e:
            traceback.print_exc()
            return AgentResult(success=False, exception=e)


class OneShotStrategy(Strategy):
    """DefaultStrategy

    The DefaultStrategy class implements a simple strategy for executing an agent's task.
    This strategy is intended for scenarios where a straightforward agent run is
    sufficient, without advanced error handling or retry logic.
    """

    async def async_run(self, agent: "Agent", state: AgentState) -> AgentResult:
        try:
            result = AgentResult()
            state.max_progress += 1
            Strategy._add_task_prompt(agent, state, task=state.task)
            await self._async_chat(agent, state, use_tools=False, progress=result)
            return result
        except Exception as e:
            return AgentResult(success=False, exception=e)


class IterativeStrategy(Strategy):
    """
    Iteratively calls a realtime-strategy or a per-iteration LLM step.
    Useful for generating many items when you can only emit one per call.
    """

    def __init__(
        self,
        iterations: int,
        iteration_task: str = "",
        substrategy: Optional[Strategy] = None,
    ):
        super().__init__()
        self.iterations: int = iterations
        self.substrategy: Optional[Strategy] = substrategy
        self.iteration_task_supplement: str = iteration_task

    def set_middleware(self, middleware: List[Middleware]):
        super().set_middleware(middleware)
        if self.substrategy is not None:
            self.substrategy.set_middleware(middleware)

    async def async_run(self, agent: "Agent", state: AgentState) -> AgentResult:
        try:
            results: AgentResult = AgentResult()
            state.max_progress += self.iterations

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
                    iteration_task_parts.extend(
                        ["Iteration Task:", self.iteration_task_supplement, ""]
                    )

                if len(results.content) > 0:
                    iteration_task_parts.extend(
                        ["Previous Output:", "\n".join(results.content), ""]
                    )

                iteration_task = "\n".join(iteration_task_parts).strip()

                if self.substrategy is not None:
                    old_task = state.task
                    state.task = iteration_task
                    result = await self.substrategy.async_run(agent, state)
                    state.task = old_task
                    results.merge(result)
                    if state.terminated:
                        return results
                    if self._run_middleware(
                        "on_progress_update", agent=agent, state=state, progress=results
                    ):
                        return results

                else:
                    state.remove_messages_if(lambda msg: msg.get("is_plan", False))
                    self._add_task_prompt(agent, state, task=iteration_task)
                    is_terminated, response = await self._async_chat(
                        agent, state, use_tools=False, progress=results
                    )
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

    async def async_run(self, agent: "Agent", state: AgentState) -> AgentResult:
        try:
            results: AgentResult = AgentResult()
            state.max_progress += len(self.steps)
            for step in self.steps:
                step_task = [
                    "Overall User Task:",
                    state.task,
                    "",
                ]

                if isinstance(step, str):
                    step_task.extend(["Current Task:", step])
                    state.remove_messages_if(lambda msg: msg.get("is_plan", False))
                    self._add_task_prompt(
                        agent, state, task="\n".join(step_task).strip()
                    )
                    is_terminated, response = await self._async_chat(
                        agent, state, use_tools=False, progress=results
                    )
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
                    if self._run_middleware(
                        "on_progress_update", agent=agent, state=state, progress=results
                    ):
                        return results

                state.truncate(agent.token_estimator)

            return results
        except Exception as e:
            return AgentResult(success=False, exception=e)


class ReACTStrategy(Strategy):
    def __init__(self, max_steps: int):
        super().__init__()
        self.max_steps = max_steps

    async def async_run(self, agent: "Agent", state: AgentState) -> AgentResult:
        react_step_prompt = """
        User Task:
        {task}
        
        Current Step: {step} or {max_steps}
        You must provide a Final Answer by step {max_steps}.
        
        Respond with either:
            1. Thought: reason about what to do next
            2. Provide tool_call for one or more tools to that will aid you answering the question.
            3. Final Answer: <text>
        
        After receiving an Observation, continue thinking.
        When you have the final answer, output:
        
        Final Answer: <text>
        
        Never hallucinate tools.
        """

        react_final_prompt = """
        User Task:
        {task}
        
        You are out of steps to perform.
        Please answer to the best of your ability with the information you have gathered in the following format:
        
        Final Answer: <text>
        """
        results = AgentResult()
        state.max_progress += self.max_steps
        for step in range(self.max_steps):
            if step < self.max_steps - 1:
                step_prompt = dedent(
                    react_step_prompt.format(
                        task=state.task, step=step + 1, max_steps=self.max_steps + 1
                    ).strip()
                )
            else:
                step_prompt = dedent(react_final_prompt.format(task=state.task).strip())

            state.update({"role": "user", "content": step_prompt})
            is_terminated, response = await self._async_chat(
                agent,
                state,
                use_tools=step < self.max_steps - 1,
                progress=results,
                ignore_content=lambda x: x.startswith("Thought:")
                or x.startswith("1. Thought:")
                or x.startswith("1.Thought:"),
            )
            if is_terminated or response is None:
                return results

            if response.tool_calls:
                if await self._async_run_tools(
                    agent=agent, state=state, progress=results, response=response
                ):
                    return results
                continue

            elif response.content and response.content.strip().startswith(
                "Final Answer:"
            ):
                if state.output_format:
                    state.max_progress += 1
                    last_content = results.content[-1].strip()
                    results.content = results.content[:-1]
                    state.task = "Now convert the output into the given schema."
                    self._add_task_prompt(
                        agent,
                        state,
                        task=f"Now convert the output into the given schema.\nOUTPUT:\n{last_content}",
                    )
                    await self._async_chat(
                        agent, state, use_tools=False, progress=results
                    )
                elif state.persona and state.persona_mode:
                    state.max_progress += 1
                    last_content = results.content[-1].strip()
                    results.content = results.content[:-1]
                    self._add_task_prompt(
                        agent,
                        state,
                        task=f"Rewrite the given content using the tone of the persona and omit the 'Final Answer:' text.\nCONTENT:\n{last_content}",
                    )
                    await self._async_chat(
                        agent, state, use_tools=False, progress=results
                    )

                return results

            state.truncate(agent.token_estimator)

        results.content.append("Max Steps encountered without a final answer.")
        return results


CRITIQUE_PROMPT: str = (
    "Critique the previous answer. Identify all mistakes, omissions, "
    "logical errors, and unclear reasoning. Be very explicit. "
    "If there are no issues with the text answer: NO ISSUES"
)
REVISION_PROMPT: str = (
    "Rewrite the answer using the critique. Provide a corrected, improved, "
    "and more accurate answer."
)


class ReflectionStrategy(Strategy):
    def __init__(self, max_reflections: int):
        super().__init__()
        self.max_reflections = max_reflections

    async def async_run(self, agent: "Agent", state: AgentState) -> AgentResult:
        try:
            results = AgentResult()

            self._add_task_prompt(agent, state, task=state.task)
            last_messages = state.messages
            is_terminated, last_response = await self._async_chat(
                agent=agent,
                state=state,
                progress=results,
                use_tools=False,
                ignore_content=lambda x: True,
            )
            if is_terminated or last_response is None:
                return results

            state.max_progress += self.max_reflections * 2
            for i in range(self.max_reflections):
                self._add_task_prompt(agent, state, task=CRITIQUE_PROMPT)
                is_terminated, response = await self._async_chat(
                    agent=agent,
                    state=state,
                    progress=results,
                    use_tools=False,
                    ignore_content=lambda x: True,
                )
                if is_terminated or not response:
                    return results

                if response.content and "NO ISSUES" in response.content:
                    break

                self._add_task_prompt(agent, state, task=REVISION_PROMPT)
                last_messages = state.messages
                is_terminated, last_response = await self._async_chat(
                    agent=agent,
                    state=state,
                    progress=results,
                    use_tools=False,
                    ignore_content=lambda x: True,
                )
                if is_terminated or not last_response:
                    return results

            results.update(chat_model_response=last_response, messages=last_messages)

            if state.output_format:
                state.max_progress += 1
                last_content = results.content[-1].strip()
                results.content = results.content[:-1]
                state.task = "Now convert the output into the given schema."
                self._add_task_prompt(
                    agent,
                    state,
                    task=f"Now convert the output into the given schema.\nOUTPUT:\n{last_content}",
                )
                await self._async_chat(agent, state, use_tools=False, progress=results)

            return results
        except Exception as e:
            return AgentResult(success=False, exception=e)


class QueryFormat(BaseModel):
    queries: List[str]


class SearchStrategy(Strategy):
    def __init__(self, search_tool_names: List[str]):
        super().__init__()
        self.search_tool_names = set(search_tool_names)

    async def async_run(self, agent: "Agent", state: AgentState) -> AgentResult:
        if not state.tools:
            return AgentResult(success=False, exception=Exception("No tools found."))

        persona_mode = state.persona_mode
        state.persona_mode = None
        tool_definitions: Dict[str, LLMTool] = dict()
        for func in state.tools:
            if not isinstance(func, Callable) or not hasattr(func, "tool"):
                return AgentResult(
                    success=False,
                    exception=Exception(f"Tool {func.__name__} is not valid."),
                )
            elif func.tool.name in self.search_tool_names:  # type:ignore
                tool_definitions[func.tool.name] = func.tool  # type: ignore

        try:
            results = AgentResult()
            state.max_progress = 2

            search_task = f"""
            User task: {state.task}
            
            Identify the best search queries.
            """

            self._add_task_prompt(agent, state, task=search_task)
            output_format = state.output_format
            state.output_format = QueryFormat
            is_terminated, response = await self._async_chat(
                agent=agent,
                state=state,
                progress=results,
                ignore_content=lambda x: True,
            )
            state.output_format = output_format
            if is_terminated or not response or not response.parsed:
                return results

            tool_calls: List[ToolCall] = []
            tool_id = 0
            for tool in tool_definitions.values():
                for query in response.parsed.queries:
                    tool_calls.append(
                        ToolCall(
                            is_async=tool.is_async,
                            arguments={"query": query},
                            name=tool.name,
                            arguments_type=tool.arg_validator,
                            tool_call_id=str(tool_id),
                            function=tool.function,
                        )
                    )
                    tool_id += 1
            state.messages = state.messages[:-1]
            dummy_message = ChatModelResponse(
                tool_calls=tool_calls, parsed=None, content=None, audio=None
            )
            await self._async_run_tools(
                agent=agent, state=state, progress=results, response=dummy_message
            )

            summarize_task = f"""
            User task: {state.task}

            Summarize the search results in the tool calls.
            """
            state.persona_mode = persona_mode
            self._add_task_prompt(agent, state, task=summarize_task)
            await self._async_chat(agent=agent, state=state, progress=results)

            return results
        except Exception as e:
            return AgentResult(success=False, exception=e)
        finally:
            state.persona_mode = persona_mode

    def extract_queries(self, text: str):
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        return lines


class DiscoveryStrategy(Strategy):
    def __init__(
        self,
        search_tool: str,
        allow_random_search: bool = True,
        rounds: int = 5,
        queries_per_round: int = 5,
    ):
        super().__init__()
        self.search_tool = search_tool
        self.rounds = rounds
        self.queries_per_round = queries_per_round
        self.allow_random_search = allow_random_search

    async def async_run(self, agent: "Agent", state: AgentState) -> AgentResult:
        if not state.tools:
            return AgentResult(success=False, exception=Exception("No tools found."))

        persona_mode = state.persona_mode
        state.persona_mode = None
        tool_definitions: LLMTool = None  # type: ignore

        for func in state.tools:
            if not isinstance(func, Callable) or not hasattr(func, "tool"):
                return AgentResult(
                    success=False,
                    exception=Exception(f"Tool {func.__name__} is not valid."),
                )
            elif func.tool.name == self.search_tool:  # type:ignore
                tool_definitions = func.tool  # type: ignore
                break

        if tool_definitions is None:
            return AgentResult(
                success=False,
                exception=Exception(f"Tool {self.search_tool} not found."),
            )

        discovered_terms = Counter()
        tool_id = 0
        try:
            results = AgentResult()
            state.update(
                {
                    "role": "user",
                    "content": (
                        f"You must explore the corpus using only the search tool. "
                        f"No prior knowledge is available. Begin generating probe queries."
                    ),
                }
            )
            state.max_progress += self.rounds * 3 + 1

            for round_idx in range(self.rounds):
                terms = [k[0] for k in discovered_terms.most_common(150) if k[1] > 1]
                random_search = ""
                if self.allow_random_search and round_idx == 0:
                    random_search = "If no clues exist, you MUST generate '*' as one of your new search queries to retrieve random sentences for the corpus. "
                probe_prompt = (
                    f"User Task:\n{state.task.strip()}\n"
                    f"You are exploring an unknown corpus.\n"
                    f"Based on all previous discoveries, generate {self.queries_per_round} "
                    f"new search queries that are **diverse** and **exploratory**.\n"
                    f"If no clues exist, start with extremely broad probes such as: "
                    f"'a', 'the', 'data', 'report', 'sports', 'economy', 'business', 'computers', 'life', 'entertainment', etc. "
                    f"{random_search}"
                    f"Be sure to ONLY GENERATE {self.queries_per_round} new search queries."
                    f"\n\nDiscovered so far: {sorted(terms)}"
                )
                self._add_task_prompt(agent, state, task=probe_prompt)
                output_format = state.output_format
                state.output_format = QueryFormat
                is_terminated, response = await self._async_chat(
                    agent=agent,
                    state=state,
                    progress=results,
                    ignore_content=lambda x: True,
                )
                state.output_format = output_format
                if is_terminated or not response or not response.parsed:
                    return results

                discovered_terms.update(
                    response.parsed.queries[: self.queries_per_round]
                )
                state.messages.pop(-1)

                tool_calls: List[ToolCall] = []

                for query in response.parsed.queries[: self.queries_per_round]:
                    tool_calls.append(
                        ToolCall(
                            is_async=tool_definitions.is_async,
                            arguments={"query": query},
                            name=tool_definitions.name,
                            arguments_type=tool_definitions.arg_validator,
                            tool_call_id=str(tool_id),
                            function=tool_definitions.function,
                        )
                    )
                    tool_id += 1
                dummy_message = ChatModelResponse(
                    tool_calls=tool_calls, parsed=None, content=None, audio=None
                )
                if await self._async_run_tools(
                    agent=agent,
                    state=state,
                    progress=results,
                    response=dummy_message,
                    include_no_results=False,
                ):
                    return results

                summary_prompt = (
                    f"Based on the new results, summarize what we learned about the corpus.\n"
                    f"Identify new topics, entity types, recurring formats, or other patterns.\n\n"
                    f"Be specific and list clearly observable characteristics."
                )
                self._add_task_prompt(agent, state, task=summary_prompt)
                temperature = state.temperature
                state.temperature = 0.3
                is_terminated, response = await self._async_chat(
                    agent=agent,
                    state=state,
                    progress=results,
                    ignore_content=lambda x: True,
                )
                state.temperature = temperature
                if is_terminated or not response:
                    return results

                discovered_terms.update(self.extract_terms(response.content or ""))

                # Remove all tool calls to save input tokens
                state.remove_messages_if(lambda m: m["role"] == "tool")

                state.truncate(agent.token_estimator)
                state.progress += 1

            final_prompt = (
                f"Using all exploration rounds, produce a final characterization of the corpus.\n"
                f"Include:\n"
                f"- Main topics\n"
                f"- Subtopics\n"
                f"- Notable entities\n"
                f"- File/document types\n"
                f"- Styles or patterns\n"
                f"- Any ontology or taxonomy that emerges\n"
                f"- Known gaps or unknowns\n"
            )
            state.persona_mode = persona_mode
            self._add_task_prompt(agent, state, task=final_prompt)
            await self._async_chat(agent=agent, state=state, progress=results)

            return results
        except Exception as e:
            return AgentResult(success=False, exception=e)
        finally:
            state.persona_mode = persona_mode

    def extract_terms(self, doc: str):
        language = detect_language(doc)
        nlp = CoreLanguageProcessor().get_pipeline(language)
        sdoc = nlp(doc)
        keywords = []
        import re

        try:
            for chunk in sdoc.noun_chunks:
                t = ""
                for token in chunk:
                    if not token.is_stop:
                        t += token.lemma_ + " "
                t = t.strip()
                if len(t) > 3 and re.match(r"^[A-Za-z ]+$", t):
                    keywords.append(t.lower())
        except Exception:
            for token in sdoc:
                if not token.is_stop:
                    t = token.lemma_.lower()
                    if len(t) > 3 and re.match(r"^[A-Za-z]+$", t):
                        keywords.append(t)
        return keywords
