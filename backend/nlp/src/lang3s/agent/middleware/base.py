from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lang3s.agent.events import AgentEvent
    from lang3s.agent.session import State


class Middleware(ABC):
    @abstractmethod
    def __call__(self, event: AgentEvent, state: State) -> None:
        pass
