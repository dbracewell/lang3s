from typing import List, Callable, Optional

from lang3s.agent.shared_types import AgentState, Plan, StepResult, AgentStep, RetrievalResult
from lang3s.agent.steps.generation import AnalysisStep, ExampleGenerationStep, PerspectiveStep, \
    SummarizationStep
from .extraction import CategorizationStep
from .retrieval import RetrievalStep
from .tools import ToolStep


class PlanRouterStep(AgentStep):

    def __init__(
        self,
        retriever: Callable[[str], List[RetrievalResult]],
        retrieval_step_name: str = "RetrievalStep",
        summarization_step_name: str = "SummarizationStep",
        reflect_step_name: str = "PerspectiveStep",
        analyze_step_name: str = "AnalyzeStep",
        example_generator_step_name: str = "ExampleGeneratorStep",
        categorization_step_name: str = "CategorizationStep",
        name: str = "PlanRouterStep"
    ):
        AgentStep.__init__(self, name=name)
        self.tool_step = ToolStep()
        self.retrieval_step = RetrievalStep(retriever, name=retrieval_step_name)
        self.summarization_step = SummarizationStep(name=summarization_step_name)
        self.reflect_step = PerspectiveStep(name=reflect_step_name)
        self.analyze_step = AnalysisStep(name=analyze_step_name)
        self.example_generator_step = ExampleGenerationStep(name=example_generator_step_name)
        self.categorization_step = CategorizationStep(name=categorization_step_name)

    async def _execute(self, agent, state: AgentState) -> StepResult:
        plan = state.last_plan
        if plan is None:
            plan = Plan(
                action="stop",
                reasoning="LLM produced invalid plan; defaulting to summarize.",
                tool=None
            )

        if plan.action == "stop":
            return StepResult(output="Stopped", terminated=True)

        if plan.action == "use_tool":
            return await self.tool_step.async_run(agent, state)

        if plan.action == "retrieve":
            return await self.retrieval_step.async_run(agent, state)

        if plan.action == "summarize":
            return await self.summarization_step.async_run(agent, state)

        if plan.action == "reflect":
            return await self.reflect_step.async_run(agent, state)

        if plan.action == "analyze":
            return await self.analyze_step.async_run(agent, state)

        if plan.action == "generate_examples":
            return await self.example_generator_step.async_run(agent, state)

        raise ValueError(f"Unknown plan action: {plan.action}")


class ConditionalStep(AgentStep):

    def __init__(
        self,
        condition: Callable[[AgentState], bool],
        then_step: AgentStep,
        else_step: Optional[AgentStep] = None,
        name: str = "ConditionalStep",
    ):
        AgentStep.__init__(self, name)
        self.condition = condition
        self.then_step = then_step
        self.else_step = else_step

    async def _execute(self, agent, state):
        step = self.then_step if self.condition(state) else self.else_step
        if step is None:
            return StepResult(success=False, output=None)
        return await step.async_run(agent, state)
