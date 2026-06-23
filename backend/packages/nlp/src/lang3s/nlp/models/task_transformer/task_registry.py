from typing import Dict, Iterable, Optional

from lang3s.core import config
from lang3s.core.typing_extras import SingletonMeta

from .task import Task


class TaskRegistry(metaclass=SingletonMeta):
    def __init__(self):
        self.registry: Dict[str, Task] = {}

    def register_task(self, task: Task) -> Task:
        self.registry[task.name] = task
        return task

    def list_tasks(
        self,
        language: Optional[str] = None,
        task_filter: Optional[Iterable[str]] = None,
    ):
        if language is None and task_filter is None:
            return list(self.registry.keys())

        if task_filter is None:
            task_set = set(self.registry.keys())
        else:
            task_set = set(task_filter)

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

        path = config.ADAPTERS_DIR / task.name
        if not path.exists():
            raise ValueError(f"{path} does not exist")

        task.load_model_head(path=path)  # type:ignore
        return task

    def unload_task(self, task_name):
        task = self.registry[task_name]
        task.head = None
