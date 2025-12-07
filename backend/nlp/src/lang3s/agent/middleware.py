import logging
from typing import TYPE_CHECKING, Any

from lang3s.agent.llm.tools import ToolCall

if TYPE_CHECKING:
    from .agent import Agent
    from .llm import ChatModelResponse
    from .shared_types import AgentState, AgentResult


class Middleware:

    def before_agent(self, agent: "Agent", state: "AgentState"):
        pass

    def after_agent(self, agent: "Agent", state: "AgentState", result: "AgentResult"):
        pass

    def before_model(self, agent: "Agent", state: "AgentState", progress: "AgentResult"):
        pass

    def after_model(self, agent: "Agent", state: "AgentState", progress: "AgentResult", result: "ChatModelResponse"):
        pass

    def before_tool_call(self, agent: "Agent", state: "AgentState", progress: "AgentResult", tool: ToolCall):
        pass

    def after_tool_call(self, agent: "Agent", state: "AgentState", progress: "AgentResult", tool: ToolCall,
                        tool_result: Any):
        pass

    def on_progress_update(self, agent: "Agent", state: "AgentState", progress: "AgentResult"):
        pass


class LoggingMiddleware(Middleware):

    def __init__(self, level: int = logging.DEBUG):
        self.logger = logging.getLogger("lang3s.agent")
        self.level = level

    def before_agent(self, agent: "Agent", state: "AgentState"):
        self.logger.log(self.level,
                        f"Beginning Agent Invoke: task={state.task}, persona={state.persona}, persona_mode={state.persona_mode}")

    def before_model(self, agent: "Agent", state: "AgentState", progress: "AgentResult"):
        self.logger.log(
            self.level,
            f"Calling LLM last_message={state.messages[-1]}"
        )

    def after_model(self, agent: "Agent", state: "AgentState", progress: "AgentResult", result: "ChatModelResponse"):
        self.logger.log(
            self.level,
            f"LLM Result={result}"
        )

    def before_tool_call(self, agent: "Agent", state: "AgentState", progress: "AgentResult", tool: ToolCall):
        self.logger.log(
            self.level,
            f"Calling Tool tool_name={tool.name} args={tool.arguments}"
        )

    def after_tool_call(self, agent: "Agent", state: "AgentState", progress: "AgentResult", tool: ToolCall,
                        tool_result: Any):
        self.logger.log(
            self.level,
            f"Finished Calling Tool tool_name={tool.name} args={tool.arguments} result={tool_result}"
        )
