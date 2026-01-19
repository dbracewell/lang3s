# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True

from typing import List, TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from lang3s.utils import filter_none

if TYPE_CHECKING:
    from .text_annotation import TextAnnotation
    from .text import Text
    from .event import Event

from . import AnnotationTypes
from .list_metadata cimport ListMetadata
from .metadata import Metadata

cdef tuple start_end_key(a):
    return a.start, a.end

cdef class TextObject:

    def __init__(self, id:str, doc_id:str, text: str):
        self._embedding = np.zeros(0)
        self._meta = ListMetadata()
        self.id = id
        self.doc_id = doc_id
        self.text = text

    def __str__(self):
        return self.text

    def __repr__(self):
        return self.text

    def __eq__(self, other):
        if isinstance(other, TextObject):
            return self.id == other.id
        return False

    def __iter__(self) -> List["TextAnnotation"]:
        return self.get_tokens()

    def __hash__(self):
        return hash(self.id)

    def __contains__(self, item):
        return self._meta.get(item, None) is not None

    def __setitem__(self, str key, object value):
        self._meta.set(key, value)

    def __delitem__(self, str key):
        self._meta.set(key, None)

    def __getitem__(self, str item):
        return self._meta.get(item, None)

    cpdef object get(self, str metadata_key, object default_value=None):
        return self._meta.get(metadata_key, default_value)

    cdef list get_sentences(self):
        raise NotImplementedError("must be defined by subclass")

    cdef list get_tokens(self):
        raise NotImplementedError("must be defined by subclass")

    property tokens:
        def __get__(self) -> List["TextAnnotation"]:
            return self.get_tokens()  #type: ignore

    property sentences:
        def __get__(self)-> List["TextAnnotation"]:
            return self.get_sentences()  #type: ignore

    cdef object get_embedding(self):
        return self._embedding

    cdef set_embedding(self, object value):
        self._embedding = value

    property embedding:
        def __get__(self) -> NDArray[np.floating]:
            return self.get_embedding()

        def __set__(self, value: NDArray[np.floating]):
            self.set_embedding(value)

    cdef int get_start(self):
        raise NotImplementedError("start must be implemented")

    property start:
        def __get__(self) -> int:
            return self.get_start()

    cdef int get_end(self):
        raise NotImplementedError("end must be implemented")

    property end:
        def __get__(self) -> int:
            return self.get_end()

    cdef bint _is_stopword(self):
        raise NotImplementedError("_is_stopword must be implemented")

    property is_stopword:
        def __get__(self) -> bool:
            return self._is_stopword()  #type: ignore

    cdef str get_lemma(self):
        lemma_str = self[Metadata.LEMMA.value]
        if lemma_str is not None:
            return lemma_str
        return " ".join([t.lemma for t in self.get_tokens()])  #type: ignore

    property lemma:
        def __get__(self) -> str:
            return self.get_lemma()  #type: ignore

    cdef object get_owner(self):
        raise NotImplementedError("owner must be implemented")

    property owner:
        def __get__(self) -> "Text":
            return self.get_owner()

    property entities:
        def __get__(self) -> List["TextAnnotation"]:
            return self.annotations_of_type(AnnotationTypes.ENTITY.value)  #type: ignore

    property noun_chunks:
        def __get__(self) -> List["TextAnnotation"]:
            return self.annotations_of_type(AnnotationTypes.NOUN_CHUNK.value)  #type: ignore

    cdef list get_events(self):
        from .event import Event
        cdef list events = []
        cdef list triggers = self.annotations_of_type(AnnotationTypes.EVENT.value)  #type: ignore
        for trigger in triggers:  #type: ignore
            a0 = trigger[Metadata.A0.value] or []
            a1 = trigger[Metadata.A1.value] or []
            loc = self.owner.get_annotation(trigger[Metadata.LOC.value])
            time = self.owner.get_annotation(trigger[Metadata.TIME.value])
            events.append(
                Event(
                    trigger=trigger,
                    a0=filter_none(
                        self.owner.get_annotation(aid) for aid in a0
                    ),
                    a1=filter_none(
                        self.owner.get_annotation(aid) for aid in a1
                    ),
                    time=time,
                    loc=loc,
                )
            )
        return events

    property events:
        def __get__(self) -> List["Event"]:
            return self.get_events()  #type: ignore

    cpdef list annotations_of_type(self, str t):
        raise NotImplementedError("annotations_of_type must be implemented")

    cpdef list interleave(self, str annotation_type):
        """
        Extremely optimized version of Python’s interleave method.
        Merges sorted tokens + sorted annotations of a given type.
        """
        cdef list anns = self.annotations_of_type(annotation_type)
        if not anns:
            return self.get_tokens()

        cdef list toks = self.get_tokens()
        anns = sorted(anns, key=start_end_key)
        toks = sorted(toks, key=start_end_key)

        cdef list out = []
        cdef int ti = 0
        cdef int ai = 0
        cdef int nt = len(toks)
        cdef int na = len(anns)
        cdef object tok, ann

        while ti < nt or ai < na:
            if ai >= na:
                out.extend(toks[ti:])
                break

            tok = toks[ti]
            ann = anns[ai]

            if ann.start <= tok.start:
                out.append(ann)
                ai += 1
                # skip tokens covered by annotation
                while ti < nt and toks[ti].start < ann.end:
                    ti += 1
            else:
                out.append(tok)
                ti += 1

        return out

    cpdef bint overlaps(self, TextObject other):
        if self.doc_id != other.doc_id:
            return False
        return self.start < other.end and self.end > other.start

    cpdef str to_string(
        self,
        bint ignore_stopwords,
        bint lemmatize,
        bint lowercase
    ):
        cdef list output = []
        for token in self.get_tokens():  #type:ignore
            token_str = token.text
            if ignore_stopwords and token.is_stopword:
                continue
            if lemmatize:
                token_str = token[Metadata.LEMMA.value]
            if lowercase:
                token_str = token_str.lower()
            output.append(token_str)
        return " ".join(output)
