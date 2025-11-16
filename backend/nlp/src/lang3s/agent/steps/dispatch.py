from typing import List, Callable, Optional

from lang3s.agent.shared_types import StepResult, AgentStep
from lang3s.agent.steps.generation import AnalysisStep, ExampleGenerationStep, PerspectiveStep, \
    SummarizationStep
from .extraction import CategorizationStep
from .planning import Plan
from .retrieval import RetrievalStep, RetrievalResult
from .tools import ToolStep


class PlanRouterStep(AgentStep):
    """
    Dispatches execution to one of several sub-steps depending on the LLM plan.

    Expected behavior:
    - Looks at the last assistant message (PlanStep output)
    - Parses it into a Plan model
    - Runs the matching step
    - Returns that step's result
    - If action="stop", terminates the loop
    """

    def __init__(
        self,
        retriever: Callable[[str], List[RetrievalResult]],
        history: int = 0
    ):
        self.tool_step = ToolStep()
        self.retrieval_step = RetrievalStep(retriever)
        self.summarization_step = SummarizationStep(history=history)
        self.reflect_step = PerspectiveStep(history=history)
        self.analyze_step = AnalysisStep(history=history)
        self.example_generator_step = ExampleGenerationStep()
        self.categorization_step = CategorizationStep()

    # ---------------------------------------------------------------------
    # Helper: extract the latest Plan from state
    # ---------------------------------------------------------------------
    def _get_plan_from_state(self, state: List[dict]) -> Plan:
        # Find last assistant message with content
        messages = [m for m in state if m["role"] == "assistant"]
        if not messages:
            raise RuntimeError("PlanRouterStep cannot find any assistant message to parse.")

        raw = messages[-1]["content"]

        try:
            plan = Plan.model_validate_json(raw)
        except Exception as e:
            return Plan(
                action="stop",
                reasoning="LLM produced invalid plan; defaulting to summarize.",
                tool=None
            )

        return plan

    # ---------------------------------------------------------------------
    # SYNC RUN
    # ---------------------------------------------------------------------
    def run(self, agent, state: List[dict], user_message: str) -> StepResult:
        plan = self._get_plan_from_state(state)
        agent.state_cache["last_plan"] = plan
        
        if plan.action == "stop":
            return StepResult(messages=state, output="Stopped", terminated=True)

        if plan.action == "use_tool":
            return self.tool_step.run(agent, state, user_message)

        if plan.action == "retrieve":
            return self.retrieval_step.run(agent, state, user_message)

        if plan.action == "summarize":
            return self.summarization_step.run(agent, state, user_message)

        if plan.action == "reflect":
            return self.reflect_step.run(agent, state, user_message)

        if plan.action == "analyze":
            return self.analyze_step.run(agent, state, user_message)

        if plan.action == "generate_examples":
            return self.example_generator_step.run(agent, state, user_message)

        if plan.action == "categorize":
            return self.categorization_step.run(agent, state, user_message)

        raise ValueError(f"Unknown plan action: {plan.action}")

    # ---------------------------------------------------------------------
    # ASYNC RUN
    # ---------------------------------------------------------------------
    async def async_run(self, agent, state: List[dict], user_message: str) -> StepResult:
        plan = self._get_plan_from_state(state)

        if plan.action == "stop":
            return StepResult(messages=state, output="Stopped", terminated=True)

        if plan.action == "use_tool":
            if hasattr(self.tool_step, "async_run"):
                return await self.tool_step.async_run(agent, state, user_message)
            return self.tool_step.run(agent, state, user_message)

        if plan.action == "retrieve":
            if hasattr(self.retrieval_step, "async_run"):
                return await self.retrieval_step.async_run(agent, state, user_message)
            return self.retrieval_step.run(agent, state, user_message)

        if plan.action == "summarize":
            if hasattr(self.summarization_step, "async_run"):
                return await self.summarization_step.async_run(agent, state, user_message)
            return self.summarization_step.run(agent, state, user_message)

        if plan.action == "reflect":
            if hasattr(self.reflect_step, "async_run"):
                return await self.reflect_step.async_run(agent, state, user_message)
            return self.reflect_step.run(agent, state, user_message)

        if plan.action == "analyze":
            if hasattr(self.reflect_step, "async_run"):
                return await self.analyze_step.async_run(agent, state, user_message)
            return self.analyze_step.run(agent, state, user_message)

        raise ValueError(f"Unknown plan action: {plan.action}")


class ConditionalStep(AgentStep):
    """
    Choose between then_step or else_step based on a predicate applied to `state`.
    """

    def __init__(
        self,
        condition: Callable[[List[dict]], bool],
        then_step: AgentStep,
        else_step: Optional[AgentStep] = None
    ):
        self.condition = condition
        self.then_step = then_step
        self.else_step = else_step

    def run(self, agent, state, user_message):
        step = self.then_step if self.condition(state) else self.else_step
        if step is None:
            return StepResult(messages=state, output=None)
        return step.run(agent, state, user_message)

    async def async_run(self, agent, state, user_message):
        step = self.then_step if self.condition(state) else self.else_step
        if step is None:
            return StepResult(messages=state, output=None)
        return await step.async_run(agent, state, user_message)
