from typing import List, Optional, Callable, Any
import json
from pydantic import BaseModel
import asyncio
from functools import partial
from lang3s.agent.shared_types import StepResult, AgentStep


class ToolStep(AgentStep):
    """
    A production-grade tool-calling step with:
        - Planner-based tool selection
        - Strong tool-calling instructions
        - Schema guidance
        - Argument validation
        - LLM self-correction using error messages
        - Multiple retry attempts
        - Sync + async tool execution
    """

    def __init__(
        self,
        max_retries: int = 3,
        helper_instructions: Optional[str] = None
    ):
        self.max_retries = max_retries
        self.helper_instructions = helper_instructions

    # ---------------------------------------------------------------------
    # Helper to build strong tool-calling prompt
    # ---------------------------------------------------------------------
    def _build_instruction(
        self,
        tool_name: str,
        tool_schema: dict,
        error: Optional[str] = None
    ) -> str:

        schema_text = json.dumps(tool_schema, indent=2)

        base = [
            f"You MUST call the tool `{tool_name}` next.",
            "Do NOT answer in natural language.",
            "Return ONLY a tool call with valid JSON arguments.",
            "The tool schema is:",
            schema_text,
        ]

        if self.helper_instructions:
            base.append(self.helper_instructions)

        if error:
            base.append(f"The last attempt had an error: {error}")
            base.append("Fix the arguments and try again.")

        return "\n".join(base)

    # ---------------------------------------------------------------------
    # SYNC VERSION
    # ---------------------------------------------------------------------
    def run(self, agent, state, user_message):
        plan_raw = state[-1]["content"]

        # Parse planner JSON
        try:
            plan = json.loads(plan_raw)
        except:
            return StepResult(messages=state, output=None)

        if plan.get("action") != "use_tool":
            return StepResult(messages=state, output=None)

        tool_name = plan["tool"]
        tool = agent.orchestrator.registry.get(tool_name)
        schema = tool.args_model.model_json_schema()

        for attempt in range(self.max_retries):
            # 1. Strong tool-call instruction
            instr = self._build_instruction(
                tool_name=tool_name,
                tool_schema=schema,
                error=None if attempt == 0 else "Retrying due to invalid args"
            )
            state.append({"role": "user", "content": instr})

            # 2. Ask LLM for tool call
            result = agent.orchestrator.chat(
                state,
                tool_names=[tool_name],
                response_model=None,
                force_tool_call=True
            )

            msg = result["assistant_message"]
            tool_calls = msg.tool_calls

            # if no tool calls → retry
            if not tool_calls:
                state.append({
                    "role": "assistant",
                    "content": "Model did not call tool. Trying again."
                })
                continue

            call = tool_calls[0]

            # 3. Validate arguments with Pydantic
            try:
                raw_args = json.loads(call.function.arguments or "{}")
                args_obj = tool.args_model.model_validate(raw_args)
            except Exception as e:
                # Send validation error back for self-healing
                err_text = f"Invalid arguments: {str(e)}"
                instr = self._build_instruction(tool_name, schema, error=err_text)
                state.append({"role": "user", "content": instr})
                continue  # retry

            # 4. Execute tool
            try:
                result_obj = tool.func(**args_obj.model_dump())
                if isinstance(result_obj, BaseModel):
                    result_obj = result_obj.model_dump()
            except Exception as e:
                result_obj = {"error": str(e)}

            # 5. Append tool result
            state.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result_obj)
            })

            return StepResult(messages=state, output=result_obj)

        # Hard fail
        state.append({"role": "assistant", "content": "Failed to call tool after retries."})
        return StepResult(messages=state, output=None)

    # ---------------------------------------------------------------------
    # ASYNC VERSION
    # ---------------------------------------------------------------------
    async def async_run(self, agent, state, user_message):
        plan_raw = state[-1]["content"]

        try:
            plan = json.loads(plan_raw)
        except:
            return StepResult(messages=state, output=None)

        if plan.get("action") != "use_tool":
            return StepResult(messages=state, output=None)

        tool_name = plan["tool"]
        tool = agent.orchestrator.registry.get(tool_name)
        schema = tool.args_model.model_json_schema()

        for attempt in range(self.max_retries):
            instr = self._build_instruction(
                tool_name,
                tool_schema=schema,
                error=None if attempt == 0 else "Retrying with corrections"
            )

            state.append({"role": "user", "content": instr})

            result = await agent.orchestrator.achat(
                state,
                tool_names=[tool_name],
                response_model=None,
                force_tool_call=True
            )

            msg = result["assistant_message"]
            tool_calls = msg.tool_calls

            if not tool_calls:
                state.append({"role": "assistant", "content": "No tool call. Retrying."})
                continue

            call = tool_calls[0]

            # Validate arguments
            try:
                raw_args = json.loads(call.function.arguments or "{}")
                args_obj = tool.args_model.model_validate(raw_args)
            except Exception as e:
                err_txt = f"Invalid tool arguments: {e}"
                instr = self._build_instruction(tool_name, schema, error=err_txt)
                state.append({"role": "user", "content": instr})
                continue

            # Execute tool
            try:
                if tool.is_async:
                    result_obj = await tool.func(**args_obj.model_dump())
                else:
                    loop = asyncio.get_running_loop()
                    bound = partial(tool.func, **args_obj.model_dump())
                    result_obj = await loop.run_in_executor(None, bound)  # type: ignore

                if isinstance(result_obj, BaseModel):
                    result_obj = result_obj.model_dump()

            except Exception as e:
                result_obj = {"error": str(e)}

            # Append result
            state.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result_obj)
            })

            return StepResult(messages=state, output=result_obj)

        state.append({"role": "assistant", "content": "Tool call failed after retries."})
        return StepResult(messages=state, output=None)


class ToolLoopStep(AgentStep):
    """
    A ReAct-style multi-step loop that:
        - Replans each iteration
        - Forces tool calling
        - Provides schema guidance
        - Validates arguments with Pydantic
        - Self-corrects tool call arguments
        - Allows multiple global iterations
        - Handles sync and async tools
    """

    def __init__(
        self,
        available_tools: List[str],
        max_loops: int = 5,
        max_tool_retries: int = 3,
        helper_instructions: Optional[str] = None,
        stop_signal: Optional[Callable[[Any], bool]] = None
    ):
        self.available_tools = available_tools
        self.max_loops = max_loops
        self.max_tool_retries = max_tool_retries
        self.helper_instructions = helper_instructions
        self.stop_signal = stop_signal

    # ---------------------------------------------------------
    # Helper to build strong forcing prompt
    # ---------------------------------------------------------
    def _tool_instruction(self, tool_name: str, schema: dict, error: Optional[str] = None) -> str:
        parts = [
            f"You MUST call the `{tool_name}` tool now.",
            "Do NOT answer in natural language.",
            "Return ONLY a tool call with valid JSON arguments.",
            "Here is the schema:",
            json.dumps(schema, indent=2),
        ]
        if self.helper_instructions:
            parts.append(self.helper_instructions)
        if error:
            parts.append(f"Fix this error and try again: {error}")
        return "\n".join(parts)

    # ---------------------------------------------------------
    # SYNC
    # ---------------------------------------------------------
    def run(self, agent, state, user_message):
        for loop_idx in range(self.max_loops):
            # 1. Replan each iteration
            plan_prompt = {
                "role": "user",
                "content": (
                    f"Re-examine the conversation. Available tools: {self.available_tools}. "
                    f"Decide the next action. Respond in JSON: "
                    '{"action": "...", "tool": "...", "reasoning": "..."}'
                )
            }
            state.append(plan_prompt)

            plan_result = agent.orchestrator.chat(
                state,
                response_model=None,
                tool_names=None
            )
            content = plan_result["content"]

            # Append planner output
            state.append({"role": "assistant", "content": content})

            # Parse JSON plan
            try:
                plan = json.loads(content)
            except Exception:
                state.append({"role": "assistant", "content": "Invalid plan JSON, stopping."})
                return StepResult(messages=state, output=None)

            action = plan.get("action")

            if action != "use_tool":
                # If stop or something else -> exit loop
                if self.stop_signal and self.stop_signal(plan):
                    return StepResult(messages=state, output=plan, terminated=True)
                return StepResult(messages=state, output=plan)

            tool_name = plan.get("tool")
            if tool_name not in self.available_tools:
                state.append({"role": "assistant", "content": f"Invalid tool: {tool_name}. Stopping."})
                return StepResult(messages=state, output=None)

            tool = agent.orchestrator.registry.get(tool_name)
            schema = tool.args_model.model_json_schema()

            # ---------------------------------------------------------
            # Tool call + robust retries
            # ---------------------------------------------------------
            for attempt in range(self.max_tool_retries):
                instr = self._tool_instruction(tool_name, schema)
                state.append({"role": "user", "content": instr})

                # Ask model to produce tool call
                result = agent.orchestrator.chat(
                    state,
                    tool_names=[tool_name],
                    force_tool_call=True
                )
                msg = result["assistant_message"]
                tool_calls = msg.tool_calls

                if not tool_calls:
                    state.append({"role": "assistant", "content": "Model did not call tool. Retrying."})
                    continue

                call = tool_calls[0]

                # Validate arguments
                try:
                    raw_args = json.loads(call.function.arguments or "{}")
                    args_obj = tool.args_model.model_validate(raw_args)
                except Exception as e:
                    err_text = f"Invalid tool arguments: {e}"
                    state.append({"role": "assistant", "content": err_text})
                    # Ask model to fix arguments
                    state.append({
                        "role": "user",
                        "content": self._tool_instruction(tool_name, schema, error=err_text)
                    })
                    continue

                # Execute tool
                try:
                    result_obj = tool.func(**args_obj.model_dump())
                    if isinstance(result_obj, BaseModel):
                        result_obj = result_obj.model_dump()
                except Exception as e:
                    result_obj = {"error": str(e)}

                # Append tool result
                state.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result_obj)
                })

                # Break tool retry loop, continue outer loop
                break

        return StepResult(messages=state, output=None, terminated=True)

    # ---------------------------------------------------------
    # ASYNC VERSION
    # ---------------------------------------------------------
    async def async_run(self, agent, state, user_message):
        for loop_idx in range(self.max_loops):
            # Replan
            plan_prompt = {
                "role": "user",
                "content": (
                    f"Re-examine conversation. Available tools: {self.available_tools}. "
                    'Respond in JSON: {"action": "...", "tool": "...", "reasoning": "..."}'
                )
            }
            state.append(plan_prompt)

            plan_result = await agent.orchestrator.achat(
                state,
                response_model=None,
                tool_names=None
            )
            content = plan_result["content"]
            state.append({"role": "assistant", "content": content})

            try:
                plan = json.loads(content)
            except:
                state.append({"role": "assistant", "content": "Invalid plan JSON"})
                return StepResult(messages=state, output=None)

            if plan.get("action") != "use_tool":
                if self.stop_signal and self.stop_signal(plan):
                    return StepResult(messages=state, output=plan, terminated=True)
                return StepResult(messages=state, output=plan)

            tool_name = plan["tool"]
            tool = agent.orchestrator.registry.get(tool_name)
            schema = tool.args_model.model_json_schema()

            for attempt in range(self.max_tool_retries):
                instr = self._tool_instruction(tool_name, schema)
                state.append({"role": "user", "content": instr})

                # Ask model for tool call
                result = await agent.orchestrator.achat(
                    state,
                    tool_names=[tool_name],
                    force_tool_call=True
                )
                msg = result["assistant_message"]
                tool_calls = msg.tool_calls

                if not tool_calls:
                    state.append({"role": "assistant", "content": "No tool call, retrying"})
                    continue

                call = tool_calls[0]

                # Validate args
                try:
                    raw_args = json.loads(call.function.arguments or "{}")
                    args_obj = tool.args_model.model_validate(raw_args)
                except Exception as e:
                    err_txt = f"Invalid arguments: {e}"
                    state.append({"role": "assistant", "content": err_txt})
                    state.append({
                        "role": "user",
                        "content": self._tool_instruction(tool_name, schema, error=err_txt)
                    })
                    continue

                # Execute tool
                try:
                    kwargs = args_obj.model_dump()
                    if tool.is_async:
                        result_obj = await tool.func(**kwargs)
                    else:
                        loop = asyncio.get_running_loop()
                        bound = partial(tool.func, **kwargs)
                        result_obj = await loop.run_in_executor(None, bound)  # type:ignore
                    if isinstance(result_obj, BaseModel):
                        result_obj = result_obj.model_dump()
                except Exception as e:
                    result_obj = {"error": str(e)}

                # Add result
                state.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result_obj)
                })

                break

        return StepResult(messages=state, output=None, terminated=True)
