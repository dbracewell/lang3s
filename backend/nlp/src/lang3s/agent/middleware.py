import json
import logging
from typing import TYPE_CHECKING, Any

import redis

from lang3s.agent.llm.tools import ToolCall

from .. import config

if TYPE_CHECKING:
    from .agent import Agent
    from .llm import ChatModelResponse
    from .shared_types import AgentResult, AgentState


class Middleware:
    def before_agent(self, agent: "Agent", state: "AgentState"):
        pass

    def after_agent(self, agent: "Agent", state: "AgentState", result: "AgentResult"):
        pass

    def before_model(
        self, agent: "Agent", state: "AgentState", progress: "AgentResult"
    ):
        pass

    def after_model(
        self,
        agent: "Agent",
        state: "AgentState",
        progress: "AgentResult",
        result: "ChatModelResponse",
    ):
        pass

    def before_tool_call(
        self,
        agent: "Agent",
        state: "AgentState",
        progress: "AgentResult",
        tool: ToolCall,
    ):
        pass

    def after_tool_call(
        self,
        agent: "Agent",
        state: "AgentState",
        progress: "AgentResult",
        tool: ToolCall,
        tool_result: Any,
    ):
        pass

    def on_progress_update(
        self, agent: "Agent", state: "AgentState", progress: "AgentResult"
    ):
        pass


class ProgressMonitor(Middleware):
    def before_agent(self, agent: "Agent", state: "AgentState"):
        print(f"{state.progress} / {state.max_progress}")

    def before_tool_call(
        self,
        agent: "Agent",
        state: "AgentState",
        progress: "AgentResult",
        tool: ToolCall,
    ):
        print(f"{state.progress} / {state.max_progress}")

    def after_tool_call(
        self,
        agent: "Agent",
        state: "AgentState",
        progress: "AgentResult",
        tool: ToolCall,
        tool_result: Any,
    ):
        print(f"{state.progress} / {state.max_progress}")

    def on_progress_update(
        self, agent: "Agent", state: "AgentState", progress: "AgentResult"
    ):
        print(f"{state.progress} / {state.max_progress}")

    def after_agent(self, agent: "Agent", state: "AgentState", result: "AgentResult"):
        print(f"{state.progress} / {state.max_progress}")


class LoggingMiddleware(Middleware):
    def __init__(self, level: int = logging.DEBUG):
        self.logger = logging.getLogger("lang3s.agent")
        self.level = level

    def before_agent(self, agent: "Agent", state: "AgentState"):
        self.logger.log(
            self.level,
            f"Beginning Agent Invoke: task={state.task}, persona={state.persona}, persona_mode={state.persona_mode}",
        )

    def before_model(
        self, agent: "Agent", state: "AgentState", progress: "AgentResult"
    ):
        self.logger.log(self.level, f"Calling LLM last_message={state.messages[-1]}")

    def after_model(
        self,
        agent: "Agent",
        state: "AgentState",
        progress: "AgentResult",
        result: "ChatModelResponse",
    ):
        self.logger.log(self.level, f"LLM Result={result}")

    def before_tool_call(
        self,
        agent: "Agent",
        state: "AgentState",
        progress: "AgentResult",
        tool: ToolCall,
    ):
        self.logger.log(
            self.level, f"Calling Tool tool_name={tool.name} args={tool.arguments}"
        )

    def after_tool_call(
        self,
        agent: "Agent",
        state: "AgentState",
        progress: "AgentResult",
        tool: ToolCall,
        tool_result: Any,
    ):
        self.logger.log(
            self.level,
            f"Finished Calling Tool tool_name={tool.name} args={tool.arguments} result={tool_result}",
        )


class NotificationMiddleware(Middleware):
    def __init__(self, userId: str, prompt: str, chatId: str):
        self.userId = userId
        self.prompt = prompt
        self.chatId = chatId
        self.redis_client = redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            db=config.REDIS_DB,
            decode_responses=True,
        )

    def _print_progress(self, state: "AgentState"):
        self.redis_client.publish(
            "events",
            json.dumps(
                {
                    "type": "agent:update",
                    "userid": self.userId,
                    "payload": {
                        "id": self.chatId,
                        "progress": state.progress / max(state.max_progress, 1),
                        "prompt": self.prompt,
                    },
                }
            ),
        )

    def before_agent(self, agent: "Agent", state: "AgentState"):
        self._print_progress(state)

    def before_tool_call(
        self,
        agent: "Agent",
        state: "AgentState",
        progress: "AgentResult",
        tool: ToolCall,
    ):
        self._print_progress(state)

    def after_tool_call(
        self,
        agent: "Agent",
        state: "AgentState",
        progress: "AgentResult",
        tool: ToolCall,
        tool_result: Any,
    ):
        self._print_progress(state)

    def on_progress_update(
        self, agent: "Agent", state: "AgentState", progress: "AgentResult"
    ):
        self._print_progress(state)
