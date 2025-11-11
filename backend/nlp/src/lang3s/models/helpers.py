from typing import Dict, List

import numpy as np

from lang3s.models.embedder import EmbeddingResult, SentenceTokenMapping


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


def decode_predictions(
    pred_label_ids: List[List[int]],
    embedding: EmbeddingResult,
    id2label: Dict[int, str],
):
    all_spans = []
    for mapping, label_seq in zip(embedding.mapping, pred_label_ids):
        word_labels = []
        for token_label_id, word_id in zip(label_seq, mapping.word_ids):
            if word_id is None:
                continue
            if len(word_labels) <= word_id:
                word_labels.append(id2label[token_label_id])
            else:
                pass

        spans = []
        start, label = None, None
        for i, tag in enumerate(word_labels):
            if tag.startswith("B-"):
                if start is not None:
                    spans.append((start, i, label))
                start = i
                label = tag[2:]
            elif tag.startswith("I-"):
                if label != tag[2:]:
                    if start is not None:
                        spans.append((start, i, label))
                    start = i
                    label = tag[2:]
            else:
                if start is not None:
                    spans.append((start, i, label))
                    start, label = None, None

        if start is not None:
            spans.append((start, len(word_labels), label))

        all_spans.append(spans)

    return all_spans
