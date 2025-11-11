from typing import List, Tuple


def read_conll_file(path: str) -> Tuple[List[List[str]], List[List[str]]]:
    sentences = []
    sentences_labels = []
    tokens, labels = [], []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                if len(tokens) > 0:
                    sentences.append(tokens)
                    sentences_labels.append(labels)
                    tokens, labels = [], []
            else:
                splits = line.split()
                token, label = splits[0], splits[-1]
                tokens.append(token)
                labels.append(label)

        if len(tokens) > 0:
            sentences.append(tokens)
            sentences_labels.append(labels)

    return sentences, sentences_labels
