import sys
from typing import List, Set

import lang3s.config as config
from lang3s.models.adapter import AdapterModel
from lang3s.types import Document, Text, TextAnnotation
from lang3s.utils import partition


class AdapterModelTagger:
    def __init__(self) -> None:
        self.model = AdapterModel()

    def __add_annotation(
        self,
        text: Text,
        start: int,
        end: int,
        offset: int,
        sentence_id: int,
        tokens: List[TextAnnotation],
        annotation_type: str,
        label: str,
    ):
        text.add_annotation(
            start=start + offset,
            end=end + offset,
            value=label,
            sentence_id=sentence_id,
            text=" ".join([tokens[i].text for i in range(start, end)]),
            type=annotation_type,
        )

    def __process_bio_tags(
        self,
        text: Text,
        offset: int,
        sentence_id: int,
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
                        sentence_id,
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
                        sentence_id,
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
                sentence_id,
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
                            sentence.sentence_id,
                            sentence_tokens,
                            output.type,
                            labels,
                        )
                    elif output.task == "clf":
                        sentence.metadata[output.type] = labels
                        pass
                    else:
                        print(f"Unknown task: {output.task}", file=sys.stderr)
