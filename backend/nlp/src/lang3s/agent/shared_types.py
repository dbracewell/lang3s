from typing import Any, List, Optional

from pydantic import BaseModel, ValidationError


class StepResult(BaseModel):
    messages: List[dict]
    output: Any = None
    terminated: bool = False


class AgentStep:
    def run(self, agent, state: List[dict], user_message: str) -> StepResult:
        raise NotImplementedError

    async def async_run(self, agent, state: List[dict], user_message: str) -> StepResult:
        raise NotImplementedError
