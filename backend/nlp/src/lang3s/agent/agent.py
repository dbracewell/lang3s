from typing import List, Optional, Any

from lang3s.models.llm import LLMOrchestrator
from lang3s.models.llm import orchestrator as DEFAULT_ORCHESTRATOR
from .persona import Persona
from .shared_types import StepResult


class Agent:
    """
    The updated Agent class:
    - Handles persona-aware steps
    - Maintains message state
    - Supports sync and async execution
    - Passes persona to steps that want it
    """

    def __init__(
        self,
        orchestrator: Optional[LLMOrchestrator] = None,
        persona: Optional[Persona] = None,
        system_message: Optional[str] = None,
    ):
        self.state_cache = {}
        self.orchestrator = orchestrator or DEFAULT_ORCHESTRATOR
        self.persona = persona
        self.steps: List[Any] = []  # list of AgentStep instances
        self.system_message = system_message

    def add_step(self, step: Any):
        """Add a step to the execution pipeline."""
        self.steps.append(step)

    # ----------------------------------------------------------------------
    # SYNC RUN
    # ----------------------------------------------------------------------
    def run(self, user_message: str) -> Any:
        # State is a list of message dicts
        state: List[dict] = []

        state.append({"role": "system", "content": self.system_message or "You are an agent."})

        # First user message
        state.append({"role": "user", "content": user_message})

        final_output = None

        for step in self.steps:
            # If the step only has async_run => error
            if hasattr(step, "async_run") and not hasattr(step, "run"):
                raise RuntimeError(
                    f"Step {step.__class__.__name__} only supports async_run(). "
                    "Use agent.arun() instead."
                )

            res: StepResult = step.run(self, state, user_message)
            state = res.messages
            final_output = res.output
            if getattr(res, "terminated", False):
                break

        return final_output

    # ----------------------------------------------------------------------
    # ASYNC RUN
    # ----------------------------------------------------------------------
    async def arun(self, user_message: str) -> Any:
        state: List[dict] = []
        state.append({"role": "system", "content": self.system_message or "You are an agent."})
        state.append({"role": "user", "content": user_message})

        final_output = None

        for step in self.steps:
            if hasattr(step, "async_run"):
                res: StepResult = await step.async_run(self, state, user_message)
            else:
                res: StepResult = step.run(self, state, user_message)

            state = res.messages
            final_output = res.output

            if getattr(res, "terminated", False):
                break

        return final_output
