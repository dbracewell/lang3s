import json
import os
from typing import Dict, Iterable, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn.utils.rnn import pad_sequence

from lang3s import config
from lang3s.utils import decorators

from .embedder import Embedder
from .helpers import decode_predictions
from .registry import AdapterRegistry
from .types import EmbeddingResult, TaskType, TransformerOutput


@decorators.singleton
class MultiTaskTransformer(nn.Module):
    def __init__(self):
        super().__init__()
        self.registry = AdapterRegistry(hidden_size=Embedder().dimensions)
        for adapter_dir in os.listdir(config.ADAPTERS_DIR):
            full_path = os.path.join(config.ADAPTERS_DIR, adapter_dir)
            if os.path.exists(full_path):
                config_file = os.path.join(
                    full_path, f"{adapter_dir}.config.json"
                )
                if os.path.exists(config_file):
                    with open(config_file) as fp:
                        self.registry.register_task(**json.load(fp))
        self.device = config.DEVICE

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

                if task.task_type == TaskType.SENTENCE:
                    logits, _ = task.head(device_embeddings, mask)
                    probs = F.softmax(logits, dim=-1)
                    pred_labels = probs.argmax(dim=-1).cpu().numpy()
                    labels = [task.id2label[i] for i in pred_labels]
                    outputs[task_name] = TransformerOutput(
                        annotation_type=task.annotation_type,
                        task_type=task.task_type,
                        labels=labels,
                    )
                else:
                    pred_sequences = task.head(device_embeddings, mask=mask)
                    decoded = decode_predictions(
                        pred_sequences, embedding, task.id2label
                    )
                    outputs[task_name] = TransformerOutput(
                        annotation_type=task.annotation_type,
                        task_type=task.task_type,
                        labels=decoded,
                    )
        return outputs
