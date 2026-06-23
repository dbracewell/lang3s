import itertools
import json
from collections import defaultdict
from typing import Dict, Iterable, NamedTuple, Optional

import torch
import torch.nn as nn

from lang3s.core import config
from lang3s.core.typing_extras import SingletonMeta
from lang3s.nlp.components.embedder import EmbeddingResult
from .task import Task
from .task_registry import TaskRegistry
from .typedefs import TaskType, TransformerResult


class TransformerOutput(NamedTuple):
    annotation_type: str
    task_type: TaskType
    labels: TransformerResult


class MultiTaskTransformer(nn.Module, metaclass=SingletonMeta):
    def __init__(self):
        super().__init__()
        self.registry = TaskRegistry()
        self.device = config.INFERENCE_DEVICE
        self.pad_label = "O"
        if config.ADAPTERS_DIR.exists():
            for adapter_dir in config.ADAPTERS_DIR.iterdir():
                if adapter_dir.is_file():
                    continue

                config_file = adapter_dir / f"{adapter_dir.name}.config.json"
                if not config_file.exists():
                    continue
                with open(config_file) as fp:
                    task = Task.model_validate(json.load(fp))
                    self.registry.register_task(task)

    def forward(
        self,
        embedding: EmbeddingResult,
        tasks: Optional[Iterable[str]] = None,
        language: Optional[str] = None,
    ) -> Dict[str, TransformerOutput]:
        outputs = defaultdict(list)

        if tasks is not None and len(set(tasks)) == 0:
            return {}

        batch_size = config.INFERENCE_BATCH_SIZE
        for idx in range(0, len(embedding.mapping), batch_size):
            batch = embedding.batch(idx, idx + batch_size)
            hidden, rm = batch.padded_token_embeddings_with_mask()

            padded_token_embeddings = (
                torch.from_numpy(hidden).type(torch.float32).to(self.device)
            )
            padded_token_mask = torch.from_numpy(rm).type(torch.bool).to(self.device)

            sentence_embeddings = torch.stack(
                [
                    torch.tensor(e, dtype=torch.float32)
                    for e in batch.sentence_embeddings
                ],
                dim=0,
            ).to(self.device)

            for task_name in self.registry.list_tasks(
                language=language,
                task_filter=tasks,
            ):
                with torch.inference_mode():
                    task = self.registry.load_task(task_name)

                    if task.head is None:
                        continue

                    task.head.to(self.device)

                    device_embeddings = sentence_embeddings
                    device_mask = None
                    if task.input_type == "token":
                        device_embeddings = padded_token_embeddings
                        device_mask = padded_token_mask.bool()

                    task.head.eval()
                    output = task.head(
                        hidden=device_embeddings,
                        mask=device_mask,
                        return_logits=True,
                    )
                    labels = task.to_labels(output, device_mask, batch)
                    outputs[task_name].append(
                        TransformerOutput(
                            annotation_type=task.annotation_type,
                            task_type=task.type,
                            labels=labels,
                        )
                    )

            del batch

        final_outputs = {}
        for task_name, output in outputs.items():
            final_outputs[task_name] = TransformerOutput(
                annotation_type=output[0].annotation_type,
                task_type=output[0].task_type,
                labels=list(itertools.chain.from_iterable(o.labels for o in output)),
            )
        return final_outputs
