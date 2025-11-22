from collections import defaultdict
from enum import Enum, auto
from typing import List, Optional, Any, Dict, cast, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from .agent import Agent

from pydantic import BaseModel

from lang3s.utils.async_helper import run_sync
from .memory import ModelScale, UnifiedMemory, MemoryConfig
from .helpers import log_step_result


class ExampleList(BaseModel):
    examples: List[str]


class StepResult(BaseModel):
    output: Any = None
    terminated: bool = False
    success: bool = True


class QueryPlan(BaseModel):
    queries: List[str]
    reasoning: str
    action: Literal["query", "stop"]


class Plan(BaseModel):
    action: Literal[
        "use_tool", "retrieve", "summarize", "stop", "reflect", "analyze", "generate_examples", "categorize"]
    tool: Optional[str] = None
    args: Optional[dict] = None
    target_category: Optional[str] = None
    reasoning: str


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
                "Rewrite or Generate text so the expression style matches the persona's tone. "
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
                'Generate search or retrieval queries shaped by the persona’s perspective. '
                'Queries should reflect what the persona prioritizes or questions while '
                'remaining objective and non-inflammatory.'
            )

        if self is PersonaMode.PLANNING:
            return (
                'Determine the best action to take to answer the user as the persona. '
                'Actions should reflect what the persona prioritizes or questions while '
                'remaining objective and non-inflammatory.'
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
    guardrails: str = (
        "Preserve factual accuracy.\n"
        "Avoid stereotypes, caricature, and extreme rhetoric.\n"
        "Do not encourage or discourage specific political actions.\n"
        "Stay respectful and grounded.\n"
    )

    def build_prompt(self, mode: PersonaMode):
        if mode == PersonaMode.NONE:
            return ""
        base = mode.get_instructions()
        parts = [
            f"Persona name: {self.name}",
            f"Persona description: {self.description}",
            "",
            "Persona Guardrails:",
            self.guardrails.strip(),
            "",
        ]

        # Add relevant persona fields depending on the mode
        if mode is PersonaMode.TONE:
            parts.append("Persona Tone Instructions:")
            parts.append(self.tone_instructions.strip())

        elif mode in (PersonaMode.PERSPECTIVE, PersonaMode.ANALYSIS,
                      PersonaMode.SUMMARIZATION, PersonaMode.QUERY_PLANNING):
            parts.append("Persona Worldview Instructions:")
            parts.append(self.worldview_instructions.strip())

        parts.append("")
        parts.append("Mode Instructions:")
        parts.append(base)

        return "\n".join(parts)


class AgentState:

    def __init__(self, persona: Optional["Persona"], model_scale=ModelScale.SMALL):
        self.persona = persona
        self.messages: List[dict] = []
        self.cache: Dict[str, Any] = {}
        self.memory_config = MemoryConfig(scale=model_scale)
        self.last_plan: Optional[Plan] = None
        self.last_output: Optional[Any] = None
        self.system_message: str = "You are a helpful agent."
        self.user_goal: Optional[str] = None

    def reset_state(self):
        self.messages = []
        self.cache = {"steps": defaultdict(list), "local_memory": UnifiedMemory(self.memory_config)}
        self.last_plan = None
        self.last_output = None
        self.system_message = "You are a helpful agent."
        self.user_goal = None

    def update(self, new_message: dict):
        self.messages.append(new_message)

    def create_base_prompt(self, persona_mode: Optional[PersonaMode] = None) -> str:
        persona_text = None
        if self.persona is not None and persona_mode is not None:
            persona_text = self.persona.build_prompt(persona_mode)
        return self.local_memory.compile(
            messages=self.messages,
            last_output=self.last_output,
            last_plan=self.last_plan,
            user_goal=self.user_goal,
            persona_text=persona_text,
        )

    def get_llm_messages(self, history: int = 1):
        if self.system_message is not None:
            return [{"role": "system", "content": self.system_message}] + self.messages[-history:]
        return self.messages[-history:]

    def prune(self):
        self.messages = self.local_memory.prune_state(self.messages)

    @property
    def local_memory(self) -> UnifiedMemory:
        return cast(UnifiedMemory, self.cache["local_memory"])

    @property
    def steps(self) -> Dict[str, List[StepResult]]:
        return cast(Dict[str, List[StepResult]], self.cache["steps"])


class AgentStep:

    def __init__(self, name: Optional[str]):
        self.name = name or self.__class__.__name__

    async def _execute(self, agent: "Agent", state: AgentState) -> StepResult:
        raise NotImplementedError

    def run(self, agent: "Agent", state: AgentState) -> StepResult:
        result = run_sync(self._execute(agent, state))
        return self._process_result(state, result)

    async def async_run(self, agent: "Agent", state: AgentState) -> StepResult:
        result = await self._execute(agent, state)
        return self._process_result(state, result)

    def _process_result(self, state: AgentState, result: StepResult) -> StepResult:
        if isinstance(result.output, Plan):
            state.last_plan = result.output
        else:
            state.last_output = result.output
        if self.__class__.__name__ not in ["PlanRouterStep", "LoopStep"]:
            log_step_result(self.name, result)
            state.steps[self.name].append(result)
        return result


class PersonaAwareStep(AgentStep):
    def __init__(self, name: Optional[str], mode: PersonaMode):
        super().__init__(name)
        self.mode = mode


class RetrievalResult(BaseModel):
    result: str
    score: float

    def __eq__(self, other):
        return self.result == other.result

    def __hash__(self):
        return hash(self.result)
