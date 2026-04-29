import os
from typing import Dict, Iterable, Optional

from lang3s import config

from .task import Task


class TaskRegistry:
    def __init__(self, hidden_size: int):
        self.registry: Dict[str, Task] = {}

    def register_task(self, task: Task) -> Task:
        self.registry[task.name] = task
        return task

    def list_tasks(
        self,
        language: Optional[str] = None,
        tasks: Optional[Iterable[str]] = None,
    ):
        if language is None and tasks is None:
            return list(self.registry.keys())

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

        task.load_model_head(path=path)  # type:ignore
        return task

    def unload_task(self, task_name):
        task = self.registry[task_name]
        task.head = None
