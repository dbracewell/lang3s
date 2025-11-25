from typing import Dict, List

import torch
from datasets import load_dataset
from jsonlines import jsonlines
from pydantic import Field

from lang3s.app import Application
from lang3s.models.training.sentenceclf import SentenceClassifierTrainer
from lang3s.models.training.trainer import Lang3sDataset, TrainerParams
from lang3s.models.transformer.task import SentenceClassificationParams, TaskType


def read_text_file(path: str):
    sentences: List[str] = []
    labels: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "\t" not in line:
                continue
            index = line.rindex("\t")
            text = line[:index].strip()
            label = line[index + 1:].strip()
            sentences.append(text)
            labels.append(label)
    return sentences, labels


def read_jsonl(path: str, text: str = "text", label: str = "label"):
    sentences: List[str] = []
    labels: List[str] = []
    with jsonlines.open(path, mode="r") as f:
        for doc in f:
            sentences.append(doc[text])
            labels.append(doc[label])
    return sentences, labels


class SentenceClassificationDataset(Lang3sDataset):
    def __init__(self, path: str, task_type: TaskType, data_format: str, label: str, text: str):
        super().__init__()
        if data_format == "text":
            sentences, labels = read_text_file(path)
        elif data_format == "json":
            sentences, labels = read_jsonl(path, text=text, label=label)
        else:
            raise ValueError(f"Format not supported: {data_format}")

        self.texts = sentences
        if task_type == TaskType.SENTENCE_MULTILABEL:
            self.multi_label = True
            if isinstance(labels[0], list):
                unique_labels = sorted(set(l for sublist in labels for l in sublist))
            else:
                unique_labels = sorted(set(labels))
                labels = [[label] for label in labels]
        else:
            self.multi_label = False
            unique_labels = sorted(set(labels))

        self.label2idx = {lbl: idx for idx, lbl in enumerate(unique_labels)}
        self.idx2label = {v: k for k, v in self.label2idx.items()}

        if task_type == TaskType.SENTENCE_MULTILABEL:
            self.labels = []
            for lbl_list in labels:
                vec = torch.zeros(len(unique_labels), dtype=torch.float)
                for lbl in lbl_list:
                    if lbl in self.label2idx:
                        vec[self.label2idx[lbl]] = 1.0
                self.labels.append(vec)
        else:
            self.labels = [self.label2idx[lbl] for lbl in labels]  # type:ignore

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx: int):
        if isinstance(idx, list):
            return {
                "text": [self.texts[i] for i in idx],
                "label": torch.tensor(
                    [self.labels[i] if self.multi_label
                     else torch.tensor(self.labels[i], dtype=torch.long) for i in idx],
                    dtype=torch.int64,
                ),
            }
        return {
            "text": self.texts[idx],
            "label": self.labels[idx]
            if self.multi_label
            else torch.tensor(self.labels[idx], dtype=torch.long)
        }


class HuggingFaceDataset(Lang3sDataset):
    def __init__(self, name: str, label: str = "label", text: str = "text"):
        super().__init__()
        self.dataset = load_dataset(name)["train"]
        self.label = label
        self.text = text
        unique_labels = set(self.dataset[label])
        self.label2idx: Dict[str, int] = {l: i for i, l in enumerate(unique_labels)}
        self.idx2label = {v: k for k, v in self.label2idx.items()}

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, idx: int):
        df = self.dataset[idx]  # type: ignore
        return {
            "text": df[self.text],
            "label": df[self.label]
        }


# class ClassificationTrainer(Application):
#     """
#     This application trains a sentence classifier.
#     """
#
#     task_name: str = Field(description="Name of the task, should be unique")
#     data: str = Field(description="Path to the dataset")
#     type: str = Field(description="The type of produced by the classifier which gets added to sentence metadata")
#     multilabel: bool = Field(default=False, description="Determines if the classifier can produce multiple labels")
#     lang: Optional[str] = Field(default=None, description="The language supported by the classifier")
#     format: str = Field(default="text", description="The format of the dataset [text,json,hf]")
#     label: str = Field(default="label", description="The label of the dataset")
#     text: str = Field(default="text", description="The text of the dataset")
#     mixup: bool = Field(default=False, description="Whether to use mixup augmentation")
#     focal_loss: bool = Field(default=False, description="Whether to use focal loss")
#     min_confidence: Optional[float] = Field(default=None, description="Minimum confidence threshold")
#     default_class: Optional[str] = Field(default=None, description="Default class label")
#     ignore_classes: Optional[List[str]] = Field(default=None,
#                                                 description="Classes to not include during classification")
#     num_epochs: int = Field(default=10, description="Number of epochs to train the model")
#     rank: int = Field(default=8, description="Rank of DoRA Layer")
#     num_attention_heads: int = Field(default=0, description="Number of heads for attention layer")
#
#     def run(self):
#         task_type: TaskType = TaskType.SENTENCE_MULTILABEL if self.multilabel else TaskType.SENTENCE
#
#         if self.format == "hf":
#             dataset = HuggingFaceDataset(self.data, label=self.label, text=self.text)
#         else:
#             dataset = SentenceClassificationDataset(
#                 path=self.data,
#                 task_type=task_type,
#                 data_format=self.format,
#                 label=self.label,
#                 text=self.text
#             )
#
#         if self.min_confidence is None:
#             self.min_confidence = 0.5 if self.multilabel else 0.0
#
#         train_task(
#             task_name=self.task_name,
#             task_type=task_type,
#             label2id=dataset.label2Id,
#             language=self.lang,
#             annotation_type=self.type,
#             dataset=dataset,
#             rank=self.rank,
#             alpha=self.rank,
#             num_epochs=self.num_epochs,
#             min_confidence=self.min_confidence,
#             default_class=self.default_class,
#             ignore_classes=self.ignore_classes,
#             use_mixup=self.mixup,
#             use_focal_loss=self.focal_loss,
#             num_attention_heads=self.num_attention_heads,
#         )


class ClfTrainer(Application, TrainerParams, SentenceClassificationParams):
    multilabel: bool = Field(default=False, description="Multilabel classification")
    format: str = Field(default="json", description="Format of the dataset")

    def run(self):
        params = dict(vars(self))
        params["task_type"] = TaskType.SENTENCE_MULTILABEL if self.multilabel else TaskType.SENTENCE
        if self.format == "hf":
            dataset = HuggingFaceDataset(name=self.data, label=self.label, text=self.text)
        else:
            dataset = SentenceClassificationDataset(task_type=params["task_type"],
                                                    data_format=self.format,
                                                    path=self.data,
                                                    label=self.label,
                                                    text=self.text)
        trainer = SentenceClassifierTrainer(dataset=dataset, **params)
        trainer.train()


if __name__ == "__main__":
    ClfTrainer.from_cli().run()
