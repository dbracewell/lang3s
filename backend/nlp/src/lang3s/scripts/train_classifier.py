import argparse
from typing import Dict, List, Optional

import torch
from datasets import load_dataset
from jsonlines import jsonlines
from pydantic import Field
from torch.utils.data import Dataset

from lang3s.app import Application
from lang3s.models.shared_types import TaskType
from lang3s.models.trainer import train_task


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


class SentenceClassificationDataset(Dataset):
    def __init__(self, path: str, task_type: TaskType, data_format: str, label: str, text: str):
        if data_format == "text":
            sentences, labels = read_text_file(path)
        elif data_format == "json":
            sentences, labels = read_jsonl(path, text=text, label=label)
        else:
            raise ValueError(f"Format not supported: {data_format}")

        self.texts = sentences
        self.label2Id: Dict[str, int] = {}

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

        self.label2Id = {lbl: idx for idx, lbl in enumerate(unique_labels)}
        self.id2label = {v: k for k, v in self.label2Id.items()}

        if task_type == TaskType.SENTENCE_MULTILABEL:
            self.labels = []
            for lbl_list in labels:
                vec = torch.zeros(len(unique_labels), dtype=torch.float)
                for lbl in lbl_list:
                    if lbl in self.label2Id:
                        vec[self.label2Id[lbl]] = 1.0
                self.labels.append(vec)
        else:
            self.labels = [self.label2Id[lbl] for lbl in labels]  # type:ignore

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


class HuggingFaceDataset(Dataset):
    def __init__(self, name: str, label: str = "label", text: str = "text"):
        self.dataset = load_dataset(name)["train"]
        self.label = label
        self.text = text
        unique_labels = set(self.dataset[label])
        self.label2Id: Dict[str, int] = {l: i for i, l in enumerate(unique_labels)}

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, idx: int):
        df = self.dataset[idx]  # type: ignore
        return {
            "text": df[self.text],
            "label": df[self.label]
        }


class ClassificationTrainer(Application):
    """
    This application trains a sentence classifier.
    """

    task_name: str = Field(description="Name of the task, should be unique")
    data: str = Field(description="Path to the dataset")
    type: str = Field(description="The type of produced by the classifier which gets added to sentence metadata")
    multilabel: bool = Field(default=False, description="Determines if the classifier can produce multiple labels")
    lang: Optional[str] = Field(default=None, description="The language supported by the classifier")
    format: str = Field(default="text", description="The format of the dataset [text,json,hf]")
    label: str = Field(default="label", description="The label of the dataset")
    text: str = Field(default="text", description="The text of the dataset")
    mixup: bool = Field(default=False, description="Whether to use mixup augmentation")
    focal_loss: bool = Field(default=False, description="Whether to use focal loss")
    min_confidence: Optional[float] = Field(default=None, description="Minimum confidence threshold")
    default_class: Optional[str] = Field(default=None, description="Default class label")
    ignore_classes: Optional[List[str]] = Field(default=None,
                                                description="Classes to not include during classification")
    num_epochs: int = Field(default=10, description="Number of epochs to train the model")
    rank: int = Field(default=8, description="Rank of DoRA Layer")

    def run(self):
        task_type: TaskType = TaskType.SENTENCE_MULTILABEL if self.multilabel else TaskType.SENTENCE

        if self.format == "hf":
            dataset = HuggingFaceDataset(self.data, label=self.label, text=self.text)
        else:
            dataset = SentenceClassificationDataset(
                path=self.data,
                task_type=task_type,
                data_format=self.format,
                label=self.label,
                text=self.text
            )

        if self.min_confidence is None:
            self.min_confidence = 0.5 if self.multilabel else 0.0

        train_task(
            task_name=self.task_name,
            task_type=task_type,
            label2id=dataset.label2Id,
            language=self.lang,
            annotation_type=self.type,
            dataset=dataset,
            rank=self.rank,
            alpha=self.rank,
            num_epochs=self.num_epochs,
            min_confidence=self.min_confidence,
            default_class=self.default_class,
            ignore_classes=self.ignore_classes,
            use_mixup=self.mixup,
            use_focal_loss=self.focal_loss,
        )


if __name__ == "__main__":
    ClassificationTrainer.from_cli().run_with_plugins()

    exit()
    parser = argparse.ArgumentParser()
    parser.add_argument("--task_name", help="Task name", required=True)
    parser.add_argument("--data", help="Data directory", required=True)
    parser.add_argument("--lang", help="Language", required=True)
    parser.add_argument("--type", help="Annotation type", required=True)
    parser.add_argument("--format", help="Dataset format", required=False, default="text")
    parser.add_argument("--label", help="Label Field for json", required=False, default="label")
    parser.add_argument("--text", help="Text Field for json", required=False, default="text")
    parser.add_argument("--multilabel", action="store_true", help="Is multilabel", required=False, default=False)
    parser.add_argument("--mixup", action="store_true", help="Use mixup augmentation", required=False, default=False)
    parser.add_argument("--focal_loss", action="store_true", help="Use Focal Loss for class imbalanced datasets",
                        required=False, default=False)
    parser.add_argument("--min_confidence", help="Minimum confidence threshold", required=False, type=float,
                        default=None)
    parser.add_argument("--default_class", help="Default class label", required=False, type=str, default=None)
    parser.add_argument(
        "--num_epochs",
        type=int,
        default=10,
        help="Number of epochs to train the model",
        required=False,
    )
    parser.add_argument("--ignore_classes", nargs="*", help="Ignore classes", required=False, type=str, default=None)
    parser.add_argument("--rank", type=int, help="Rank of DoRA Layer", required=False, default=8)
    args = parser.parse_args()

    task_type: TaskType = TaskType.SENTENCE_MULTILABEL if args.multilabel else TaskType.SENTENCE

    if args.format == "hf":
        dataset = HuggingFaceDataset(args.data, label=args.label, text=args.text)
    else:
        dataset = SentenceClassificationDataset(
            path=args.data,
            task_type=task_type,
            data_format=args.format,
            label=args.label,
            text=args.text
        )

    if args.min_confidence is None:
        args.min_confidence = 0.5 if args.multilabel else 0.0

    train_task(
        task_name=args.task_name,
        task_type=task_type,
        label2id=dataset.label2Id,
        language=args.lang,
        annotation_type=args.type,
        dataset=dataset,
        rank=args.rank,
        alpha=args.rank,
        num_epochs=args.num_epochs,
        min_confidence=args.min_confidence,
        default_class=args.default_class,
        ignore_classes=args.ignore_classes,
        use_mixup=args.mixup,
        use_focal_loss=args.focal_loss,
    )
