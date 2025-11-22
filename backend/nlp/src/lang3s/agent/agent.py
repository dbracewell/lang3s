from typing import List, Optional, Any, Dict

from pydantic import BaseModel

from lang3s.agent.steps.generation import GenerationStep
from lang3s.models.llm import LLMOrchestrator
from lang3s.models.llm import orchestrator as DEFAULT_ORCHESTRATOR
from lang3s.utils.async_helper import run_sync
from .helpers import clean_thinking
from .memory import ModelScale
from .shared_types import Plan, StepResult, AgentStep, AgentState, Persona


class AgentResult(BaseModel):
    steps: Dict[str, List[Any]]
    output: Any


class Agent:

    def __init__(
        self,
        orchestrator: Optional[LLMOrchestrator] = None,
        persona: Optional[Persona] = None,
        model_scale: Optional[ModelScale] = None,
    ):
        model_scale = model_scale if model_scale is not None else ModelScale.SMALL
        self.state: AgentState = AgentState(model_scale=model_scale, persona=persona)
        self.orchestrator = orchestrator or DEFAULT_ORCHESTRATOR
        self.steps: List[AgentStep] = []

    def add_step(self, step: Any):
        self.steps.append(step)

    def run(self, system_message: Optional[str], user_message: Optional[str] = None) -> AgentResult:
        return run_sync(self.arun(system_message=system_message, user_message=user_message))

    async def arun(self, system_message: Optional[str], user_message: Optional[str] = None) -> Any:
        self.state.reset_state()

        if system_message is not None:
            self.state.system_message = system_message

        self.state.messages.append({"role": "system",
                                    "content": self.state.system_message or "You are an agent."})

        if user_message is not None:
            self.state.messages.append({"role": "user",
                                        "content": user_message})
            self.state.user_goal = user_message

        if len(self.steps) == 0:
            self.steps.append(GenerationStep())

        for step in self.steps:
            self.state.prune()

            res: StepResult = await step.async_run(self, self.state)
            self.state.cache["examples"] = 0

            if isinstance(res.output, Plan):
                self.state.last_plan = res.output
                self.state.last_output = ""
            elif res.output is not None:
                self.state.last_plan = None
                self.state.last_output = clean_thinking(res.output)
            else:
                self.state.last_plan = None
                self.state.last_output = ""

            if getattr(res, "terminated", False):
                break

        final_steps = {}
        for name, results in self.state.steps.items():
            final_steps[name] = _convert_result(results)

        return AgentResult(steps=final_steps, output=self.state.last_output)


def _convert_result(results: List[StepResult]) -> List[Any]:
    final_list = []
    for res in results:
        if isinstance(res.output, list):
            final_list.extend(res.output)
        else:
            final_list.append(res.output)
    return final_list
