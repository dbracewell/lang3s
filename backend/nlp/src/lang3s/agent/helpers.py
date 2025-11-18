import json
import logging
import re
import textwrap
from typing import Any, Optional

from pydantic.main import BaseModel

from .shared_types import Plan, StepResult


def clean_thinking(output: Any) -> Any:
    if isinstance(output, str):
        return re.sub(r"<think>.*?</think>", "", output, flags=re.DOTALL).strip()
    return output


def log_step_result(name: str, result: StepResult):
    logger = logging.getLogger(f"lang3s.agent.{name}")
    if logger.isEnabledFor(logging.DEBUG):
        output = result.output
        if isinstance(output, Plan):
            output = f"{{action={output.action}, reason={output.reasoning}}}"
        if isinstance(output, BaseModel):
            output = output.model_dump_json()
        elif not isinstance(output, str):
            output = json.dumps(output)
        output = textwrap.shorten(output, width=200)
        logger.debug(
            f"success={result.success}, terminated={result.terminated}, output={output}")


_PLAN_TRANSITIONS = {
    None: ["use_tool", "retrieve", "summarize", "stop", "reflect", "analyze", "generate_examples", "categorize"],
    "use_tool": ["summarize", "reflect", "analyze", "generate_examples", "categorize", "stop"],
    "retrieve": ["summarize", "reflect", "analyze", "generate_examples", "categorize", "use_tool"],
    "summarize": ["stop"],
    "stop": [],
    "reflect": ["use_tool", "retrieve", "generate_examples", "categorize", "summarize"],
    "analyze": ["use_tool", "retrieve", "generate_examples", "categorize", "summarize"],
    "generate_examples": ["use_tool", "generate_examples", "retrieve", "categorize"],
    "categorize": ["stop"],
}


def get_valid_next_actions(last_plan: Optional[Plan]) -> str:
    if last_plan is None:
        return "Please select one of the following actions: " + ", ".join(_PLAN_TRANSITIONS[None])
    last_action = last_plan.action
    if last_action == "stop":
        return ""
    if last_action in _PLAN_TRANSITIONS:
        return "Please select one of the following actions: " + ", ".join(_PLAN_TRANSITIONS[None])
    return "You are in an invalid state."


def is_valid_plan_transition(from_state: str, to_state: str) -> bool:
    if from_state not in _PLAN_TRANSITIONS:
        return False
    if to_state not in _PLAN_TRANSITIONS[from_state]:
        return False
    return True
