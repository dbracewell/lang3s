import argparse
from typing import Dict

from datasets import Dataset

from lang3s.io.conll import read_conll_file
from lang3s.models.trainer import train_task
from lang3s.models.transformer import TaskType


class IOBDataset(Dataset):
    def __init__(self, path: str):
        self.sentences, self.labels = read_conll_file(path)
        self.label2Id: Dict[str, int] = self._create_label_map()
        self.labels = [[self.label2Id[lbl] for lbl in s] for s in self.labels]

    def _create_label_map(self):
        labels = set()
        for sentence in self.labels:
            for lbl in sentence:
                if lbl != "O":
                    labels.add(lbl)

        label_list = sorted(labels, key=lambda x: (x[2:], x[:1]))
        label_list.insert(0, "O")

        return {lab: i for i, lab in enumerate(label_list)}

    def __len__(self):
        return len(self.sentences)

    def __getitem__(self, idx: int):
        if isinstance(idx, list):
            batch_sentences = [self.sentences[i] for i in idx]
            batch_labels = [self.labels[i] for i in idx]
            max_len = max(len(s) for s in batch_sentences)
            batch_sentences = [
                s + ["~~~EMPTY~~~"] * (max_len - len(s))
                for s in batch_sentences
            ]
            batch_labels = [
                s + [-500] * (max_len - len(s)) for s in batch_labels
            ]
            return {"text": batch_sentences, "label": batch_labels}
        return {"text": self.sentences[idx], "label": self.labels[idx]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task_name", help="Task name", required=True)
    parser.add_argument("--data", help="Data directory", required=True)
    parser.add_argument("--lang", help="Language", required=True)
    parser.add_argument("--type", help="Annotation type", required=True)
    parser.add_argument(
        "--num_epochs",
        type=int,
        default=3,
        help="Number of epochs to train the model",
    )
    args = parser.parse_args()

    dataset = IOBDataset(args.data)
    train_task(
        task_name=args.task_name,
        task_type=TaskType.TOKEN,
        label2id=dataset.label2Id,
        language=args.lang,
        annotation_type=args.type,
        dataset=dataset,
        num_epochs=args.num_epochs,
        lr=1e-4,
    )
