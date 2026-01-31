from __future__ import annotations

import weakref
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import numpy as np
from psycopg.types.json import Jsonb

from lang3s import config

from .db_columns import TextAnnotationRow
from .metadata import AnnotationTypes, Metadata
from .text_object import TextObject

if TYPE_CHECKING:
    from .text import Text


class TextAnnotation(TextObject):
    __slots__ = (
        "sentence_id",
        "type",
        "value",
        "source",
        "_owner_ref",
        "_tokens",
        "_annotations",
    )

    def __init__(
        self,
        *,
        owner: "Text",
        id: Optional[str] = None,
        text: str,
        start: int,
        end: int,
        sentence_id: int,
        type: str,
        value: str,
        source: str,
        embedding: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            id=id,
            text=text,
            doc_id=owner.doc_id,
            metadata=dict(),
            embedding=embedding
            if embedding is not None
            else np.zeros(config.SEMANTIC_EMBEDDING_DIMENSION, dtype=np.float32),
            start=start,
            end=end,
        )
        self._owner_ref: weakref.ReferenceType["Text"] = weakref.ref(owner)
        self._tokens: List[TextAnnotation] | None = None
        self._annotations: Dict[str, List[TextAnnotation]] | None = None
        self.sentence_id = sentence_id
        self.type = type
        self.value = value
        self.source = source
        if metadata is not None:
            self.metadata.update(metadata)

    def __ensure_tokens(self):
        if self._tokens is None:
            self._tokens = []
            self._tokens.extend(self._owner_ref().tokens[self.start : self.end])

    def __ensure_annotations(self):
        if self._annotations is None:
            self._annotations = defaultdict(list)
            owner = self._owner_ref()
            if self.type != AnnotationTypes.TOKEN.value:
                self._annotations[self.type].append(self)
            for a in owner.annotations:
                if self.overlaps(a):  # type:ignore
                    self._annotations[a.type].append(a)
            for a in owner.sentences:
                if self.overlaps(a):  # type:ignore
                    self._annotations[a.type].append(a)

    @property
    def tokens(self) -> List[TextAnnotation]:
        if self.type == AnnotationTypes.TOKEN.value:
            return [self]
        self.__ensure_tokens()
        return self._tokens

    def annotations_of_type(self, annotation_type: str) -> List[TextAnnotation]:
        if annotation_type == AnnotationTypes.TOKEN.value:
            return self.tokens
        self.__ensure_annotations()
        return self._annotations[annotation_type]

    @property
    def owner(self) -> "Text":
        owner = self._owner_ref()
        if owner is None:
            raise RuntimeError("Owner Text has already been deleted")
        return owner

    @property
    def is_stopword(self) -> bool:
        v = self.metadata.get(Metadata.IS_STOPWORD.value, None)
        if v is not None:
            return v

        if self.type == AnnotationTypes.TOKEN.value:
            return False

        return all(t.is_stopword for t in self.tokens)

    @property
    def parent(self) -> Optional[TextAnnotation]:
        if self.type == AnnotationTypes.TOKEN.value:
            head = self.metadata.get(Metadata.HEAD.value, None)
            if head is None or head == self.start:
                return None
            return self.owner.tokens[head]

        span_set = set((token.start for token in self.tokens))
        for token in self.tokens:
            head = token.metadata.get(Metadata.HEAD.value, None)
            if head is not None and (head not in span_set or head == token.start):
                return self.owner.tokens[head]
        return None

    @property
    def children(self) -> List[TextAnnotation]:
        children: List[TextAnnotation] = []
        if self.type == AnnotationTypes.TOKEN.value:
            for token in self.sentence.tokens:
                if token[Metadata.HEAD.value] == self.start and token.id != self.id:
                    children.append(token)
        else:
            for token in self.tokens:
                children.extend(token.children)

        return children

    @property
    def subtree(self) -> List[TextAnnotation]:
        out = set()
        stack = [self]
        visited = set()

        while stack:
            node = stack.pop()
            if node.start not in visited:
                children = node.children
                out.update(children)
                visited.add(node.start)
                stack.extend(children)

        return sorted(out, key=lambda x: x.start)

    @property
    def coref(self) -> TextAnnotation:
        coref_id = self.metadata.get(
            Metadata.COREF.value,
        )
        if coref_id is None:
            return self
        for ann in self.owner.annotations:
            if ann.id == coref_id:
                return ann
        return self

    @property
    def sentence_aid(self) -> str:
        return self.sentence.id

    @property
    def lemma(self) -> str:
        lemma_str = self.metadata.get(Metadata.LEMMA.value, None)
        if lemma_str is None:
            if self.type == AnnotationTypes.TOKEN.value:
                return self.text.lower()
            lemma_str = " ".join(t.lemma for t in self.tokens)
        return lemma_str

    def insert_values(self):
        if self.embedding is None:
            emb = np.zeros(config.SEMANTIC_EMBEDDING_DIMENSION, dtype=np.float32)
        else:
            emb = (
                self.embedding
                if isinstance(self.embedding, np.ndarray)
                else np.asarray(self.embedding, dtype=np.float32)
            )

        sent = self.sentence

        normalized_text = (
            self.metadata.get(Metadata.COREF_TEXT.value)
            or self.metadata.get(Metadata.LEMMA.value)
            or self.text
        ).upper()

        if len(normalized_text) > 1000:
            normalized_text = normalized_text[:1000]

        return TextAnnotationRow(
            id=self.id,
            text_id=self.owner.id,
            doc_id=self.doc_id,
            start=self.start,
            end=self.end,
            sentence_id=self.sentence_id,
            sentence_aid=sent.id,
            type=self.type,
            value=self.value,
            source=self.source,
            text=self.text,
            clean_text=self.to_string(True, True, True),
            normalized_text=normalized_text,
            mapping=(
                f"{self.type}:{self.value}"
                if self.type not in {"sentence", "noun_chunk"}
                else None
            ),
            embedding=emb,
            metadata=Jsonb(self.metadata),
        )

    @property
    def dep(self):
        if self.type == AnnotationTypes.TOKEN.value:
            return self.metadata.get(Metadata.RELATION.value, "ROOT")
        parent = self.parent
        if parent is None:
            return "ROOT"
        return parent.metadata.get(Metadata.RELATION.value, "ROOT")

    def to_json(self) -> Dict[str, Any]:
        emb = self.embedding
        if isinstance(emb, np.ndarray):
            emb = emb.tolist()
        return {
            "id": self.id,
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "type": self.type,
            "value": self.value,
            "source": self.source,
            "sentence_id": self.sentence_id,
            "embedding": emb,
            "metadata": self.metadata,
        }

    def detach(self):
        self.embedding = None  # type:ignore
        self.metadata.clear()
