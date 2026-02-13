import logging

from lang3s.utils.logger import get_logger

from ..events import AgentEvent
from ..session import State
from .base import Middleware


class LoggingMiddleware(Middleware):
    def __init__(self, level: int = logging.DEBUG):
        self.logger = get_logger("LANG3S_AGENT")
        self.level = level

    def __call__(self, event: AgentEvent, state: State) -> None:
        self.logger.log(
            self.level,
            f"Task: {state.task} | Event: {event.type}, {event.content}",
        )
