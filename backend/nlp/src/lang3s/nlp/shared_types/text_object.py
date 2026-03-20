from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

import numpy as np
import shortuuid

from lang3s.nlp.metadata import AnnotationTypes, Metadata
from lang3s.utils import filter_none

if TYPE_CHECKING:
    from .event import Event
    from .text import Text
    from .text_annotation import TextAnnotation


def start_end_key(a) -> Tuple[int, int]:
    return a.start, a.end


class TextObject(abc.ABC):
    __slots__ = ("id", "doc_id", "text", "embedding", "start", "end", "metadata")

    def __init__(
        self,
        *,
        id: str | None,
        doc_id: str,
        text: str,
        embedding: np.ndarray,
        metadata: Dict[str, Any],
        start: int = 0,
        end: int = 0,
    ):
        self.id: str = id if id is not None else shortuuid.uuid()
        self.doc_id: str = doc_id
        self.text: str = text
        self.embedding: np.ndarray = embedding
        self.metadata: Dict[str, Any] = metadata
        self.start: int = start
        self.end: int = end

    def __str__(self):
        return self.text

    def __repr__(self):
        return self.text

    def __hash__(self):
        return hash(self.id)

    def __contains__(self, item: str):
        return item in self.metadata

    def __setitem__(self, key: str, value: Any):
        self.metadata[key] = value

    def __delitem__(self, key: str):
        if key in self.metadata:
            del self.metadata[key]

    def __getitem__(self, key: str):
        return self.metadata.get(key, None)

    def get(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)

    @property
    def tokens(self) -> List["TextAnnotation"]:
        return self.annotations_of_type(AnnotationTypes.TOKEN.value)

    @property
    def sentences(self) -> List["TextAnnotation"]:
        return self.annotations_of_type(AnnotationTypes.SENTENCE.value)

    @property
    def sentence(self) -> "TextAnnotation":
        sentences = self.annotations_of_type(AnnotationTypes.SENTENCE.value)
        if len(sentences) == 0:
            raise RuntimeError("No sentences found")
        return sentences[0]

    @property
    @abc.abstractmethod
    def is_stopword(self) -> bool:
        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def lemma(self) -> str:
        raise NotImplementedError()

    @property
    def entities(self) -> List["TextAnnotation"]:
        return self.annotations_of_type(AnnotationTypes.ENTITY.value)

    @property
    def noun_chunks(self) -> List["TextAnnotation"]:
        return self.annotations_of_type(AnnotationTypes.ENTITY.value)

    @abc.abstractmethod
    def annotations_of_type(self, annotation_type: str) -> List["TextAnnotation"]:
        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def owner(self) -> "Text":
        raise NotImplementedError()

    @property
    def annotations(self) -> List["TextAnnotation"]:
        return [a for a in self.owner.annotations if a.overlaps(self)]

    @property
    def frames(self) -> List["Event"]:
        from .event import Event

        events = []
        if getattr(self, "is_eventive", False):
            triggers = [self]
        else:
            triggers = [a for a in self.annotations if a.is_eventive]

        for trigger in triggers:
            a0 = trigger[Metadata.A0.value] or []
            a1 = trigger[Metadata.A1.value] or []
            loc = self.owner.get_annotation(trigger[Metadata.LOC.value])
            time = self.owner.get_annotation(trigger[Metadata.TIME.value])
            events.append(
                Event(
                    trigger=trigger,  # type:ignore
                    a0=filter_none(self.owner.get_annotation(aid) for aid in a0),
                    a1=filter_none(self.owner.get_annotation(aid) for aid in a1),
                    time=time,
                    loc=loc,
                )
            )
        return events

    def interleave(self, annotation_type: str) -> List["TextAnnotation"]:
        """
        Extremely optimized version of Python’s interleave method.
        Merges sorted tokens + sorted annotations of a given type.
        """
        anns = self.annotations_of_type(annotation_type)
        if not anns:
            return self.tokens

        toks = self.tokens
        anns = sorted(anns, key=start_end_key)
        toks = sorted(toks, key=start_end_key)

        out = []
        ti = 0
        ai = 0
        nt = len(toks)
        na = len(anns)

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

    def overlaps(self, other: TextObject) -> bool:
        if self.doc_id != other.doc_id:
            return False
        return self.start < other.end and self.end > other.start

    def to_json(self) -> Dict[str, Any]:
        return self.__dict__.copy()

    @abc.abstractmethod
    def detach(self):
        raise NotImplementedError()

    def to_string(
        self,
        ignore_stopwords: bool = False,
        lemmatize: bool = True,
        lowercase: bool = True,
    ):
        output = []
        for token in self.tokens:  # type:ignore
            token_str = token.text
            if ignore_stopwords and token.is_stopword:
                continue
            if lemmatize:
                token_str = token[Metadata.LEMMA.value]
            if lowercase:
                token_str = token_str.lower()
            output.append(token_str)
        return " ".join(output)
