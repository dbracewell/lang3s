from typing import Callable, List, Optional

from lang3s.agent.helpers import is_valid_plan_transition
from lang3s.agent.shared_types import AgentState, AgentStep, StepResult, Plan, QueryPlan


class LoopStep(AgentStep):

    def __init__(self,
                 max_loops: int,
                 steps: List[AgentStep],
                 on_start: Optional[Callable[[AgentState], None]] = None,
                 on_step_complete: Optional[Callable[[AgentState, StepResult], StepResult]] = None,
                 on_end_of_iteration: Optional[Callable[[AgentState], None]] = None,
                 on_finish: Optional[Callable[[AgentState, StepResult], None]] = None,
                 name: str = "LoopStep") -> None:
        AgentStep.__init__(self, name)
        self.max_loops = max_loops
        self.steps = steps
        self.plan_history = []
        self.initializer = on_start
        self.updater = on_end_of_iteration
        self.finalizer = on_finish
        self.on_step_complete = on_step_complete

    async def _execute(self, agent, state: AgentState) -> StepResult:
        result = StepResult(output=None)
        self.plan_history = []

        if self.initializer is not None:
            self.initializer(state)
        state.cache["examples"] = 0
        
        is_stopped = False
        for _ in range(self.max_loops):
            for step in self.steps:
                result = await step.async_run(agent, state)
                if self.on_step_complete is not None:
                    result = self.on_step_complete(state, result)

                if isinstance(result.output, Plan) or isinstance(result.output, QueryPlan):
                    self.plan_history.append(result.output)

                if self._in_stop_state() or getattr(result, "terminated", False):
                    result = StepResult(output=state.last_output)
                    is_stopped = True
                    break

            if is_stopped:
                break
            elif self.updater is not None:
                self.updater(state)

        if self.finalizer is not None:
            self.finalizer(state, result)

        state.cache["examples"] = 0
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
