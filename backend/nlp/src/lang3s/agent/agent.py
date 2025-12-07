from typing import Any, Callable, List, Optional, Type

from pydantic import BaseModel

from lang3s import config
from lang3s.agent.middleware import Middleware
from lang3s.agent.token_estimator import TokenEstimator
from .llm import ChatModel
from .shared_types import AgentState, Persona, PersonaMode, AgentResult
from .strategy import Strategy, OneShotStrategy, PlanningStrategy


class Agent:

    def __init__(self, *,
                 strategy: Optional[Strategy] = None,
                 model: Optional[ChatModel] = None,
                 system_message: Optional[str] = None,
                 temperature: Optional[float] = None,
                 max_output_tokens: Optional[int] = None,
                 max_input_tokens: Optional[int] = None,
                 max_history: int = 50,
                 tools: Optional[List[Callable[..., Any]]] = None,
                 output_format: Optional[Type[BaseModel]] = None,
                 persona: Optional[Persona] = None,
                 middleware: Optional[List[Middleware]] = None,
                 ):
        self.__starting_state = AgentState(
            system_message=system_message,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            max_input_tokens=max_input_tokens or 1000000,
            tools=tools,
            output_format=output_format,
            persona=persona,
            max_history=max_history,
            task="",
        )
        self.middleware = middleware or []
        self.model = model or ChatModel(config.LLM_MODEL)
        self.token_estimator = TokenEstimator(model or config.LLM_MODEL)
        self.strategy: Strategy
        if strategy is None:
            if self.__starting_state.tools is None:
                self.strategy = OneShotStrategy()
            else:
                self.strategy = PlanningStrategy()
        else:
            self.strategy = strategy
        self.strategy.set_middleware(self.middleware)

    def invoke(self,
               prompt: str,
               *,
               persona_mode: Optional[PersonaMode] = None) -> AgentResult:
        state = AgentState.from_existing(self.__starting_state,
                                         task=prompt,
                                         persona_mode=persona_mode)
        state.begin_agent()
        for middleware in self.middleware:
            middleware.before_agent(self, state)
        try:
            result = self.strategy.run(self, state)
            for middleware in self.middleware:
                middleware.after_agent(self, state, result)
            return result
        except Exception as e:
            print(e)

    async def async_invoke(self,
                           prompt: str,
                           *,
                           persona_mode: Optional[PersonaMode] = None) -> AgentResult:
        state = AgentState.from_existing(self.__starting_state,
                                         task=prompt,
                                         persona_mode=persona_mode)
        state.begin_agent()
        for middleware in self.middleware:
            middleware.before_agent(self, state)
        try:
            result = await self.strategy.async_run(self, state)
            for middleware in self.middleware:
                middleware.after_agent(self, state, result)
            return result
        except Exception as e:
            print(e)
