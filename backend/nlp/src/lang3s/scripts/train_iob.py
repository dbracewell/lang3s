from typing import List, Tuple

from lang3s.app import Application
from lang3s.models.training.iob import IObTrainer, TokenClassificationParams, TokenDataset
from lang3s.models.training.trainer import TrainerParams


def read_conll_file(path: str) -> List[Tuple[List[str], List[str]]]:
    sentences = []
    tokens, labels = [], []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                if len(tokens) > 0:
                    sentences.append((tokens, labels))
                    tokens, labels = [], []
            else:
                splits = line.split()
                token, label = splits[0], splits[-1]
                tokens.append(token)
                labels.append(label)

        if len(tokens) > 0:
            sentences.append((tokens, labels))

    return sentences


class TokenClassifier(Application, TrainerParams, TokenClassificationParams):
    """
    This application trains a token classifier.
    """

    def run(self):
        trainer = IObTrainer(
            dataset=TokenDataset(read_conll_file(self.data)),
            **vars(self)
        )
        trainer.train()


if __name__ == "__main__":
    TokenClassifier.from_cli().run()
