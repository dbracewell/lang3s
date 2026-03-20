from __future__ import annotations

import itertools
import weakref
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import numpy as np
from psycopg.types.json import Jsonb

from lang3s import config
from lang3s.nlp.metadata import AnnotationTypes, Metadata

from ...utils import flatten
from ..language import uses_whitespace
from .db_columns import TextAnnotationRow
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

    @property
    def is_eventive(self):
        return len(self.get(Metadata.A1, [])) > 0 or len(self.get(Metadata.A0, [])) > 0

    def __ensure_tokens(self):
        if self._tokens is None:
            self._tokens = []
            self._tokens.extend(self._owner_ref().tokens[self.start : self.end])

    def __ensure_annotations(self):
        if self._annotations is None:
            self._annotations = defaultdict(list)
            owner = self._owner_ref()

            # if self.type != AnnotationTypes.TOKEN:
            #     self._annotations[self.type].append(self)

            for a in owner.annotations:
                if self.overlaps(a):  # type:ignore
                    self._annotations[a.type].append(a)
            for a in owner.sentences:
                if self.overlaps(a):  # type:ignore
                    self._annotations[a.type].append(a)

    @property
    def annotations(self) -> List["TextAnnotation"]:
        self.__ensure_annotations()
        return flatten(self._annotations.values())

    def text_with_coref(self):
        parts = ""
        last_start = self.tokens[0]["start_char"]
        need_whitespace = uses_whitespace(self.owner["language"])
        for token in self.tokens:
            coref = token.coref
            if need_whitespace:
                parts += " " * (token["start_char"] - last_start)
                last_start = token["end_char"]
            parts += coref.text

        return parts.strip()

    @property
    def tokens(self) -> List[TextAnnotation]:
        if self.type == AnnotationTypes.TOKEN:
            return [self]
        self.__ensure_tokens()
        return self._tokens

    def annotations_of_type(self, annotation_type: str) -> List[TextAnnotation]:
        if annotation_type == AnnotationTypes.TOKEN:
            return self.tokens
        self.__ensure_annotations()
        return self._annotations.get(annotation_type, [])

    @property
    def owner(self) -> "Text":
        owner = self._owner_ref()
        if owner is None:
            raise RuntimeError("Owner Text has already been deleted")
        return owner

    @property
    def is_stopword(self) -> bool:
        v = self.metadata.get(Metadata.IS_STOPWORD, None)
        if v is not None:
            return v

        if self.type == AnnotationTypes.TOKEN:
            return False

        return all(t.is_stopword for t in self.tokens)

    def clear_cache(self):
        if self.type == AnnotationTypes.TOKEN:
            if self._annotations:
                for other in itertools.chain.from_iterable(self._annotations.values()):
                    other.clear_cache()
        self._tokens = None
        self._annotations = None

    @property
    def parent(self) -> Optional[TextAnnotation]:
        if self.type == AnnotationTypes.TOKEN:
            head = self.metadata.get(Metadata.HEAD, None)
            if head is None or head == self.start:
                return None
            return self.owner.tokens[head]

        span_set = set((token.start for token in self.tokens))
        for token in self.tokens:
            head = token.metadata.get(Metadata.HEAD, None)
            if head is not None and (head not in span_set or head == token.start):
                return self.owner.tokens[head]
        return None

    @property
    def head(self) -> TextAnnotation:
        if self.type == AnnotationTypes.TOKEN:
            return self

        span_set = set((token.start for token in self.tokens))
        for token in self.tokens:
            head = token.metadata.get(Metadata.HEAD, None)
            if head is not None and (head not in span_set or head == token.start):
                return token
        return self.tokens[-1]

    @property
    def children(self) -> List[TextAnnotation]:
        children: List[TextAnnotation] = []
        if self.type == AnnotationTypes.TOKEN:
            for token in self.sentence.tokens:
                if token[Metadata.HEAD] == self.start and token.id != self.id:
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
        coref_id = self.metadata.get(Metadata.COREF)
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
        lemma_str = self.metadata.get(Metadata.LEMMA, None)
        if lemma_str is None:
            if self.type == AnnotationTypes.TOKEN:
                return self.text.lower()
            lemma_str = " ".join(t.lemma for t in self.tokens)
        return lemma_str

    @property
    def normalized_text(self) -> str:
        if self.type == AnnotationTypes.SENTENCE:
            return self.text
        return (
            self.metadata.get(Metadata.COREF_TEXT)
            or self.metadata.get(Metadata.LEMMA)
            or self.text
        ).upper()

    def previous_token(self) -> Optional[TextAnnotation]:
        if self.start == 0:
            return None
        return self.owner.tokens[self.start - 1]

    def next_token(self) -> Optional[TextAnnotation]:
        if self.end == len(self.owner.tokens):
            return None
        return self.owner.tokens[self.end]

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

        normalized_text = self.normalized_text

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
    def mapping(self) -> str:
        return f"{self.type}:{self.value}"

    @property
    def dep(self):
        if self.type == AnnotationTypes.TOKEN:
            return self.metadata.get(Metadata.RELATION, "ROOT")
        parent = self.parent
        if parent is None:
            return "ROOT"
        return parent.metadata.get(Metadata.RELATION, "ROOT")

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
