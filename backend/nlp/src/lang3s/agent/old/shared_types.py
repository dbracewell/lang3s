from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, Type

from lang3s.llm.old.chat_model import ChatModelResponse
from lang3s.llm.token_estimator import TokenEstimator

if TYPE_CHECKING:
    pass

from pydantic import BaseModel


@dataclass
class AgentResult:
    content: List[str] = field(default_factory=list)
    parsed: List[Any] = field(default_factory=list)
    exception: Optional[Exception] = field(default=None)
    success: bool = field(default=True)
    trace: List[Tuple[List[Dict[str, Any]], ChatModelResponse]] = field(
        default_factory=list
    )

    def update(
        self, chat_model_response: ChatModelResponse, messages: List[Dict[str, Any]]
    ) -> "AgentResult":
        if (
            not chat_model_response.tool_calls
            and chat_model_response.content
            and len(chat_model_response.content.strip()) > 0
        ):
            self.content.append(chat_model_response.content.strip())
        if chat_model_response.parsed:
            self.parsed.append(chat_model_response.parsed)
        if chat_model_response.exception:
            self.exception = chat_model_response.exception
            self.success = False
        self.trace.append((messages.copy(), chat_model_response))
        return self

    def merge(self, agent_result: "AgentResult") -> None:
        if (
            agent_result.content is None
            and agent_result.parsed is None
            and agent_result.exception is None
        ):
            return
        self.content.extend(agent_result.content)
        self.parsed.extend(agent_result.parsed)
        self.trace.extend(agent_result.trace)
        if not self.exception:
            self.exception = agent_result.exception
        if self.success:
            self.success = agent_result.success


class PersonaMode(Enum):
    NONE = auto()
    TONE = auto()  # Rewrite expression style only
    PERSPECTIVE = auto()  # Interpret content through worldview
    ANALYSIS = auto()  # How the agent reasons about content
    QUERY_PLANNING = auto()  # How queries are framed
    SUMMARIZATION = auto()  # How summaries are framed
    PLANNING = auto()
    CONTRAST = auto()

    # -----------------------------------------------------------
    # Base textual instructions for each persona mode
    # -----------------------------------------------------------
    def get_instructions(self) -> str:
        """
        Returns mode-specific instructions to help guide the LLM.
        These are mode-level, independent of a specific persona.
        """

        if self is PersonaMode.NONE:
            return (
                "Operate with a neutral tone, without adding stylistic or "
                "worldview modifications."
            )

        if self is PersonaMode.TONE:
            return (
                "Answer the user in a style that matches the persona's tone. "
                "Do NOT alter factual meaning or add/remove information—only adjust tone."
            )

        if self is PersonaMode.PERSPECTIVE:
            return (
                "Interpret or frame the content through the persona's worldview. "
                "Highlight what the persona would focus on, but do NOT introduce "
                "new facts or exaggerations. Maintain accuracy and avoid bias."
            )

        if self is PersonaMode.ANALYSIS:
            return (
                "Analyze the content using the persona's values or interpretive lens. "
                "Describe what the persona would consider important, concerning, or noteworthy. "
                "Stay factual; the persona lens modifies reasoning focus, not truth."
            )

        if self is PersonaMode.QUERY_PLANNING:
            return (
                "Generate search or retrieval queries shaped by the persona’s perspective. "
                "Queries should reflect what the persona prioritizes or questions while "
                "remaining objective and non-inflammatory."
            )

        if self is PersonaMode.PLANNING:
            return (
                "Determine the best action to take to answer the user as the persona. "
                "Actions should reflect what the persona prioritizes or questions while "
                "remaining objective and non-inflammatory."
            )

        if self is PersonaMode.SUMMARIZATION:
            return (
                "Summarize content from the persona's perspective—emphasizing aspects "
                "the persona values—while keeping the summary concise, accurate, and grounded."
            )

        if self is PersonaMode.CONTRAST:
            return (
                "Contrast the content using the persona's perspective—emphasizing aspects. "
                "Provide a response that would likely be given by someone of this persona.."
            )

        raise ValueError(f"No instructions defined for mode: {self.name}")


class Persona(BaseModel):
    """
    A reusable persona definition.

    - name: descriptive label
    - description: high-level explanation of worldview / style
    - tone_instructions: how to shape tone/voice
    - worldview_instructions: how to shape interpretation/analysis
    - guardrails: safety constraints (no caricature, no persuasion, etc.)
    - modes: PersonaMode values where persona should apply
    """

    name: str
    description: str
    tone_instructions: str = ""
    worldview_instructions: str = ""
    guardrails: str = ""

    def build_prompt(self, mode: PersonaMode, task: str):
        if mode == PersonaMode.NONE:
            return ""
        base = mode.get_instructions()
        parts = [
            "Persona name:",
            self.name,
            "",
            "Persona description:",
            self.description,
            "",
        ]

        if self.guardrails:
            parts.append("Persona Guardrails:")
            parts.append(self.guardrails.strip())
            parts.append("")

        if mode is PersonaMode.TONE:
            parts.append("Persona Tone Instructions:")
            parts.append(self.tone_instructions.strip())
            parts.append("")

        elif mode in (
            PersonaMode.PERSPECTIVE,
            PersonaMode.ANALYSIS,
            PersonaMode.SUMMARIZATION,
            PersonaMode.QUERY_PLANNING,
        ):
            parts.append("Persona Worldview Instructions:")
            parts.append(self.worldview_instructions.strip())
            parts.append("")

        parts.append("Mode Instructions:")
        parts.append(base)
        parts.append("")

        if task:
            parts.append("User Task:")
            parts.append(task)

        return "\n".join(parts).strip()


@dataclass
class AgentState:
    task: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    temperature: Optional[float] = field(default=None)
    max_output_tokens: Optional[int] = field(default=None)
    tools: Optional[List[Callable[..., Any]]] = field(default=None)
    output_format: Optional[Type[BaseModel]] = field(default=None)
    persona: Optional[Persona] = field(default=None)
    persona_mode: Optional[PersonaMode] = field(default=None)
    system_message: Optional[str] = field(default=None)
    cache: Dict[str, Any] = field(default_factory=dict)
    max_history: int = field(default=50)
    terminated: bool = field(default=False)
    max_input_tokens: int = field(default=1000000)
    progress: int = field(default=0)
    max_progress: int = field(default=0)

    @classmethod
    def from_existing(
        cls, state: "AgentState", task: str, persona_mode: Optional[PersonaMode] = None
    ) -> "AgentState":
        new_state = cls(**state.__dict__)
        new_state.messages = []
        new_state.task = task
        new_state.persona_mode = persona_mode
        new_state.terminated = False
        new_state.cache = {}
        return new_state

    def begin_agent(self):
        self.messages.clear()
        self.terminated = False
        self.max_progress = 0
        self.progress = 0
        # self.messages.append(
        #     {
        #         "role": "system",
        #         "content": self.system_message or "You are a helpful agent.",
        #     }
        # )

    def update(self, messages: dict | List[dict]):
        if isinstance(messages, list):
            self.messages.extend([self._set_priority(m) for m in messages])
        else:
            self.messages.append(self._set_priority(messages))

    def _set_priority(self, message: dict) -> dict:
        if "_priority" in message:
            return message
        priority = 1
        role = message["role"]
        if role == "system":
            priority = 100
        elif role == "tool":
            priority = 10
        elif role == "user":
            priority = 5
        message["_priority"] = priority
        return message

    def truncate(self, token_estimator: TokenEstimator):
        if not self.messages:
            return

        self.remove_messages_if(
            lambda m: m.get("is_plan", False)
            or (m["role"] == "tool" and m.get("is_empty", False))
        )

        system_msg = self.messages[0] if self.messages[0]["role"] == "system" else None
        history = self.messages[1:] if system_msg else self.messages[:]
        if len(history) > self.max_history:
            history = history[-self.max_history :]

        new_messages = []
        if system_msg:
            new_messages.append(system_msg)
        new_messages.extend(history)

        total_tokens = 0
        for message in new_messages:
            if "_token_count" not in message:
                message["_token_count"] = token_estimator.count_messages([message])
            total_tokens += message["_token_count"]

        while total_tokens > self.max_input_tokens and len(new_messages) > 3:
            candidates = new_messages[1:]
            min_priority = min(m.get("_priority", 1) for m in candidates)
            for i in range(1, len(new_messages)):
                if new_messages[i].get("_priority", 1) == min_priority:
                    removed = new_messages.pop(i)
                    total_tokens -= removed["_token_count"]
                    break

        self.messages = new_messages

    def remove_messages_if(self, filter: Callable[[Dict[str, Any]], bool]):
        self.messages = [m for m in self.messages if not filter(m)]
