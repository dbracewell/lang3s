import argparse
from typing import Dict, List

import torch
from datasets import Dataset

from lang3s.models.trainer import train_task
from lang3s.models.transformer import TaskType


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
            label = line[index + 1 :].strip()
            sentences.append(text)
            labels.append(label)
    return sentences, labels


class SentenceClassificationDataset(Dataset):
    def __init__(self, path: str):
        texts, labels = read_text_file(path)
        self.texts = texts
        self.label2Id: Dict[str, int] = {}
        for idx, lbl in enumerate(set(labels)):
            self.label2Id[lbl] = idx
        self.labels = [self.label2Id[lbl] for lbl in labels]

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx: int):
        if isinstance(idx, list):
            return {
                "text": [self.texts[i] for i in idx],
                "label": torch.tensor(
                    [self.labels[i] for i in idx],
                    dtype=torch.int64,
                ),
            }
        return {
            "text": self.texts[idx],
            "label": torch.tensor(self.labels[idx]),
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task_name", help="Task name", required=True)
    parser.add_argument("--data", help="Data directory", required=True)
    parser.add_argument("--lang", help="Language", required=True)
    parser.add_argument("--type", help="Annotation type", required=True)
    parser.add_argument(
        "--num_epochs",
        type=int,
        default=10,
        help="Number of epochs to train the model",
        required=True,
    )
    args = parser.parse_args()

    dataset = SentenceClassificationDataset(args.data)
    train_task(
        task_name=args.task_name,
        task_type=TaskType.SENTENCE,
        label2id=dataset.label2Id,
        language=args.lang,
        annotation_type=args.type,
        dataset=dataset,
        num_epochs=args.num_epochs,
    )
