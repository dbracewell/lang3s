import re
from typing import Any


def clean_thinking(output: Any) -> Any:
    if isinstance(output, str):
        return re.sub(r"<think>.*?</think>", "", output, flags=re.DOTALL).strip()
    return output
