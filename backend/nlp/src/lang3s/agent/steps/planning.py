import logging
from typing import List, Literal, Optional

from lang3s.agent.shared_types import StepResult, AgentStep
from lang3s.agent.persona import PersonaAwareStep, PersonaMode, Persona
from pydantic import ValidationError, BaseModel

logger = logging.getLogger(__name__)


class QueryPlan(BaseModel):
    queries: List[str]
    reasoning: str
    action: Literal["query", "stop"]


class Plan(BaseModel):
    action: Literal[
        "use_tool", "retrieve", "summarize", "stop", "reflect", "analyze", "generate_examples", "categorize"]
    tool: Optional[str] = None
    target_category: Optional[str] = None
    reasoning: str


class PlanStep(PersonaAwareStep):

    def __init__(self,
                 available_tools: Optional[List[str]] = None,
                 history: int = 100):
        super().__init__(PersonaMode.PLANNING)
        self.available_tools = available_tools or []
        self.history = history

    def _prompt(self, user_message: str) -> str:
        return f"""
        Examine the conversation so far and user input: "{user_message}"

        Your task is to decide the next action.

        Available tools: {", ".join(self.available_tools)}

        You must decide the next action. 
        Always choose the action that advances toward a final answer.

        Available Actions:
        1. "use_tool"
           Use a registered tool to gather external information. 
           Use this when:
           - You need factual data not present in memory.
           - You need search results, documents, or structured data.
           Output must include: {{"action": "use_tool", "tool": "<tool_name>", ...}}
        
        2. "retrieve"
           Retrieve new data from an internal retrieval system (vector search, lexical search, etc.).
           Use this when:
           - You already have example sentences, queries, keywords, or context.
           - You need to find real sentences or documents from the corpus.
           Typical use after "generate_examples".
           Output: {{"action": "retrieve"}}
        
        3. "summarize"
           Summarize current information into a concise, user-ready answer.
           Use this only when:
           - You have sufficient information to present a coherent summary.
           - No additional tools, retrieval, or analysis is required.
           Produces a summary and should usually be followed by "stop".
        
        4. "reflect"
           Think step-by-step about the information gathered so far.
           Use this when:
           - You need to evaluate the quality of the plan or evidence.
           - You need to check whether another action (retrieve, use_tool, analyze) is needed.
           Must never repeat endlessly. 
           Do not choose "reflect" more than once without new information.
        
        5. "analyze"
           Analyze previously retrieved or generated content to extract insights or structure.
           Use this when:
           - You need to understand examples or retrieved results.
           - You must prepare information for categorization or summarization.
           Should not be repeated if no new data was retrieved.
        
        6. "generate_examples"
           Generate example sentences or synthetic samples for a target category.
           Use this when:
           - The task requires generating category-specific examples.
           - No real data is yet retrieved.
           Output must include the target category.
        
        7. "categorize"
           Categorize retrieved sentences into either:
           - The target category
           - Another known category (if applicable)
           - "None" (if unrelated)
           Use this when:
           - Real sentences from "retrieve" or "use_tool" are available.
           - The task requires classification.
           Output: {{"action": "categorize", "target_category": "<category>"}}
        
        8. "stop"
           Finish processing and produce the final output.
           Choose this when:
           - The task is complete.
           - A summary has been generated.
           - Categorization is complete.
           - No further retrieval, analysis, or tool use is necessary.
           - Reflecting would add no value.
        
        ------------------------------
        
        Action Selection Rules:
        
        - Always choose the next action that most directly advances the task.
        - Use "reflect" only once between operations.
        - Avoid repeating the same action more than twice (especially analyze/reflect/summarize).
        - If the last step was "summarize", you MUST choose "stop".
        - If categorization is complete, choose "stop".
        - If retrieval produced no new data, DO NOT call retrieve again—choose "summarize" or "stop".
        - If examples have not yet been generated but retrieval is needed, choose "generate_examples".
        - If the task is unclear or insufficiently supported by data, choose "use_tool" or "retrieve" instead of "summarize".
        - Choose "stop" as soon as a finished answer is available.
        
        Action Requirements:
        - If action = "generate_examples":
            - You MUST set "target_category" to the category from the user request or previous context.
            - "target_category" MUST NOT be null.
            - Never leave "target_category" undefined.
        
        - If action = "categorize":
            - You MUST include the correct target category.
            - "target_category" MUST NOT be null.
        
        - If the user explicitly mentions a category (e.g. "Sports Injury"), 
          you MUST repeat that category in "target_category".
        
        - Never output a plan where the reasoning mentions a category 
          but "target_category" is null.
                    
        Output Format:
        {{
            "action": "<one of the above>",
            "target_category": "<optional>" or null,
            "tool": "<optional>" or null,
            "reasoning": "Explain why this action is the best next step."
        }}

        Make sure to use all previous messages and actions including your previous reflections, analysis, and summaries when making your choice.
        """

    def run_no_persona(self, agent, state: List[dict], user_message: str) -> StepResult:
        state.append({"role": "user", "content": self._prompt(user_message)})
        result = agent.orchestrator.chat(
            state,
            response_model=Plan,
            tool_names=None
        )
        plan = result["content"]
        parsed = Plan.model_validate_json(plan)
        state.append({"role": "assistant", "content": plan})
        logger.debug(f"PlanState: Generated plan='{plan}'")
        return StepResult(messages=state, output=parsed, terminated=parsed.action == "stop")

    def run_with_persona(
        self,
        agent,
        state: List[dict],
        user_message: str,
        persona: Persona,
        mode: PersonaMode,
    ) -> StepResult:
        prompt = self.build_persona_prompt(persona, mode, self._prompt(user_message), user_message,
                                           history=self.history)
        state.append({"role": "user", "content": prompt})
        result = agent.orchestrator.chat(
            state,
            response_model=Plan,
            tool_names=None
        )

        plan = result["content"]
        parsed = Plan.model_validate_json(plan)
        state.append({"role": "assistant", "content": plan})
        logger.debug(f"PlanState: Generated plan='{plan}'")
        return StepResult(messages=state, output=parsed, terminated=parsed.action == "stop")


class QueryPlanner(PersonaAwareStep):
    """
    Produce a research plan compatible with your ToolStep/RobustToolLoopStep:

    {
      "queries": [...],
      "reasoning": "..."
    }

    - Without persona: neutral query planning.
    - With persona (QUERY_PLANNING): queries framed through worldview.
    """

    persona_modes = [PersonaMode.QUERY_PLANNING]

    def _base_prompt(self, user_message: str) -> str:
        return f"""
The user is asking:

{user_message}

Generate a research plan in JSON with fields:
- "queries": list of search queries
- "reasoning": why these queries and this tool.

Respond in JSON that matches this schema:
{QueryPlan.model_json_schema()}

If you cannot generate any more queries respond with action: 'stop' otherwise action: 'query'
"""

    def run_no_persona(self, agent, state: List[dict], user_message: str) -> StepResult:
        prompt = self._base_prompt(user_message)
        state.append({"role": "user", "content": prompt})
        result = agent.orchestrator.chat(state)
        raw = result["content"]

        try:
            plan = QueryPlan.model_validate_json(raw)
        except ValidationError:
            plan = QueryPlan(
                queries=[user_message],
                reasoning="Fallback plan due to invalid JSON.",
                action="stop",
            )

        state.append({"role": "assistant", "content": plan.model_dump_json()})
        return StepResult(messages=state, output=plan, terminated=plan.action == "stop")

    def run_with_persona(
        self,
        agent,
        state: List[dict],
        user_message: str,
        persona: Persona,
        mode: PersonaMode,
    ) -> StepResult:
        task = (
            "Generate a JSON research plan for querying documents, reflecting this persona's focus. "
            "You must still respect the required JSON schema."
        )
        base_prompt = self._base_prompt(user_message)
        prompt = self.build_persona_prompt(persona, mode, task, base_prompt)
        state.append({"role": "user", "content": prompt})
        result = agent.orchestrator.chat(state, response_model=QueryPlan)
        raw = result["content"]

        try:
            plan = QueryPlan.model_validate_json(raw)
        except ValidationError:
            plan = QueryPlan(
                queries=[user_message],
                reasoning="Fallback persona plan due to invalid JSON.",
                action="stop",
            )

        state.append({"role": "assistant", "content": plan.model_dump_json()})
        return StepResult(messages=state, output=plan, terminated=plan.action == "stop")
