from typing import List

from lang3s.models.shared_types import SentenceTokenMapping


def align_labels(mapping: SentenceTokenMapping, labels: List[int]):
    assert mapping.token_count == len(mapping.word_ids), (
        f"token_count mismatch: {mapping.token_count} vs {len(mapping.word_ids)}"
    )

    encoded = []
    for word_idx in mapping.word_ids:

        if word_idx is None:
            encoded.append(-100)
            continue

        if not (0 <= word_idx < len(labels)):
            raise ValueError(
                f"word_idx out of range: {word_idx} labels_len={len(labels)}"
            )

        encoded.append(labels[word_idx])

    return encoded  # normal Python list
