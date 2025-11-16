import re
from typing import List, Any

from lang3s.agent.shared_types import AgentStep, StepResult
from lang3s.agent.steps.planning import Plan, QueryPlan


class LoopStep(AgentStep):

    def __init__(self, max_loops, steps: List[AgentStep]) -> None:
        self.max_loops = max_loops
        self.steps = steps
        self.plan_history = []

    def run(self, agent, state: List[dict], user_message: str) -> StepResult:
        result = StepResult(messages=state, output=user_message)
        self.plan_history = []
        for _ in range(self.max_loops):
            for step in self.steps:
                result = step.run(agent, state, user_message)
                state = result.messages
                agent.state_cache["last_output"] = result.output

                if isinstance(result.output, Plan) or isinstance(result.output, QueryPlan):
                    self.plan_history.append(result.output)
                    agent.state_cache["last_plan"] = result.output

                if getattr(result, "terminated", False):
                    return StepResult(
                        messages=state,
                        output=result.output,
                        terminated=True
                    )

                if self._should_stop_from_content(result.output):
                    return StepResult(
                        messages=state,
                        output=result.output,
                        terminated=True
                    )

            if self._should_terminate_loop():
                return StepResult(
                    messages=state,
                    output=result.output,
                    terminated=True
                )

        return result

    def _should_terminate_loop(self):
        if len(self.plan_history) == 0:
            return False

        i = 0
        last_plan = None
        while i < len(self.plan_history):
            last_plan = self.plan_history[i]
            if last_plan.action in ["summarize", "stop"]:
                return True
            if last_plan.action in ["analyze", "reflect"]:
                break
            i += 1
        if last_plan is None:
            return False

        same_action_count = 0
        for i in range(1, len(self.plan_history)):
            plan = self.plan_history[i]
            if plan.action in ["summarize", "stop"]:
                return True
            if plan.action in ["analyze", "reflect"] and plan.action == last_plan.action:
                same_action_count += 1
                if same_action_count >= 2:
                    return True
            else:
                same_action_count = 0
                last_plan = plan
        return False

    async def async_run(self, agent, state: List[dict], user_message: str) -> StepResult:
        result = StepResult(messages=state, output=user_message)
        for _ in range(self.max_loops):
            for step in self.steps:
                if hasattr(step, "async_run"):
                    result = await step.async_run(agent, state, user_message)
                else:
                    result = step.run(agent, state, user_message)

                state = result.messages
                agent.state_cache["last_output"] = result.output

                if isinstance(result.output, Plan) or isinstance(result.output, QueryPlan):
                    self.plan_history.append(result.output)
                    agent.state_cache["last_plan"] = result.output

                if getattr(result, "terminated", False):
                    return StepResult(
                        messages=state,
                        output=result.output,
                        terminated=True
                    )

                if self._should_stop_from_content(result.output):
                    return StepResult(
                        messages=state,
                        output=result.output,
                        terminated=True
                    )

            if self._should_terminate_loop():
                return StepResult(
                    messages=state,
                    output=result.output,
                    terminated=True
                )

        return result

    def _should_stop_from_content(self, output: Any) -> bool:
        """
        Detect stop signals from LLM or planning steps.
        Supports:
        - JSON dict with action="stop"
        - Text saying "stop" or "terminate"
        """
        if output is None:
            return False

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
