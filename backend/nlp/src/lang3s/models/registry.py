import os
from typing import Dict, Iterable, Optional

import torch

from lang3s import config

from .heads import TaskHead
from .types import Adapter, TaskType


class AdapterRegistry:
    def __init__(self, hidden_size: int):
        self.hidden_size = hidden_size
        self.device = config.DEVICE
        self.registry: Dict[str, Adapter] = {}

    def register_task(
        self,
        task_name: str,
        label2id: Dict[str, int],
        annotation_type: str,
        task_type: TaskType,
        language: Optional[str] = None,
    ) -> Adapter:
        adapter = Adapter(
            label2id=label2id,
            task_type=task_type,
            task_name=task_name,
            annotation_type=annotation_type,
            language=language,
        )
        self.registry[task_name] = adapter
        return adapter

    def list_tasks(
        self,
        language: Optional[str] = None,
        tasks: Optional[Iterable[str]] = None,
    ):
        if language is None and tasks is None:
            return list(self.registry.keys())

        task_set = None
        if tasks is None:
            task_set = set(self.registry.keys())
        else:
            task_set = set(tasks)

        if len(task_set) == 0:
            return []

        tasks = []

        for task_name, task_def in self.registry.items():
            in_task_set = task_name in task_set
            is_lang_match = (
                language is None
                or task_def.language is None
                or language.lower() == task_def.language.lower()
            )

            if in_task_set and is_lang_match:
                tasks.append(task_name)

        return tasks

    def load_task(self, task_name):
        task = self.registry[task_name]

        if task.head is not None:
            return task

        path = os.path.join(
            config.ADAPTERS_DIR,
            task_name,
        )
        if not os.path.exists(path):
            raise ValueError(f"{path} does not exist")

        head = TaskHead(
            hidden_size=self.hidden_size,
            num_labels=len(task.label2id),
            task_type=task.task_type,
        )
        head.load_state_dict(
            torch.load(f"{path}/{task_name}_head.pt", map_location=self.device)
        )
        head.to(self.device)
        head.eval()
        task.head = head
        return task

    def unload_task(self, task_name):
        task = self.registry[task_name]
        task.head = None
