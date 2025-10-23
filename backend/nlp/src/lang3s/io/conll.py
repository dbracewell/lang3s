from datasets import Dataset, DatasetDict
from typing import List


def read_conll_file(path: str):
    sentences = []
    tokens, labels = [], []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                if tokens:
                    sentences.append({"tokens": tokens, "labels": labels})
                    tokens, labels = [], []
            else:
                splits = line.split()
                token, label = splits[0], splits[-1]
                tokens.append(token)
                labels.append(label)
        if tokens:
            sentences.append({"tokens": tokens, "labels": labels})
    return sentences


def load_conll_dataset(task_files: dict, splits: List[str] | None = None):
    if splits is None:
        splits = ["train", "dev", "test"]
    dataset_splits = {}
    for split_name in splits:
        if split_name in task_files and task_files[split_name] is not None:
            dataset_splits[split_name] = Dataset.from_list(
                read_conll_file(task_files[split_name])
            )
    return DatasetDict(dataset_splits)
