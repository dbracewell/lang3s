from typing import Dict, Optional, List

from pydantic import Field
from torch.utils.data import Dataset

from lang3s.app import Application
from lang3s.io.conll import read_conll_file
from lang3s.models.shared_types import TaskType
from lang3s.models.trainer import train_task


class IOBDataset(Dataset):
    def __init__(self, path: str):
        self.sentences, self.labels = read_conll_file(path)
        # self.sentences = self.sentences[:100]
        # self.labels = self.labels[:100]
        self.label2Id: Dict[str, int] = self._create_label_map()
        self.id2label: Dict[int, str] = {v: k for k, v in self.label2Id.items()}
        self.indexed_labels = [[self.label2Id[lbl] for lbl in s] for s in self.labels]

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
            batch_index = [self.indexed_labels[i] for i in idx]
            return {"text": batch_sentences,
                    "label": batch_index,
                    "raw_label": batch_labels}

        return {"text": self.sentences[idx],
                "label": self.indexed_labels[idx],
                "raw_label": self.labels[idx]}


class TokenClassifier(Application):
    """
    This application trains a token classifier.
    """

    task_name: str = Field(description="Name of the task, should be unique")
    data: str = Field(description="Path to the dataset")
    type: str = Field(description="The type of produced by the classifier which gets added to sentence metadata")
    lang: Optional[str] = Field(default=None, description="The language supported by the classifier")
    ignore_classes: Optional[List[str]] = Field(default=None,
                                                description="Classes to not include during classification")
    num_epochs: int = Field(default=100, description="Number of epochs to train the model")
    rank: int = Field(default=8, description="Rank of DoRA Layer")
    alpha: int = Field(default=8, description="Alpha of DoRA Layer")
    num_attention_heads: int = Field(default=0, description="Number of heads for attention layer")
    lstm_hidden_dim: int = Field(default=256, description="LSTM hidden dimension")

    def run(self):
        task_type: TaskType = TaskType.TOKEN
        dataset = IOBDataset(self.data)
        train_task(
            task_name=self.task_name,
            task_type=task_type,
            label2id=dataset.label2Id,
            language=self.lang,
            annotation_type=self.type,
            dataset=dataset,
            rank=self.rank,
            alpha=self.alpha,
            num_epochs=self.num_epochs,
            ignore_classes=self.ignore_classes,
            num_attention_heads=self.num_attention_heads,
            lstm_hidden=self.lstm_hidden_dim,
            lr=5e-5,
            warmup_ratio=0.1,
        )


if __name__ == "__main__":
    TokenClassifier.from_cli().run()
