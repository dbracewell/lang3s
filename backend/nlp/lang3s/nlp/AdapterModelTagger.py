import sys
from typing import List, Set

import numpy as np

from lang3s import config
from lang3s.core.core_types import Document, Text, TextAnnotation
from lang3s.models.adapter import AdapterModel
from lang3s.utils import partition


def __average_embedding(embeddings: List[List[float]]) -> List[float]:
    sums = [np.array(vector) for vector in embeddings]
    return np.average(sums, axis=0).tolist()


class AdapterModelTagger:
    def __init__(self) -> None:
        self.model = AdapterModel()

    def __add_annotation(
        self,
        text: Text,
        start: int,
        end: int,
        offset: int,
        tokens: List[TextAnnotation],
        annotation_type: str,
        label: str,
    ):
        text.add_annotation(
            start=start + offset,
            end=end + offset,
            value=label,
            text=" ".join([tokens[i].text for i in range(start, end)]),
            embedding=__average_embedding(
                [tokens[i].embedding for i in range(start, end)]
            ),
            type=annotation_type,
        )

    def __process_bio_tags(
        self,
        text: Text,
        offset: int,
        tokens: List[TextAnnotation],
        annotation_type: str,
        labels: List[str],
    ):
        start = -1
        prev_label = "O"
        for idx, label in enumerate(labels):
            if label == "O":
                if start >= 0 and prev_label != "O":
                    self.__add_annotation(
                        text,
                        start,
                        idx,
                        offset,
                        tokens,
                        annotation_type,
                        prev_label,
                    )
                start = -1
                prev_label = "O"
            elif label.startswith("B-"):
                if start >= 0 and prev_label != "O":
                    self.__add_annotation(
                        text,
                        start,
                        idx,
                        offset,
                        tokens,
                        annotation_type,
                        prev_label,
                    )
                prev_label = label[2:]
                start = idx
            elif label.startswith("I-"):
                if start >= 0 and prev_label == label[2:]:
                    pass
                else:
                    start = idx
                    prev_label = label[2:]
        if start >= 0 and prev_label != "O":
            self.__add_annotation(
                text,
                start,
                len(tokens),
                offset,
                tokens,
                annotation_type,
                prev_label,
            )

    def tag(self, doc: Document, tasks: Set[str] | None = None):
        if tasks is not None and len(tasks) == 0:
            return

        sentences, tokens, token_strs = doc.text.tag_data()
        for batch in partition(token_strs, config.INFERENCE_BATCH_SIZE):
            outputs = self.model.tag(
                language=doc.language, texts=batch, annotation_types=tasks
            )
            for output in outputs:
                for sentence, sentence_tokens, labels in zip(
                    sentences, tokens, output.label
                ):
                    if output.task == "bio":
                        self.__process_bio_tags(
                            doc.text,
                            sentence.start,
                            sentence_tokens,
                            output.type,
                            labels,
                        )
                    elif output.task == "clf":
                        sentence.metadata[output.type] = labels
                        pass
                    else:
                        print(f"Unknown task: {output.task}", file=sys.stderr)
