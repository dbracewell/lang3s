import argparse
from typing import Dict, List

import torch
from datasets import load_dataset
from jsonlines import jsonlines
from torch.utils.data import Dataset

from lang3s.models.trainer import train_task
from lang3s.models.types import TaskType


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
    def __init__(self, path: str, data_format: str, json_label: str, json_text: str):
        if data_format == "text":
            sentences, labels = read_text_file(path)
        elif data_format == "json":
            sentences, labels = read_jsonl(path, text=json_text, label=json_label)
        else:
            raise ValueError(f"Format not supported: {data_format}")

        self.texts = sentences
        self.label2Id: Dict[str, int] = {}

        if isinstance(labels[0], list):
            self.multi_label = True
            unique_labels = sorted(set(l for sublist in labels for l in sublist))
        else:
            self.multi_label = False
            unique_labels = sorted(set(labels))

        self.label2Id = {lbl: idx for idx, lbl in enumerate(unique_labels)}
        self.id2label = {v: k for k, v in self.label2Id.items()}

        if self.multi_label:
            self.labels = []
            for lbl_list in labels:
                vec = torch.zeros(len(unique_labels), dtype=torch.float)
                for lbl in lbl_list:
                    if lbl in self.label2Id:
                        vec[self.label2Id[lbl]] = 1.0
                self.labels.append(vec)
        else:
            self.labels = [self.label2Id[lbl] for lbl in labels]

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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task_name", help="Task name", required=True)
    parser.add_argument("--data", help="Data directory", required=True)
    parser.add_argument("--lang", help="Language", required=True)
    parser.add_argument("--type", help="Annotation type", required=True)
    parser.add_argument("--format", help="Dataset format", required=False, default="text")
    parser.add_argument("--label", help="Label Field for json", required=False, default="label")
    parser.add_argument("--text", help="Text Field for json", required=False, default="text")
    parser.add_argument("--multilabel", action="store_true", help="Is multilabel", required=False, default=False)
    parser.add_argument(
        "--num_epochs",
        type=int,
        default=10,
        help="Number of epochs to train the model",
        required=False,
    )
    args = parser.parse_args()

    if args.format == "hf":
        dataset = HuggingFaceDataset(args.data, label=args.label, text=args.text)
    else:
        dataset = SentenceClassificationDataset(args.data, args.format, args.label, args.text)
    train_task(
        task_name=args.task_name,
        task_type=TaskType.SENTENCE_MULTILABEL if args.multilabel else TaskType.SENTENCE,
        label2id=dataset.label2Id,
        language=args.lang,
        annotation_type=args.type,
        dataset=dataset,
        num_epochs=args.num_epochs,
    )
