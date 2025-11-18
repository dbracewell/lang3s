import json
import textwrap
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Any

from pydantic import BaseModel


class ModelScale(Enum):
    SMALL = auto()
    MEDIUM = auto()
    LARGE = auto()


@dataclass
class MemoryConfig:
    scale: ModelScale

    # Max messages to keep in raw state after pruning
    max_messages_small: int = 8
    max_messages_medium: int = 16
    max_messages_large: int = 32

    # How many recent messages to feed into the compiled summary
    summary_window_small: int = 6
    summary_window_medium: int = 12
    summary_window_large: int = 24

    truncation_size_small: int = 100
    truncation_size_medium: int = 400
    truncation_size_large: int = 800

    # Rough character budget for compiled summary (for dynamic tightening)
    target_summary_chars: int = 4000

    def truncation_size(self) -> int:
        if self.scale == ModelScale.SMALL:
            return self.truncation_size_small
        if self.scale == ModelScale.MEDIUM:
            return self.truncation_size_medium
        return self.truncation_size_large

    def max_messages(self) -> int:
        if self.scale == ModelScale.SMALL:
            return self.max_messages_small
        if self.scale == ModelScale.MEDIUM:
            return self.max_messages_medium
        return self.max_messages_large

    def summary_window(self) -> int:
        if self.scale == ModelScale.SMALL:
            return self.summary_window_small
        if self.scale == ModelScale.MEDIUM:
            return self.summary_window_medium
        return self.summary_window_large


class UnifiedMemory:
    """
    Unified memory layer that:
    - Summarizes recent context into a compact "compiled context"
    - Prunes the raw state based on model scale
    - Works for both small and large models with different thresholds
    """

    def __init__(self, config: MemoryConfig):
        self.config = config

    # ---------- summarization helpers ----------

    def _summarize_recent_messages(self, messages: List[dict]) -> str:
        """
        Summarize the last N messages (N depends on model scale).
        Keeps it short for small models, richer for large ones.
        """
        window = self.config.summary_window()
        clipped = messages[-window:]
        parts = []

        for msg in clipped:
            role = msg.get("role", "unknown")
            content = (msg.get("content") or "").strip()
            # content = content[:self.config.truncation_size()]
            parts.append(f"- {role}: {content}")

        return "\n".join(parts)

    def _truncate_to_budget(self, text: str) -> str:
        """
        Enforce a rough character budget on compiled summary.
        Useful for small/medium models or when context grows.
        """
        budget = self.config.target_summary_chars
        if len(text) <= budget:
            return text
        # Truncate from the top (oldest info) if it overshoots
        overflow = len(text) - budget
        return text[overflow:]

    # ---------- public API: compile & prune ----------

    def compile(
        self,
        messages: List[dict],
        last_plan: Optional[BaseModel],
        last_output: Optional[Any],
        user_goal: Optional[str] = None,
        persona_text: Optional[str] = None,
    ) -> str:
        """
        Builds a compressed context summary, tuned for the configured model scale.
        This is what you feed into planning / analysis / summarization steps.
        """
        recent_summary = self._summarize_recent_messages(messages)
        last_output_str = None
        if last_output is not None:
            if isinstance(last_output, BaseModel):
                last_output_str = last_output.model_dump_json()
            elif not isinstance(last_output, str):
                last_output_str = json.dumps(last_output, indent=2)
            else:
                last_output_str = last_output

        base = f"""
            ### TASK CONTEXT SUMMARY
            User goal:
            {user_goal or "Unknown"}

            Recent conversation:
            {recent_summary or "No recent messages."}

        """

        if persona_text:
            base += f"""
            Persona:
            {persona_text}
            
            """

        if last_plan:
            base += f"""
            Last plan:
            {json.dumps(last_plan.model_dump(), indent=2) if last_plan else "None"}

            """

        if last_output:
            base += f"""
            Last output:
            {last_output_str if last_output is not None else "None"}

            """

        base += f"""
            ### END SUMMARY
            """.strip()

        base = textwrap.dedent(base)

        return self._truncate_to_budget(base)

    def prune_state(self, messages: List[dict]) -> List[dict]:
        """
        Prunes raw conversation state based on model scale.

        - For SMALL models: keep very few messages (last N).
        - For LARGE models: keep a bit more, but still avoid unbounded growth.
        """
        max_len = self.config.max_messages()
        if len(messages) <= max_len:
            return messages

        messages = [m for m in messages if _is_good_message(m)]

        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        system_keep = system_msgs[-2:]

        remaining_slots = max_len - len(system_keep)
        non_system_keep = non_system[-max(remaining_slots, 0):]

        pruned = system_keep + non_system_keep
        return pruned


def _is_good_message(msg: dict) -> bool:
    if msg.get("status", "success") == "failed":
        return False
    if msg.get("content", None) is None:
        return False
    return True
