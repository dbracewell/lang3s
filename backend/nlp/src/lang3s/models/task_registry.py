import os
from typing import Dict, Iterable, Optional, List, Tuple

import torch
import torch.nn as nn

from lang3s import config
from .augmentation.mixup import Mixup
from .layers.adapter import DoRA
from .layers.crf import BiLSTMCRFClassifierHead
from .layers.mlp import MLPClassificationHead
from .loss.focal import FocalLoss
from .shared_types import TaskType, EmbeddingResult


class TaskHead(nn.Module):

    def __init__(self,
                 task_type: TaskType,
                 hidden_size: int,
                 num_labels: int,
                 original_layer: nn.Linear,
                 rank: int = 8,
                 alpha: int = 8,
                 dropout=0.2,
                 lstm_hidden: Optional[int] = None,
                 use_mixup: bool = False,
                 weights: Optional[torch.Tensor] = None,
                 use_focal_loss: bool = False,
                 ):
        super(TaskHead, self).__init__()
        self.task_type = task_type
        self.dora_adapter = DoRA(original_layer=original_layer, rank=rank, alpha=alpha)

        if self.task_type.is_sentence_level():
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
            self.mixup = None
            self.classifier = BiLSTMCRFClassifierHead(
                hidden_size=hidden_size,
                num_labels=num_labels,
                dropout=dropout,
                lstm_hidden=lstm_hidden,
            )

    def forward(self, hidden, mask=None, labels=None, return_logits=False):
        adapted = self.dora_adapter(hidden)

        if self.task_type.is_sentence_level():
            if mask is not None:
                mask = mask.unsqueeze(-1).float()
                summed = torch.sum(adapted * mask, dim=1)
                counts = torch.clamp(mask.sum(dim=1), min=1e-9)
                pooled = summed / counts
            else:
                pooled = adapted.mean(dim=1)

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
            return self.classifier(hidden, mask=mask, labels=labels)


class Task:
    def __init__(
        self,
        name: str,
        type: TaskType | str,
        label2id: Dict[str, int],
        annotation_type: str,
        rank: int = 8,
        alpha: int = 8,
        language: Optional[str] = None,
        min_confidence: float = 0,
        default_class: Optional[str] = None,
        ignore_classes: Optional[List[str]] = None,
        lstm_hidden: Optional[int] = None,
    ) -> None:
        self.annotation_type = annotation_type
        self.language = language
        self.label2id = label2id
        self.id2label = {v: k for k, v in label2id.items()}
        self.type = type if isinstance(type, TaskType) else TaskType(type)
        self.name = name
        self.rank = rank
        self.alpha = alpha
        self.head: Optional[torch.nn.Module] = None
        self.min_confidence = min_confidence
        self.default_class = default_class
        self.ignore_classes = ignore_classes or []
        self.lstm_hidden = lstm_hidden

    def to_json(self):
        return {
            "annotation_type": self.annotation_type,
            "language": self.language,
            "label2id": self.label2id,
            "type": self.type.value,
            "name": self.name,
            "min_confidence": self.min_confidence,
            "default_class": self.default_class,
            "ignore_classes": self.ignore_classes,
            "rank": self.rank,
            "alpha": self.alpha,
            "lstm_hidden": self.lstm_hidden,
        }

    def to_labels(self,
                  head_output: torch.Tensor | List[List[int]],
                  embedding: "EmbeddingResult") -> List[Tuple[str | None, float]] | List[
        Tuple[List[str], list[float]]] | List[
                                                       List[Tuple[int, int, str]]]:

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

        return decode_predictions(head_output, embedding, id2label)  # type: ignore


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
        self.device = config.DEVICE
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

        head = TaskHead(
            hidden_size=self.hidden_size,
            num_labels=len(task.label2id),
            task_type=task.type,
            original_layer=dummy_layer,
            rank=task.rank,
            alpha=task.alpha,
            lstm_hidden=task.lstm_hidden,
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
