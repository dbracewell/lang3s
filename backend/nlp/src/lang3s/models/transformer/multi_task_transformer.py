import itertools
import json
import os
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, NamedTuple, cast

import torch
import torch.nn as nn

from lang3s import config
from lang3s.models.embedder import EmbeddingResult
from lang3s.utils import decorators
from .shared_types import TaskType, TransformerResult
from .task import SentenceClassificationParams, Task
from .task_registry import TaskRegistry


class TransformerOutput(NamedTuple):
    annotation_type: str
    task_type: TaskType
    labels: TransformerResult


@decorators.singleton
class MultiTaskTransformer(nn.Module):
    def __init__(self):
        super().__init__()
        self.registry = TaskRegistry(hidden_size=config.TOKEN_EMBEDDING_DIMENSION)
        self.device = config.INFERENCE_DEVICE
        self.pad_label = 'O'
        if os.path.exists(config.ADAPTERS_DIR):
            for adapter_dir in os.listdir(config.ADAPTERS_DIR):
                full_path = os.path.join(config.ADAPTERS_DIR, adapter_dir)
                if os.path.exists(full_path):
                    config_file = os.path.join(
                        full_path, f"{adapter_dir}.config.json"
                    )
                    if os.path.exists(config_file):
                        with open(config_file) as fp:
                            task = Task.from_dict(json.load(fp))
                            self.registry.register_task(task)

    def forward(
        self,
        embedding: EmbeddingResult,
        sentences: List[List[str]],
        tasks: Optional[Iterable[str]] = None,
        language: Optional[str] = None,
    ) -> Dict[str, TransformerOutput]:
        outputs = defaultdict(list)
        batch_size = config.INFERENCE_BATCH_SIZE
        for idx in range(0, len(embedding.mapping), batch_size):
            batch = embedding.batch(idx, idx + batch_size)
            # batch_sentences = sentences[idx:idx + batch_size]

            hidden, rm = batch.padded_token_embeddings_with_mask()
            padded_token_embeddings = torch.from_numpy(hidden).type(torch.float32).to(self.device)
            padded_token_mask = torch.from_numpy(rm).type(torch.bool).to(self.device)

            # word_to_subword = []
            # word_ids_list = [m.word_ids for m in batch.mapping]
            # for word_ids, tokens in zip(word_ids_list, batch_sentences):
            #     mapping = []
            #     for word_idx in range(len(tokens)):
            #         sub_positions = [i for i, w in enumerate(word_ids) if w == word_idx]
            #         if len(sub_positions) == 0:
            #             mapping.append(None)  # rare, but safe fallback
            #         else:
            #             mapping.append(sub_positions[0])  # FIRST subword
            #     word_to_subword.append(mapping)

            sentence_embeddings = torch.stack(
                [torch.tensor(e, dtype=torch.float32) for e in batch.sentence_embeddings],
                dim=0,
            ).to(self.device)

            for task_name in self.registry.list_tasks(
                language=language, tasks=tasks
            ):
                with torch.inference_mode():
                    task = self.registry.load_task(task_name)

                    if task.head is None:
                        continue

                    task.head.to(self.device)
                    device_embeddings = sentence_embeddings
                    device_mask = None

                    if task.type.is_token() or cast(SentenceClassificationParams, task.params).num_attention_heads > 0:
                        device_embeddings = padded_token_embeddings
                        device_mask = padded_token_mask.bool()

                    task.head.eval()
                    output = task.head(hidden=device_embeddings, mask=device_mask, return_logits=True)
                    labels = task.to_labels(output, device_mask, batch)
                    outputs[task_name].append(TransformerOutput(
                        annotation_type=task.annotation_type,
                        task_type=task.type,
                        labels=labels
                    ))

        final_outputs = {}
        for task_name, output in outputs.items():
            final_outputs[task_name] = TransformerOutput(
                annotation_type=output[0].annotation_type,
                task_type=output[0].task_type,
                labels=list(itertools.chain.from_iterable(o.labels for o in output)),
            )
        return final_outputs
