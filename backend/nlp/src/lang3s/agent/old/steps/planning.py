from typing import List, Optional

from pydantic import ValidationError

from lang3s.agent.old.helpers import get_valid_next_actions
from lang3s.agent.old.shared_types import (
    AgentState,
    PersonaAwareStep,
    PersonaMode,
    Plan,
    QueryPlan,
    StepResult,
)


class PlanStep(PersonaAwareStep):

    def __init__(self,
                 available_tools: Optional[List[str]] = None,
                 history: int = 100,
                 name: str = "PlanStep"):
        super().__init__(name=name, mode=PersonaMode.PLANNING)
        self.available_tools = available_tools or []
        self.history = history

    def _task_prompt(self, state: AgentState) -> str:
        return f"""
    {state.create_base_prompt(self.mode)}
    
    You must choose the NEXT ACTION to move toward completing the user's task.

    Available tools: {self.available_tools}

    ACTIONS:
    - "use_tool"          → use a tool; requires "tool" and "args"
    - "retrieve"          → retrieve data from a retriever/vector store
    - "summarize"         → produce a final or intermediate summary
    - "reflect"           → briefly evaluate progress and decide next step
    - "analyze"           → analyze previous results
    - "generate_examples" → create example sentences; requires "target_category"
    - "categorize"        → classify items; requires "target_category"
    - "stop"              → finish; only when task is complete

    {get_valid_next_actions(state.last_plan)}
    
    If you are DONE with your task select "stop".

    RULES:
    - USE the summary above; do NOT ignore previous steps.
    - KEEP reasoning short (1–2 sentences).
    - DO NOT repeat the same action more than twice in a row.
    - If you already have enough information for an answer, choose "summarize" or "stop".
    - If you just summarized, choose "stop".

    OUTPUT FORMAT (JSON ONLY):
    {{
      "action": "<one of the above>",
      "tool": "<tool name>" or null,
      "args": {{ ... }} or null,
      "target_category": "<category>" or null,
      "reasoning": "short explanation"
    }}

    Return ONLY the JSON. No extra text.
    """.strip()

    def _call_model_for_plan(self, agent, state: List[dict], prompt: str) -> Plan:
        state.append({"role": "user", "content": prompt})
        raw = agent.orchestrator.chat(state, response_model=None)["content"]

        try:
            plan = Plan.model_validate_json(raw)
        except Exception:
            # one retry with a more explicit correction instruction
            correction = "The previous output was invalid. Regenerate a strictly valid JSON Plan object."
            state.append({"role": "user", "content": correction})
            raw = agent.orchestrator.chat(state, response_model=None)["content"]
            plan = Plan.model_validate_json(raw)

        state.append({"role": "assistant", "content": raw})
        return plan

    async def _execute(
        self,
        agent,
        state: AgentState,
    ) -> StepResult:
        state.update({"role": "user", "content": self._task_prompt(state)})
        result = await agent.orchestrator.achat(
            state.get_llm_messages(),
            response_model=Plan,
            tool_names=None
        )
        plan = result["content"]
        try:
            parsed = Plan.model_validate_json(plan)
        except Exception:
            correction = "The previous output was invalid. Regenerate a strictly valid JSON Plan object."
            state.update({"role": "user", "content": correction})
            plan = (await agent.orchestrator.achat(state.get_llm_messages(), response_model=None))["content"]
            try:
                parsed = Plan.model_validate_json(plan)
            except Exception:
                state.update({"role": "assistant", "content": plan, "status": "failed"})
                return StepResult(success=False, output=None)

        state.update({"role": "assistant", "content": plan})
        state.last_plan = parsed

        return StepResult(output=parsed, terminated=parsed.action == "stop")


class QueryPlanner(PersonaAwareStep):
    def __init__(self, name: str = "QueryPlanner"):
        PersonaAwareStep.__init__(self, mode=PersonaMode.QUERY_PLANNING, name=name)

    def _base_prompt(self, state: AgentState) -> str:
        persona_task = ("Generate a JSON research plan for querying documents, reflecting this persona's focus. "
                        "You must still respect the required JSON schema.")

        if state.persona is None:
            persona_task = ""

        return f"""
{state.create_base_prompt(self.mode)}

Generate a research plan in JSON with fields:
- "queries": list of search queries
- "reasoning": why these queries and this tool.

Respond in JSON that matches this schema:
{QueryPlan.model_json_schema()}

{persona_task}

If you cannot generate any more queries respond with action: 'stop' otherwise action: 'query'
"""

    async def _execute(
        self,
        agent,
        state: AgentState,
    ) -> StepResult:
        task = (

        )
        prompt = self._base_prompt(state)
        state.update({"role": "user", "content": prompt})
        result = await agent.orchestrator.achat(state.get_llm_messages(), response_model=QueryPlan, tool_names=None)
        raw = result["content"]

        try:
            plan = QueryPlan.model_validate_json(raw)
        except ValidationError:
            plan = QueryPlan(
                queries=[],
                reasoning="Fallback plan due to invalid JSON.",
                action="stop",
            )

        state.update({"role": "assistant", "content": plan.model_dump_json()})
        state.last_output = plan
        return StepResult(output=plan, terminated=plan.action == "stop")
