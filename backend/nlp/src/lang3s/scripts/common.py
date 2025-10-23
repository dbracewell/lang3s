from typing import Dict
import json
import os

from lang3s.config import ADAPTERS_DIR


def load_adapter_config() -> Dict[str, Dict[str, str]]:
    if os.path.exists(os.path.join(ADAPTERS_DIR, "adapters.json")):
        return json.load(open(os.path.join(ADAPTERS_DIR, "adapters.json")))
    return {}


def update_adapter_config(
    name: str,
    task: str,
    language: str,
    annotation_type: str,
) -> None:
    adapter_config = load_adapter_config()
    adapter_config[name] = {
        "language": language,
        "type": annotation_type,
        "task": task,
    }
    save_adapter_config(adapter_config)


def save_adapter_config(adapter_config: Dict[str, Dict[str, str]]) -> None:
    json.dump(
        adapter_config, open(os.path.join(ADAPTERS_DIR, "adapters.json"), "w"), indent=2
    )
