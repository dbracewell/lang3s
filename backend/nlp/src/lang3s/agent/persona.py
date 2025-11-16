"""
persona_module.py

Persona support for your agent framework:
- PersonaMode enum
- Persona class
- PersonaAwareStep base class
- Concrete persona-aware steps for analysis, planning, synthesis, and rewriting.

Assumptions:
- There is an Agent class with attributes:
    - orchestrator: LLMOrchestrator (has .chat(messages, ...) method)
    - persona: Optional[Persona]
- There is an AgentStep base class with:
    def run(self, agent, state, user_message) -> StepResult
- There is a StepResult Pydantic model or dataclass:
    fields: messages: list[dict], output: Any, terminated: bool = False
"""

from enum import Enum, auto
from typing import List, Optional

from pydantic import BaseModel, ValidationError
from .shared_types import AgentStep, StepResult


class PersonaMode(Enum):
    """How a Persona should influence a step."""
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

    # -----------------------------------------------------------
    # Instructions enriched with persona-specific data
    # -----------------------------------------------------------
    def build_instructions(self, persona: Optional["Persona"]) -> str:
        """
        Produces a full block of instructions that combines:
        - persona metadata (tone, worldview, guardrails)
        - mode-specific behavior instructions
        """
        base = self.get_instructions()

        if persona is None or persona.name == "Neutral":
            return base

        parts = [
            f"Persona name: {persona.name}",
            f"Persona description: {persona.description}",
            "",
            "Persona Guardrails:",
            persona.guardrails.strip(),
            "",
        ]

        # Add relevant persona fields depending on the mode
        if self is PersonaMode.TONE:
            parts.append("Persona Tone Instructions:")
            parts.append(persona.tone_instructions.strip())

        elif self in (PersonaMode.PERSPECTIVE, PersonaMode.ANALYSIS,
                      PersonaMode.SUMMARIZATION, PersonaMode.QUERY_PLANNING):
            parts.append("Persona Worldview Instructions:")
            parts.append(persona.worldview_instructions.strip())

        parts.append("")
        parts.append("Mode Instructions:")
        parts.append(base)

        return "\n".join(parts)


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


class PersonaAwareStep(AgentStep):
    """
    Base class for steps that *optionally* use a persona.

    Subclasses define:
      - persona_modes: List[PersonaMode] they support
      - run_no_persona(...)
      - run_with_persona(...)

    The default run(...) implementation:
      - looks for agent.persona
      - checks if it supports any of persona_modes
      - delegates appropriately
    """

    persona_modes: List[PersonaMode] = []

    def __init__(self, mode: PersonaMode):
        self.mode = mode

    def run(self, agent, state: List[dict], user_message: str) -> StepResult:
        persona: Optional[Persona] = getattr(agent, "persona", None)
        if not persona:
            return self.run_no_persona(agent, state, user_message)

        return self.run_with_persona(agent, state, user_message, persona, self.mode)

    # Subclasses implement these:
    def run_no_persona(self, agent, state: List[dict], user_message: str) -> StepResult:
        raise NotImplementedError

    def run_with_persona(
        self,
        agent,
        state: List[dict],
        user_message: str,
        persona: Persona,
        mode: PersonaMode,
    ) -> StepResult:
        raise NotImplementedError

    # Shared helper to build persona prompts
    @staticmethod
    def build_persona_prompt(
        persona: Persona,
        mode: PersonaMode,
        task_instructions: str,
        content: str,
        history: int = 1
    ) -> str:
        mode_instructions = mode.build_instructions(persona=persona)
        prompt = mode_instructions
        if task_instructions.strip() != "":
            prompt += f"\n\nTask:\n{task_instructions}\n"
        if history > 0:
            prompt += f"\nInclude the last {history} messages as context.\n\n"
        return f"{prompt}\n\nContent:\n---\n{content}\n---\n"


class PersonaContentAnalysisStep(PersonaAwareStep):
    """
    Analyze the user's request and/or retrieved content.

    - Without persona: neutral analysis.
    - With persona (ANALYSIS mode): analysis with worldview emphasis.
    """

    persona_modes = [PersonaMode.ANALYSIS]

    def run_no_persona(self, agent, state: List[dict], user_message: str) -> StepResult:
        prompt = f"""
Analyze the user's request and any context so far.
Identify key topics, entities, and claims. Respond in plain text.
User request:
{user_message}
"""
        state.append({"role": "user", "content": prompt})
        result = agent.orchestrator.chat(state)
        analysis = result["content"]
        state.append({"role": "assistant", "content": analysis})
        return StepResult(messages=state, output=analysis)

    def run_with_persona(
        self,
        agent,
        state: List[dict],
        user_message: str,
        persona: Persona,
        mode: PersonaMode,
    ) -> StepResult:
        task = (
            "Analyze the user's request and context. Identify key topics, entities, and claims. "
            "Highlight aspects that this persona would especially focus on, but do not change facts."
        )
        prompt = self.build_persona_prompt(persona, mode, task, user_message)
        state.append({"role": "user", "content": prompt})
        result = agent.orchestrator.chat(state)
        analysis = result["content"]
        state.append({"role": "assistant", "content": analysis})
        return StepResult(messages=state, output=analysis)


class PersonaResearchPlan(BaseModel):
    action: str
    tool: str
    queries: List[str]
    reasoning: str


class PersonaResearchPlanningStep(PersonaAwareStep):
    """
    Produce a research plan compatible with your ToolStep/RobustToolLoopStep:

    {
      "action": "use_tool",
      "tool": "<tool name>",
      "queries": [...],
      "reasoning": "..."
    }

    - Without persona: neutral query planning.
    - With persona (QUERY_PLANNING): queries framed through worldview.
    """

    persona_modes = [PersonaMode.QUERY_PLANNING]

    def __init__(self, available_tools: List[str]):
        self.available_tools = available_tools

    def _base_prompt(self, user_message: str) -> str:
        return f"""
The user is asking:

{user_message}

Generate a research plan in JSON with fields:
- "action": MUST be "use_tool"
- "tool": one of {self.available_tools}
- "queries": list of search queries
- "reasoning": why these queries and this tool.

Return ONLY JSON.
"""

    def run_no_persona(self, agent, state: List[dict], user_message: str) -> StepResult:
        prompt = self._base_prompt(user_message)
        state.append({"role": "user", "content": prompt})
        result = agent.orchestrator.chat(state)
        raw = result["content"]

        try:
            plan = PersonaResearchPlan.model_validate_json(raw)
        except ValidationError:
            # fallback minimal plan
            plan = PersonaResearchPlan(
                action="use_tool",
                tool=self.available_tools[0],
                queries=[user_message],
                reasoning="Fallback plan due to invalid JSON.",
            )

        state.append({"role": "assistant", "content": plan.model_dump_json()})
        return StepResult(messages=state, output=plan)

    def run_with_persona(
        self,
        agent,
        state: List[dict],
        user_message: str,
        persona: Persona,
        mode: PersonaMode,
    ) -> StepResult:
        task = (
            "Generate a JSON research plan for querying tools, reflecting this persona's focus. "
            "You must still respect the required JSON schema and available tools."
        )
        base_prompt = self._base_prompt(user_message)
        prompt = self.build_persona_prompt(persona, mode, task, base_prompt)
        state.append({"role": "user", "content": prompt})
        result = agent.orchestrator.chat(state)
        raw = result["content"]

        try:
            plan = PersonaResearchPlan.model_validate_json(raw)
        except ValidationError:
            plan = PersonaResearchPlan(
                action="use_tool",
                tool=self.available_tools[0],
                queries=[user_message],
                reasoning="Fallback persona plan due to invalid JSON.",
            )

        state.append({"role": "assistant", "content": plan.model_dump_json()})
        return StepResult(messages=state, output=plan)


class PersonaSynthesisStep(PersonaAwareStep):
    """
    Synthesize gathered evidence into a summary.

    - Without persona: neutral summary.
    - With persona (SUMMARIZATION): summary framed by worldview/tone.
    """

    persona_modes = [PersonaMode.SUMMARIZATION, PersonaMode.PERSPECTIVE]

    def __init__(self, instructions: Optional[str] = None):
        self.instructions = instructions or (
            "Summarize the information gathered so far. Keep it concise and factual."
        )

    def run_no_persona(self, agent, state: List[dict], user_message: str) -> StepResult:
        prompt = self.instructions
        state.append({"role": "user", "content": prompt})
        result = agent.orchestrator.chat(state)
        summary = result["content"]
        state.append({"role": "assistant", "content": summary})
        return StepResult(messages=state, output=summary)

    def run_with_persona(
        self,
        agent,
        state: List[dict],
        user_message: str,
        persona: Persona,
        mode: PersonaMode,
    ) -> StepResult:
        task = (
            "Summarize the gathered information, emphasizing what this persona would focus on, "
            "while keeping facts accurate and not engaging in persuasion."
        )
        # Neutral context: last assistant/tool content is the evidence
        evidence_chunks = [
            m["content"] for m in state if m["role"] in ("assistant", "tool")
        ]
        evidence_text = "\n\n".join(evidence_chunks[-10:]) or "No evidence found."

        prompt = self.build_persona_prompt(persona, mode, task, evidence_text)
        state.append({"role": "user", "content": prompt})
        result = agent.orchestrator.chat(state)
        summary = result["content"]
        state.append({"role": "assistant", "content": summary})
        return StepResult(messages=state, output=summary)


class PersonaPerspectiveRewriteStep(PersonaAwareStep):
    """
    Final rewrite step that takes the latest assistant message (neutral analysis/synthesis)
    and rewrites it from the persona's perspective.

    - Without persona: passes through.
    - With persona (PERSPECTIVE or TONE): perspective + tone.
    """

    persona_modes = [PersonaMode.PERSPECTIVE, PersonaMode.TONE, PersonaMode.SUMMARIZATION]

    def run_no_persona(self, agent, state: List[dict], user_message: str) -> StepResult:
        # No-op: just return the last assistant content
        assistant_msgs = [m for m in state if m["role"] == "assistant"]
        if not assistant_msgs:
            return StepResult(messages=state, output=None)
        return StepResult(messages=state, output=assistant_msgs[-1]["content"], terminated=True)

    def run_with_persona(
        self,
        agent,
        state: List[dict],
        user_message: str,
        persona: Persona,
        mode: PersonaMode,
    ) -> StepResult:
        assistant_msgs = [m for m in state if m["role"] == "assistant"]
        if not assistant_msgs:
            return StepResult(messages=state, output=None)
        neutral_text = assistant_msgs[-1]["content"]

        task = (
            "Rewrite this analysis in the persona's voice and perspective. "
            "Highlight values, concerns, and framing relevant to the persona, "
            "but do not change factual claims or tell the user what to do."
        )

        prompt = self.build_persona_prompt(persona, mode, task, neutral_text)
        state.append({"role": "user", "content": prompt})
        result = agent.orchestrator.chat(state)
        rewritten = result["content"]
        state.append({"role": "assistant", "content": rewritten})
        return StepResult(messages=state, output=rewritten, terminated=True)
