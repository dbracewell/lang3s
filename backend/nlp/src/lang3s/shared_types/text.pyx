# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True

import itertools
import json
from typing import Any, Dict, Optional, List

import numpy as np
import shortuuid
from numpy.typing import NDArray
from psycopg.types.json import Jsonb

from .db_columns import TextRow
from .metadata import AnnotationTypes
from .text_annotation import TextAnnotation
from .text_object cimport TextObject
from ..maths import binarize

cdef class Text(TextObject):
    def __cinit__(self):
        # TextObject.__cinit__ already sets embedding and _meta
        self._annotations = []
        self._tokens = []
        self._sentences = []

    def __init__(
        self,
        doc_id: str,
        content: str,
        id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[NDArray[np.floating]] = None,
    ):
        # readonly attributes come from TextObject .pxd
        self.text = content  #type:ignore
        self.id = id if id is not None else shortuuid.uuid()
        self.doc_id = doc_id

        if embedding is not None:
            self._embedding = embedding

        if metadata is not None:
            self._meta.update(metadata)  #type:ignore

        self._annotations = []
        self._tokens = []
        self._sentences = []

    cdef list get_tokens(self):
        return self._tokens

    cdef list get_sentences(self):
        return self._sentences

    property annotations:
        def __get__(self) -> List[TextAnnotation]:
            return self._annotations

    cdef int get_start(self):
        cdef int n = len(self._tokens)
        if n:
            return (<object> self._tokens[0]).start
        return 0

    cdef int get_end(self):
        cdef int n = len(self._tokens)
        if n:
            return (<object> self._tokens[n - 1]).end
        return 0

    cdef bint _is_stopword(self):
        return False

    cpdef list annotations_of_type(self, str annotation_type):
        cdef list out = []
        cdef object ann
        for ann in self._annotations:
            if ann.type == annotation_type:
                out.append(ann)
        return out

    cdef object get_owner(self):
        return self

    cpdef object get_annotation(self, str id):
        """
        Return the first annotation (token, sentence, or other) with the given id.
        """
        if id is None:
            return None
        for token in self._tokens:
            if token.id == id:
                return token
        for sentence in self._sentences:
            if sentence.id == id:
                return sentence
        for annotation in self._annotations:
            if annotation.id == id:
                return annotation
        return None

    property all_annotations:
        def __get__(self) -> List[TextAnnotation]:
            return list(
                itertools.chain.from_iterable(
                    [self._tokens, self._sentences, self._annotations]
                )
            )

    cpdef void remove_annotations(self, list sources):
        cdef list filtered = []
        for annotation in self._annotations:
            if annotation.source not in sources:
                filtered.append(annotation)
        self._annotations = filtered  #type:ignore

    def tag_data(self):
        cdef list sentences = []
        cdef list tokens = []
        cdef list token_strs = []
        cdef object sent, tok

        for sent in self._sentences:
            sentences.append(sent)
            tokens.append(sent.tokens)
            token_strs.append([tok.text for tok in sent.tokens])  #type: ignore

        return sentences, tokens, token_strs

    def insert_values(self):
        cdef object emb = self._embedding
        cdef object arr

        if emb is None:
            arr = np.zeros(0, dtype=np.float32)

        elif isinstance(emb, np.ndarray):
            arr = emb
        else:
            arr = np.array(emb, dtype=np.float32)

        return list(TextRow(
            id=self.id,
            text=self.text,
            doc_id=self.doc_id,
            embedding=binarize(arr),
            full_embedding=arr,
            metadata=Jsonb(self._meta.to_dict()),  #type: ignore
        ))

    def to_json(self):
        cdef object emb = self._embedding
        if isinstance(emb, np.ndarray):
            emb_list = emb.tolist()
        else:
            emb_list = emb

        return {
            "id": self.id,
            "text": self.text,
            "embedding": emb_list,
            "metadata": self._meta.to_dict(),  #type:ignore
            "annotations": [
                a.to_json()
                for a in self.all_annotations
            ],
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
        int start,
        int end,
        int sentence_id,
        str type,
        str value,
        str id=None,
        str source="UNKNOWN",
        object embedding=None,
        dict metadata=None,
    ) -> TextAnnotation:
        annotation = TextAnnotation(
            id=id if id is not None else shortuuid.uuid(),
            owner=self,
            text=text,
            start=start,
            end=end,
            source=source,  #type:ignore
            sentence_id=sentence_id,
            type=type,  #type: ignore
            value=value,  #type: ignore
            embedding=embedding,
            metadata=metadata,  #type:ignore
        )

        if annotation.type == AnnotationTypes.TOKEN.value:
            self._tokens.append(annotation)
        elif annotation.type == AnnotationTypes.SENTENCE.value:
            self._sentences.append(annotation)
        else:
            self._annotations.append(annotation)
        return annotation

    def attach_annotation(self, annotation) -> TextAnnotation:
        """
        Attach an existing TextAnnotation if not already present.
        """
        if self.get_annotation(annotation.id) is not None:  #type: ignore
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
        int start,
        int end,
        str source,
        str type=None,
        str value=None,
        dict metadata=None,
    ) -> TextAnnotation:
        """
        Create a new span annotation covering tokens[start:end].
        Span is NOT automatically added to self.annotations.
        """
        cdef list span_tokens = self._tokens[start:end]
        cdef object t

        annotation = TextAnnotation(
            id=shortuuid.uuid(),
            owner=self,
            text=" ".join((t.text for t in span_tokens)),  #type:ignore
            start=start,
            end=end,
            source=source,  #type: ignore
            sentence_id=min((t.sentence_id for t in span_tokens)),  #type: ignore
            type=type if type is not None else "span",
            value=value if value is not None else "",
            metadata=metadata,  #type: ignore
        )
        return annotation
