from typing import List

from lang3s.agent.helpers import log_step_result, is_valid_plan_transition
from lang3s.agent.shared_types import AgentState, AgentStep, StepResult, Plan, QueryPlan


def _should_terminate_in_loop(result: StepResult) -> bool:
    if getattr(result, "terminated", False):
        return True

    output = result.output

    if output is None:
        return True

    # If plan is dict-like
    if isinstance(output, dict):
        action = output.get("action")
        if isinstance(action, str) and action.lower() in {"stop", "end", "finish"}:
            return True

    # If output is text
    if isinstance(output, str):
        lowered = output.strip().lower()
        if lowered in {"stop", "halt", "terminate", "done", "finish"}:
            return True

    return False


class LoopStep(AgentStep):

    def __init__(self, max_loops, steps: List[AgentStep], name: str = "LoopStep") -> None:
        AgentStep.__init__(self, name)
        self.max_loops = max_loops
        self.steps = steps
        self.plan_history = []

    async def _execute(self, agent, state: AgentState) -> StepResult:
        result = StepResult(output=None)
        self.plan_history = []

        for _ in range(self.max_loops):
            for step in self.steps:
                result = await step.async_run(agent, state)
                log_step_result(step.name, result)

                if isinstance(result.output, Plan) or isinstance(result.output, QueryPlan):
                    self.plan_history.append(result.output)

                if _should_terminate_in_loop(result):
                    return StepResult(output=state.last_output)

            if self._in_stop_state():
                return result

        state.last_plan = None
        return result

    def _in_stop_state(self):
        if len(self.plan_history) < 2:
            return False

        if self.plan_history[-1].action == "stop":
            return True

        if is_valid_plan_transition(self.plan_history[-2].action, self.plan_history[-1].action):
            return False

        return True
