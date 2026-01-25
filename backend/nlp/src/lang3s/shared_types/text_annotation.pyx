# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
import weakref
from typing import Any, Dict, Optional, List

import numpy as np
from numpy.typing import NDArray
from psycopg.types.json import Jsonb

from . import AnnotationTypes
from .db_columns import TextAnnotationRow
from .metadata import Metadata
from .text cimport Text
from .text_object cimport TextObject


cdef class TextAnnotation(TextObject):
    def __init__(
        self,
        id: str,
        owner: Text,
        text: str,
        int start,
        int end,
        int sentence_id,
        str type,
        str value,
        str source,
        embedding: Optional[NDArray[np.floating]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        TextObject.__init__(self, id=id, text=text,doc_id=owner.doc_id)
        self._start = start
        self._end = end
        self.source = source
        self._owner_ref = weakref.ref(owner)
        self.type = type
        self.sentence_id = sentence_id
        self.value = value

        if embedding is not None:
            self._embedding = embedding

        if metadata is not None:
            self._meta.update(metadata)  #type: ignore

    property source:
        def __get__(self) -> str:
            return self.source

        def __set__(self, value: str):
            self.source = value

    property type:
        def __get__(self) -> str:
            return self.type
        def __set__(self, value: str):
            self.type = value

    property value:
        def __get__(self) -> str:
            return self.value
        def __set__(self, value: str):
            self.value = value

    cdef int get_start(self):
        return self._start

    cdef int get_end(self):
        return self._end

    cdef list get_tokens(self):
        cdef object generic_owner = self.owner
        cdef Text owner_doc = <Text> generic_owner

        if self.type == AnnotationTypes.TOKEN.value:
            return [self]

        cdef list toks = []
        cdef object tok

        for tok in owner_doc._tokens[self._start:self._end]:
            toks.append(tok)
        return toks


    cdef list get_sentences(self):
        cdef object generic_owner = self.owner
        cdef Text owner_doc = <Text> generic_owner

        if self.type == AnnotationTypes.SENTENCE.value:
            return [self]

        for s in owner_doc._sentences:
            if s.start < self.get_end() and s.end > self.get_start():
                return [s]

        raise Exception("No sentence found")

    cpdef list annotations_of_type(self, str type):
        cdef object generic_owner = self.owner
        cdef Text owner_doc = <Text> generic_owner


        cdef list out = []
        cdef object a

        if self.type == type:
            out.append(self)
            return out

        for a in owner_doc._annotations:
            if a.type == type and self.overlaps(a):
                out.append(a)
        return out

    cdef object get_owner(self):
        cdef object obj = self._owner_ref()
        if obj is None:
            raise RuntimeError("Owner Text has already been deleted")
        return obj

    cdef bint _is_stopword(self):
        cdef object v = self[Metadata.IS_STOPWORD.value]
        if v is not None:
            return <bint> v

        if self.type != AnnotationTypes.TOKEN.value:
            # all tokens must be stopwords
            for tok in self.get_tokens():  #type: ignore
                if not tok.is_stopword:
                    return False
            return True

        # token-level default
        return False

    cdef object get_parent(self):
        """
        Dependency parent based on HEAD metadata.
        """
        cdef object head
        cdef set span_set
        cdef object token

        if self.type == AnnotationTypes.TOKEN.value:
            head = self[Metadata.HEAD.value]
            if head == self.get_start():
                return None
            return self.owner.tokens[head]

        # span-level parent: find token whose head is outside span
        span_set = set((token.start for token in self.gettokens()))  #type: ignore
        for token in self.gettokens():  #type: ignore
            head = token[Metadata.HEAD.value]
            if head not in span_set or head == token.start:
                return self.owner.tokens[head]

        return None

    property parent:
        def __get__(self) -> Optional[TextAnnotation]:
            return self.get_parent()

    cdef list get_subtree(self):
        """
        All descendants in the dependency tree starting from this span.
        """
        cdef set ancestors = set()
        cdef set visited = set()
        cdef list horizon = [self]
        cdef TextAnnotation n
        cdef list children

        while horizon:
            n = horizon.pop()
            if n.get_start() not in visited:  #type:ignore
                children = n.get_children()  #type: ignore
                ancestors.update(children)  #type: ignore
                horizon.extend(children)
                visited.add(n.get_start())  #type:ignore
        return list(ancestors)

    property subtree:
        def __get__(self) -> List[TextAnnotation]:
            return self.get_subtree()  #type: ignore

    cdef list get_children(self):
        cdef list children = []
        cdef object token

        if self.type == AnnotationTypes.TOKEN.value:
            for token in self.owner.tokens:
                if token[Metadata.HEAD.value] == self.get_start():
                    children.append(token)
            return children

        for token in self.gettokens():  #type: ignore
            children.extend(token.children)
        return children

    property children:
        def __get__(self) -> List[TextAnnotation]:
            return self.get_children()  #type: ignore

    cdef object get_coref(self):
        cdef object coref_id = self._meta.get(Metadata.COREF.value, None)  #type:ignore
        cdef object ann
        if coref_id is None:
            return self
        for ann in self.owner._annotations:
            if ann.id == coref_id:
                return ann
        return self

    property coref:
        def __get__(self) -> TextAnnotation:
            return self.get_coref()

    # ------------------------------------------------------------------
    # DB insertion / dep / sentence
    # ------------------------------------------------------------------
    def insert_values(self):
        cdef object emb = self._embedding
        cdef object arr

        if emb is None:
            arr = np.zeros(0, dtype=np.float32)
        elif isinstance(emb, np.ndarray):
            arr = emb
        else:
            arr = np.array(emb, dtype=np.float32)

        sent: TextAnnotation = self.sentence

        normalized_text = self._meta.get(Metadata.COREF_TEXT.value,
                                         self._meta.get(Metadata.LEMMA.value,
                                                        self.text
                                                        )).upper()


        return list(TextAnnotationRow(
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
            normalized_text=normalized_text if len(normalized_text) < 1000 else normalized_text[:1000],
            mapping=f"{self.type}:{self.value}"
            if self.type not in ["sentence", "noun_chunk"]
            else None,
            embedding=arr,
            metadata=Jsonb(self._meta.to_dict())  #type:ignore
        ))

    def metadata(self):
        return self._meta.to_dict()

    property dep:
        def __get__(self):
            cdef TextAnnotation parent
            if self.type == AnnotationTypes.TOKEN.value:
                return self._meta.get(Metadata.RELATION.value, "ROOT")  #type:ignore
            parent = self.get_parent()
            if parent is None:
                return "ROOT"
            return parent._meta.get(Metadata.RELATION.value, "ROOT")  #type: ignore

    property sentence:
        def __get__(self) -> TextAnnotation:
            if self.type == AnnotationTypes.SENTENCE.value:
                return self
            cdef list sentences = self.get_sentences()
            if len(sentences) == 0:
                raise Exception("No sentence found")
            return sentences[0]  #type: ignore

    def to_json(self) -> Dict[str, Any]:
        cdef object emb = self._embedding
        if isinstance(emb, np.ndarray):
            emb_list = emb.tolist()
        else:
            emb_list = emb

        return {
            "id": self.id,
            "text": self.text,
            "start": self.get_start(),
            "end": self.get_end(),
            "type": self.type,
            "value": self.value,
            "source": self.source,
            "sentence_id": self.sentence_id,
            "embedding": emb_list if emb is not None else None,
            "metadata": self._meta.to_dict(),  #type: ignore
        }

    cpdef void detach(self):
        self._owner_ref = None
        self._embedding = None
        self._meta = None
        self.source = None
        self.type = None
        self.value = None