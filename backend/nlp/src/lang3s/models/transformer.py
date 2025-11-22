import json
import os
from typing import Dict, Iterable, Optional

import torch
import torch.nn as nn
from torch.nn.utils.rnn import pad_sequence

from lang3s import config
from lang3s.utils import decorators
from .embedder import Embedder
from .shared_types import EmbeddingResult, TransformerOutput
from .task_registry import Task, TaskRegistry


@decorators.singleton
class MultiTaskTransformer(nn.Module):
    def __init__(self):
        super().__init__()
        self.registry = TaskRegistry(hidden_size=Embedder().dimensions)
        self.device = config.DEVICE
        if os.path.exists(config.ADAPTERS_DIR):
            for adapter_dir in os.listdir(config.ADAPTERS_DIR):
                full_path = os.path.join(config.ADAPTERS_DIR, adapter_dir)
                if os.path.exists(full_path):
                    config_file = os.path.join(
                        full_path, f"{adapter_dir}.config.json"
                    )
                    if os.path.exists(config_file):
                        with open(config_file) as fp:
                            task = Task(**json.load(fp))
                            self.registry.register_task(task)

    def forward(
        self,
        embedding: EmbeddingResult,
        tasks: Optional[Iterable[str]] = None,
        language: Optional[str] = None,
    ) -> Dict[str, TransformerOutput]:
        outputs = dict()
        device_embeddings = pad_sequence(
            [torch.Tensor(e) for e in embedding.token_embeddings],
            batch_first=True,
            padding_value=0,
        ).to(self.device)
        mask = torch.sum(torch.abs(device_embeddings), dim=-1) != 0
        for task_name in self.registry.list_tasks(
            language=language, tasks=tasks
        ):
            with torch.inference_mode():
                task = self.registry.load_task(task_name)
                if task.head is None:
                    continue
                outputs[task_name] = TransformerOutput(
                    annotation_type=task.annotation_type,
                    task_type=task.type,
                    labels=task.to_labels(head_output=task.head(device_embeddings, mask, return_logits=True),
                                          embedding=embedding),
                )
        return outputs
