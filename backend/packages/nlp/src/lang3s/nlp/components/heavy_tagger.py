from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from lang3s.core.typing_extras import SingletonMeta
from lang3s.nlp.models.task_transformer import MultiTaskTransformer

if TYPE_CHECKING:
    from lang3s.data.schemas import Document, TextAnnotation
    from lang3s.nlp.components.embedder import EmbeddingResult
    from lang3s.nlp.models.task_transformer.typedefs import TokenLabelResult


class HeavyTagger(metaclass=SingletonMeta):
    def __init__(self):
        self.transformer = MultiTaskTransformer()

    def tag(
        self,
        doc: Document,
        embeddings: EmbeddingResult,
        tasks: Iterable[str] | None,
    ):
        tagger = MultiTaskTransformer()
        outputs = tagger.forward(
            embeddings,
            language=doc.language,
            tasks=tasks,
        )

        for source_name, output in outputs.items():
            if output.task_type.is_sentence_level():
                for label_tuple, sentence in zip(output.labels, doc.text.sentences):
                    label, prob = label_tuple
                    if label and len(label) > 0:
                        sentence[output.annotation_type] = {
                            "value": label,
                            "source": source_name,
                            "confidence": prob,
                        }

            else:
                all_labels: TokenLabelResult = output.labels  # type: ignore
                for sentence, sentence_labels in zip(doc.text.sentences, all_labels):
                    for label, start, end in sentence_labels:
                        self._add_token_span(
                            start=start,
                            end=end,
                            sentence=sentence,
                            annotation_type=output.annotation_type,
                            source_name=source_name,
                            label=label,
                            doc=doc,
                        )

    def _add_token_span(
        self,
        start: int | None,
        end: int,
        doc: Document,
        sentence: TextAnnotation,
        annotation_type: str,
        source_name: str,
        label: str | None,
    ):
        if start and label:
            doc.text.add_annotation(
                content=" ".join([t.content for t in sentence.tokens[start:end]]),
                start=start + sentence.start,
                end=end + sentence.start,
                sentence_index=sentence.sentence_index,
                type_=annotation_type,
                source=source_name,
                value=label,
            )


heavy_tagger = HeavyTagger()
