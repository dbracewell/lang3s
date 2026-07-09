import logging

from lang3s.core.logger import get_logger

from ..events import AgentEvent, AgentEventType
from ..session import State
from .base import Middleware


class LoggingMiddleware(Middleware):
    def __init__(self, logger_name: str = "LANG3S_AGENT", level: int = logging.DEBUG):
        self.logger = get_logger(logger_name)
        self.level = level

    def __call__(self, event: AgentEvent, state: State) -> None:
        if event.type == AgentEventType.TOOL_CALL_RESULT:
            self.logger.log(
                self.level,
                f"Task: {state.task} | Event: {event.type}, {event.tool_result}",
            )
        elif event.content:
            self.logger.log(
                self.level,
                f"Task: {state.task} | Event: {event.type}, {event.content}",
            )
        elif event.parsed:
            self.logger.log(
                self.level,
                f"Task: {state.task} | Event: {event.type}, {event.parsed}",
            )
        else:
            self.logger.log(
                self.level,
                f"Task: {state.task} | Event: {event.type}",
            )
