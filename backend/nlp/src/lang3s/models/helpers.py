from typing import List

import numpy as np

from lang3s.models.shared_types import SentenceTokenMapping


def align_labels(mapping: SentenceTokenMapping, labels: List[int]):
    token_count = mapping.token_count
    encoded = np.full(token_count, -100, dtype=np.int64)  # default pad
    for token_idx, word_idx in enumerate(mapping.word_ids):
        if word_idx is None:
            encoded[token_idx] = -100
        else:
            if word_idx < 0 or word_idx >= len(labels):
                raise ValueError(
                    f"word_idx out of range: {word_idx} labels_len={len(labels)}"
                )
            encoded[token_idx] = labels[word_idx]
    return encoded
