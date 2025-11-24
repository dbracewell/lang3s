import os
from typing import Dict, Iterable, Optional, List, Tuple

import torch
import torch.nn as nn
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict
from pydantic.fields import computed_field
from torch.nn.modules.activation import MultiheadAttention

from lang3s import config
from .augmentation.mixup import Mixup
from .layers.adapter import DoRA
from .layers.mlp import MLPClassificationHead
from .loss.focal import FocalLoss
from .shared_types import TaskType, EmbeddingResult


class TaskHead(nn.Module):

    def __init__(self,
                 task_type: TaskType,
                 hidden_size: int,
                 num_labels: int,
                 original_layer: nn.Linear,
                 label_list: List[str],
                 rank: int = 8,
                 alpha: int = 8,
                 dropout=0.2,
                 lstm_hidden: Optional[int] = None,
                 use_mixup: bool = False,
                 weights: Optional[torch.Tensor] = None,
                 use_focal_loss: bool = False,
                 num_attention_heads: int = 0,
                 use_dora: bool = False,
                 ):
        super(TaskHead, self).__init__()
        self.task_type = task_type
        self.num_attention_heads: int = num_attention_heads
        self.use_dora = use_dora
        self.mixup = None
        self.attention_layer = None
        self.dora_adapter = None

        if self.task_type.is_sentence_level():
            if self.use_dora and original_layer is not None:
                self.dora_adapter = DoRA(original_layer=original_layer, rank=rank, alpha=alpha)

            if self.num_attention_heads > 0:
                self.attention_layer = MultiheadAttention(hidden_size,
                                                          num_heads=num_attention_heads,
                                                          batch_first=True)

            loss_type = "multiclass" if self.task_type == TaskType.SENTENCE else "multilabel"
            if use_focal_loss:
                loss_function = FocalLoss(alpha=weights,
                                          loss_type=loss_type,
                                          reduction="mean")
            elif self.task_type == TaskType.SENTENCE:
                loss_function = nn.CrossEntropyLoss()
            else:
                loss_function = nn.BCEWithLogitsLoss()

            self.mixup = Mixup(loss_fn=loss_function) if use_mixup else None
            self.classifier = MLPClassificationHead(
                hidden=hidden_size,
                num_labels=num_labels,
                loss_fn=loss_function,
            )


        else:
            self.use_dora = False
            self.classifier = nn.Linear(hidden_size, num_labels)
            self.classifier = None

    def forward(self, hidden, mask=None, labels=None, return_logits=False):
        if self.task_type.is_sentence_level():
            x = hidden
            if self.attention_layer is not None and x.dim() == 3:
                key_padding_mask = None
                if mask is not None:
                    key_padding_mask = ~mask
                attn_out, _ = self.attention_layer(
                    x, x, x,
                    key_padding_mask=key_padding_mask,
                    need_weights=False,
                )
                pooled = attn_out.mean(dim=1)
            else:
                if x.dim() == 3:
                    pooled = x.mean(dim=1)
                else:
                    pooled = x

            if self.dora_adapter is not None:
                pooled = self.dora_adapter(pooled)

            if labels is not None:
                if self.mixup is not None:
                    pooled, y_a, y_b, lam = self.mixup.augment(pooled, labels)
                    logits = self.classifier(pooled)
                    loss = self.mixup(logits, y_a, y_b, lam)
                    return logits, loss

                return self.classifier(pooled, labels)
            else:
                logits = self.classifier(pooled)
                if return_logits:
                    return logits

                if self.task_type == TaskType.SENTENCE_MULTILABEL:
                    probs = torch.sigmoid(logits)
                    return (probs > 0.5).int()
                else:
                    return torch.argmax(logits, dim=-1)


        else:  # TOKEN CLASSIFICATION
            if labels is not None:
                return self.classifier(hidden, mask=mask, labels=labels)
            else:
                return self.classifier(hidden, mask=mask)

        if self.dora_adapter is not None:
            adapted = self.dora_adapter(hidden)
        else:
            adapted = hidden

        if self.attention_layer is not None:
            if self.task_type.is_sentence_level():
                adapted, _ = self.attention_layer(adapted, adapted, adapted)

        if self.task_type.is_sentence_level():
            if self.attention_layer is not None:
                pooled = adapted.mean(dim=1)
            else:
                pooled = adapted

            if labels is not None:
                if self.mixup is not None:
                    pooled, y_a, y_b, lam = self.mixup.augment(pooled, labels)
                    logits = self.classifier(pooled)
                    loss = self.mixup(logits, y_a, y_b, lam)
                    return logits, loss

                return self.classifier(pooled, labels)
            else:
                logits = self.classifier(pooled)
                if return_logits:
                    return logits
                elif self.task_type == TaskType.SENTENCE_MULTILABEL:
                    probs = torch.sigmoid(logits)
                    return (probs > 0.5).int()
                else:
                    return torch.argmax(logits, dim=-1)

        else:
            if labels is not None:
                return self.classifier(adapted, mask=mask, labels=labels)
            else:
                return self.classifier(adapted, mask=mask)


class Task(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )

    annotation_type: str
    name: str
    type: TaskType
    label2id: Dict[str, int]
    num_attention_heads: int = 0
    rank: int = 8
    alpha: int = 8
    language: Optional[str] = None
    min_confidence: float = 0
    default_class: Optional[str] = None
    ignore_classes: List[str] = Field(default_factory=list)
    lstm_hidden: Optional[int] = None
    head: Optional[TaskHead] = None
    use_dora: bool = True

    @computed_field
    @property
    def id2label(self) -> Dict[int, str]:
        return {v: k for k, v in self.label2id.items()}

    def to_json(self):
        return self.model_dump(exclude={"head", "id2label"})

    @classmethod
    def from_dict(cls, json_dict):
        return cls.model_validate(json_dict)

    def create_head(self,
                    hidden_size: int,
                    original_layer: nn.Linear,
                    device: torch.device | str = "cpu",
                    path: Optional[str] = None):

        label_list = [""] * len(self.label2id)
        for idx, label in self.id2label.items():
            label_list[idx] = label

        self.head = TaskHead(
            hidden_size=hidden_size,
            num_labels=len(self.label2id),
            task_type=self.type,
            original_layer=original_layer,
            rank=self.rank,
            alpha=self.alpha,
            lstm_hidden=self.lstm_hidden,
            num_attention_heads=self.num_attention_heads,
            label_list=label_list,
            use_dora=self.use_dora,
        )
        if path is not None:
            self.head.load_state_dict(
                torch.load(f"{path}/{self.name}_head.pt", map_location=device)
            )
        self.head.to(device)
        self.head.eval()
        return self.head

    def to_labels(self,
                  head_output: torch.Tensor | List[List[int]],
                  embedding: "EmbeddingResult") -> (List[Tuple[str | None, float]] |
                                                    List[Tuple[List[str], list[float]]] |
                                                    List[List[str]]):

        if self.type == TaskType.SENTENCE_MULTILABEL:
            probs = torch.sigmoid(head_output)  # type: ignore
            predictions = (probs >= self.min_confidence).int().cpu().tolist()
            labels = []
            for prediction in predictions:
                row_label = []
                row_probs = []
                for index, value in enumerate(prediction):
                    if value == 0:
                        continue
                    label_str = self.id2label[index]
                    if label_str not in self.ignore_classes:
                        row_label.append(label_str)
                        row_probs.append(probs[index].item())
                labels.append((row_label, row_probs))
            return labels

        if self.type == TaskType.SENTENCE:
            probs = torch.softmax(head_output, dim=-1)  # type: ignore
            predictions = torch.argmax(probs, dim=-1).cpu().tolist()
            labels = []
            for i, label in enumerate(predictions):
                if probs[i][label] >= self.min_confidence:
                    label_str = self.id2label[label]
                    if label_str not in self.ignore_classes:
                        labels.append((label_str, probs[i][label].item()))
                else:
                    labels.append((self.default_class, 0))
            return labels

        output = []
        for sentence in head_output:
            output.append([self.id2label[i] for i in sentence])  # type:ignore
        return output


def decode_predictions(
    pred_label_ids: List[List[int]],
    embedding: EmbeddingResult,
    id2label: Dict[int, str],
):
    all_spans = []
    for mapping, label_seq in zip(embedding.mapping, pred_label_ids):
        word_labels = []
        for token_label_id, word_id in zip(label_seq, mapping.word_ids):
            if word_id is None:
                continue
            if len(word_labels) <= word_id:
                word_labels.append(id2label[token_label_id])
            else:
                pass

        spans = []
        start, label = None, None
        for i, tag in enumerate(word_labels):
            if tag.startswith("B-"):
                if start is not None:
                    spans.append((start, i, label))
                start = i
                label = tag[2:]
            elif tag.startswith("I-"):
                if label != tag[2:]:
                    if start is not None:
                        spans.append((start, i, label))
                    start = i
                    label = tag[2:]
            else:
                if start is not None:
                    spans.append((start, i, label))
                    start, label = None, None

        if start is not None:
            spans.append((start, len(word_labels), label))

        all_spans.append(spans)

    return all_spans


class TaskRegistry:
    def __init__(self, hidden_size: int):
        self.hidden_size = hidden_size
        self.registry: Dict[str, Task] = {}

    def register_task(
        self,
        task: Task
    ) -> Task:
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

        dummy_layer = nn.Linear(self.hidden_size, self.hidden_size)
        task.create_head(self.hidden_size, dummy_layer)
        return task

    def unload_task(self, task_name):
        task = self.registry[task_name]
        task.head = None
