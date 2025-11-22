import asyncio
import json
from functools import partial
from typing import Any, List, Optional, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from lang3s.agent import Agent

from pydantic import BaseModel

from lang3s.agent.shared_types import AgentState, StepResult, AgentStep
from lang3s.models.llm import RegisteredTool


def instruction_builder(
    tool_name: str,
    tool_schema: dict,
    error: Optional[str] = None,
) -> str:
    msg = f"""
You must generate VALID arguments for the tool "{tool_name}" using the schema below.

TOOL ARGUMENT SCHEMA:
{json.dumps(tool_schema, indent=2)}

REQUIREMENTS:
- Output MUST be ONLY a JSON object (no text before or after).
- The JSON MUST match the "properties" and "required" fields in the schema exactly.
- DO NOT include fields not listed in the schema.
- Use correct data types for each field.
- DO NOT call the tool; only return the argument object.
- DO NOT rename fields.
- DO NOT include comments or explanations.
- DO NOT wrap the JSON in backticks.

"""

    if error:
        msg += f"""
ERROR DETECTED:
{error}

Your task:
- FIX the arguments so they comply with the tool schema.
- Return ONLY a corrected JSON object containing the arguments.
"""

    msg += """
Return ONLY the JSON object containing corrected arguments.
NOTHING ELSE.
"""

    return msg.strip()


async def _tool_caller(
    agent: "Agent",
    tool: "RegisteredTool",
    provided_args: Dict[str, Any],
    max_retries: int,
    state: AgentState,
) -> Dict[str, Any]:
    schema = tool.args_model.model_json_schema()
    current_args = provided_args

    for _ in range(1, max_retries + 1):
        try:
            arg_obj = tool.args_model.model_validate(current_args)
        except Exception as validation_error:
            error_text = f"Invalid tool arguments: {str(validation_error)}. Please fix the arguments."
            instr = instruction_builder(
                tool_name=tool.name,
                tool_schema=schema,
                error=error_text
            )

            state.update({"role": "user", "content": instr, "status": "failed"})
            regen = await agent.orchestrator.achat(
                state.get_llm_messages(),
                response_model=None
            )

            try:
                current_args = json.loads(regen["content"])
            except Exception:
                state.update({
                    "role": "assistant",
                    "content": "Invalid argument regeneration. Trying again."
                })
                continue

            continue

        try:
            result = tool.func(**arg_obj.model_dump())
            if isinstance(result, BaseModel):
                result = result.model_dump()

        except Exception as exec_error:
            error_text = f"Tool execution failed: {str(exec_error)}. Try adjusting the arguments."
            instr = instruction_builder(
                tool_name=tool.name,
                tool_schema=schema,
                error=error_text
            )

            state.update({"role": "user", "content": instr, "status": "failed"})
            regen = agent.orchestrator.chat(state.get_llm_messages(), response_model=None)

            try:
                current_args = json.loads(regen["content"])
            except Exception:
                state.update({
                    "role": "assistant",
                    "content": "Invalid regenerated arguments. Trying again.",
                    "status": "failed",
                })
                continue

            continue

        return {
            "role": "tool",
            "name": tool.name,
            "content": json.dumps(result),
            "status": "success",
        }

    return {
        "role": "assistant",
        "content": f"Failed to call tool '{tool.name}' after {max_retries} attempts.",
        "status": "failed",
    }


async def _async_tool_caller(
    agent,
    tool: "RegisteredTool",
    provided_args: Dict[str, Any],
    max_retries: int,
    state: List[dict],
) -> Dict[str, Any]:
    schema = tool.args_model.model_json_schema()

    # We try using planner-provided args first, then fallback to LLM-generated corrections
    current_args = provided_args

    for _ in range(1, max_retries + 1):
        try:
            arg_obj = tool.args_model.model_validate(current_args)
        except Exception as validation_error:
            error_text = f"Invalid tool arguments: {str(validation_error)}. Please fix the arguments."
            instr = instruction_builder(
                tool_name=tool.name,
                tool_schema=schema,
                error=error_text
            )

            state.append({"role": "user", "content": instr})
            regen = agent.orchestrator.chat(
                state,
                response_model=None
            )

            try:
                current_args = json.loads(regen["content"])
            except Exception:
                state.append({
                    "role": "assistant",
                    "content": "Invalid argument regeneration. Trying again."
                })
                continue

            continue

        try:
            if tool.is_async:
                result = await tool.func(**arg_obj.model_dump())
            else:
                loop = asyncio.get_running_loop()
                bound = partial(tool.func, **arg_obj.model_dump())
                result = await loop.run_in_executor(None, bound)  # type: ignore
            if isinstance(result, BaseModel):
                result = result.model_dump()

        except Exception as exec_error:
            error_text = f"Tool execution failed: {str(exec_error)}. Try adjusting the arguments."
            instr = instruction_builder(
                tool_name=tool.name,
                tool_schema=schema,
                error=error_text
            )

            state.append({"role": "user", "content": instr})
            regen = agent.orchestrator.chat(state, response_model=None)

            try:
                current_args = json.loads(regen["content"])
            except Exception:
                state.append({
                    "role": "assistant",
                    "content": "Invalid regenerated arguments. Trying again."
                })
                continue

            continue

        return {
            "role": "tool",
            "name": tool.name,
            "content": json.dumps(result),
            "status": "success",
        }

    return {
        "role": "assistant",
        "content": f"Failed to call tool '{tool.name}' after {max_retries} attempts.",
        "status": "failed",
    }


class ToolStep(AgentStep):

    def __init__(
        self,
        max_retries: int = 3,
        name: str = "ToolStep",
        helper_instructions: Optional[str] = None
    ):
        AgentStep.__init__(self, name=name)
        self.max_retries = max_retries
        self.helper_instructions = helper_instructions

    async def _execute(self, agent: "Agent", state: AgentState):
        plan = state.last_plan
        if plan is None:
            return StepResult(success=False, output=None)
        if plan.action != "use_tool":
            return StepResult(success=False, output=None)
        if plan.tool is None or plan.args is None:
            return StepResult(success=False, output=None)

        response = await _tool_caller(agent=agent,
                                      tool=agent.orchestrator.registry.get(plan.tool),
                                      max_retries=self.max_retries,
                                      state=state,
                                      provided_args=plan.args)

        state.update(response)
        return StepResult(output=response if response["status"] == "success" else None)


class AutoToolStep(AgentStep):

    def __init__(self, max_retries: int, name: str = "AutoToolStep"):
        AgentStep.__init__(self, name)
        self.max_retries = max_retries
        self.tool_step = ToolStep(max_retries=self.max_retries)

    async def _prepare(self, agent, state: AgentState) -> Dict[str, Any] | StepResult:
        available = list(agent.orchestrator.registry.names())

        prompt = f"""
        {state.create_base_prompt()}
        
        Look at the conversation and decide whether calling any of these tools
        would significantly improve the answer:

        Available tools: {available}

        Your task:
        - If tools are needed, produce JSON:
          {{
            "decision": "use_tools",
            "tools": [
               {{ "name": "...", "args": {{...}} }},
               ...
            ]
          }}

        - If NO tools are needed:
          {{
            "decision": "skip",
            "reasoning": "..."
          }}
        """

        state.update({"role": "user", "content": prompt})
        response = await agent.orchestrator.achat(state.get_llm_messages())
        plan_json = response["content"]

        try:
            plan = json.loads(plan_json)
        except json.JSONDecodeError:
            return StepResult(success=False, output=None)

        if plan["decision"] == "skip":
            return StepResult(output=None)

        return plan

    async def _execute(self, agent, state) -> StepResult:
        plan = await self._prepare(agent, state)
        if isinstance(plan, StepResult):
            return plan

        all_results = {}
        for tool_call in plan["tools"]:
            tool_name = tool_call["name"]
            tool = agent.orchestrator.registry.get(tool_name)
            args = tool_call["args"]
            response = await _tool_caller(agent=agent,
                                          tool=tool,
                                          max_retries=self.max_retries,
                                          state=state,
                                          provided_args=args)
            all_results[tool_name] = response["content"]
            state.update(response)

        return StepResult(output=all_results)
