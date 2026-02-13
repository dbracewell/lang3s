from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple, override

import numpy as np
import shortuuid
from numpy.typing import NDArray
from psycopg.types.json import Jsonb

from lang3s import config

from .db_columns import TextRow
from .metadata import AnnotationTypes
from .text_annotation import TextAnnotation
from .text_object import TextObject


class Text(TextObject):
    __slots__ = ("_annotations", "_tokens", "_sentences", "keywords", "__weakref__")

    def __init__(
        self,
        *,
        doc_id: str,
        content: str,
        id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[NDArray[np.floating]] = None,
    ):
        TextObject.__init__(
            self,
            id=id,
            text=content,
            doc_id=doc_id,
            metadata=dict(),
            embedding=embedding
            if embedding is not None
            else np.zeros(config.SEMANTIC_EMBEDDING_DIMENSION, dtype=np.float32),
        )
        if metadata is not None:
            self.metadata.update(metadata)
        self._tokens: List[TextAnnotation] = []
        self._sentences: List[TextAnnotation] = []
        self.keywords: List[Tuple[str, np.ndarray]] = []
        self._annotations: List[TextAnnotation] = []

    @property
    @override
    def tokens(self) -> List[TextAnnotation]:
        return self._tokens

    @property
    @override
    def sentences(self) -> List[TextAnnotation]:
        return self._sentences

    @property
    @override
    def sentence(self) -> TextAnnotation:
        return self._sentences[0]

    @property
    def annotations(self) -> List[TextAnnotation]:
        return self._annotations

    def get_annotation(self, annotation_id: str) -> "TextAnnotation | None":
        """
        Return the first annotation (token, sentence, or other) with the given id.
        """
        for token in self._tokens:
            if token.id == annotation_id:
                return token
        for sentence in self._sentences:
            if sentence.id == annotation_id:
                return sentence
        for a in self.annotations:
            if a.id == annotation_id:
                return a
        return None

    @property
    def is_stopword(self) -> bool:
        return False

    @property
    def lemma(self) -> str:
        return " ".join(t.lemma for t in self._tokens)

    @property
    def owner(self) -> Text:
        return self

    def annotations_of_type(self, annotation_type: str) -> List[TextAnnotation]:
        if annotation_type == AnnotationTypes.TOKEN.value:
            return self._tokens
        elif annotation_type == AnnotationTypes.SENTENCE.value:
            return self._sentences
        to_return = []
        for annotation in self._annotations:
            if annotation.type == annotation_type:
                to_return.append(annotation)
        return to_return

    def remove_annotations(
        self, sources: List[str] | None = None, types: List[str] | None = None
    ) -> None:
        source_set = set(sources or [])
        types_set = set(types or [])
        remaining = []
        for ann in self._annotations:
            if ann.source in source_set or ann.type in types_set:
                ann.detach()
                del ann
            else:
                remaining.append(ann)
        self._annotations = remaining
        for ann in self._annotations:
            ann._annotations = None
            ann._tokens = None

    def detach(self):
        if self._tokens is not None:
            for token in self._tokens:
                token.detach()
                del token
        if self._sentences is not None:
            for sentence in self._sentences:
                sentence.detach()
                del sentence
        if self._annotations is not None:
            for annotation in self._annotations:
                annotation.detach()
                del annotation
        self._tokens.clear()
        self._sentences.clear()
        self._annotations.clear()
        self.embedding = None
        self.metadata.clear()
        self.keywords.clear()

    @property
    def all_annotations(self) -> List[TextAnnotation]:
        return self._annotations + self._tokens + self._sentences

    def tag_data(self):
        sentences = []
        tokens = []
        token_strs = []

        for sent in self._sentences:
            sentences.append(sent)
            tokens.append(sent.tokens)
            token_strs.append([tok.text for tok in sent.tokens])  # type: ignore

        return sentences, tokens, token_strs

    def insert_values(self):
        emb = self.embedding
        arr = emb
        if not isinstance(emb, np.ndarray):
            arr = np.array(emb, dtype=np.float32)
        return TextRow(
            id=self.id,
            text=self.text,
            doc_id=self.doc_id,
            embedding=arr,
            metadata=Jsonb(self.metadata),  # type: ignore
        )

    def to_json(self):
        emb = self.embedding
        if isinstance(emb, np.ndarray):
            emb = emb.tolist()

        return {
            "id": self.id,
            "text": self.text,
            "embedding": emb,
            "metadata": self.metadata,
            "annotations": [a.to_json() for a in self.all_annotations],
        }

    @staticmethod
    def from_json(obj: Dict[str, Any]) -> "Text":
        text_dict = obj["text"]

        embedding = text_dict.get("embedding")
        if isinstance(embedding, str):
            embedding = np.array(json.loads(embedding))
        elif isinstance(embedding, list):
            embedding = np.array(embedding)

        text = Text(
            id=text_dict["id"],
            metadata=text_dict.get("metadata", {}),
            content=text_dict["text"],
            doc_id=obj["id"],
            embedding=embedding,
        )

        for annotation in text_dict.get("annotations", []):
            emb = annotation.get("embedding")
            if emb is not None:
                if isinstance(emb, str):
                    emb = np.array(json.loads(emb), dtype=np.float16)
                elif isinstance(emb, list):
                    emb = np.array(emb, dtype=np.float16)

            text.add_annotation(
                id=annotation["id"],
                text=annotation["text"],
                start=annotation["start"],
                end=annotation["end"],
                sentence_id=annotation["sentence_id"],
                type=annotation["type"],
                value=annotation["value"],
                embedding=emb,
                metadata=annotation.get("metadata", {}),
            )

        text._tokens = sorted(text._tokens, key=lambda token: token.start)
        text._sentences = sorted(text._sentences, key=lambda s: s.start)
        return text

    def add_annotation(
        self,
        text: str,
        start: int,
        end: int,
        sentence_id: int,
        type: str,
        value: str,
        id: str | None = None,
        source: str = "UNKNOWN",
        embedding: np.ndarray | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> TextAnnotation:
        annotation = TextAnnotation(
            owner=self,
            id=id,
            text=text,
            start=start,
            end=end,
            source=source,
            sentence_id=sentence_id,
            type=type,
            value=value,
            embedding=embedding,
            metadata=metadata,
        )
        if annotation.type == AnnotationTypes.TOKEN.value:
            self._tokens.append(annotation)
            self.end = len(self._tokens)
        elif annotation.type == AnnotationTypes.SENTENCE.value:
            self._sentences.append(annotation)
        else:
            self._annotations.append(annotation)
        return annotation

    def attach_annotation(self, annotation) -> TextAnnotation:
        """
        Attach an existing TextAnnotation if not already present.
        """
        if self.get_annotation(annotation.id) is not None:  # type: ignore
            return annotation
        if annotation.type == AnnotationTypes.TOKEN.value:
            self._tokens.append(annotation)
        elif annotation.type == AnnotationTypes.SENTENCE.value:
            self._sentences.append(annotation)
        else:
            self._annotations.append(annotation)
        return annotation

    def create_span(
        self,
        start: int,
        end: int,
        source: str,
        type: str | None = None,
        value: str | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> TextAnnotation:
        """
        Create a new span annotation covering tokens[start:end].
        Span is NOT automatically added to self.annotations.
        """
        span_tokens = self._tokens[start:end]

        annotation = TextAnnotation(
            id=shortuuid.uuid(),
            owner=self,
            text=self.text[span_tokens[0]["start_char"] : span_tokens[-1]["end_char"]],
            start=start,
            end=end,
            source=source,
            sentence_id=min((t.sentence_id for t in span_tokens)),
            type=type if type is not None else "span",
            value=value if value is not None else "",
            metadata=metadata,
        )
        return annotation
