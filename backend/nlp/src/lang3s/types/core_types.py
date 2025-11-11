import itertools
import json
from abc import ABC, abstractmethod
from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    Tuple,
    TypeVar,
    override,
)

import numpy as np
import shortuuid
from more_itertools import first
from numpy.typing import NDArray
from psycopg.types.json import Jsonb

from lang3s.utils import filter_none

from .metadata import AnnotationTypes, Metadata

T = TypeVar("T", bound="Deserializable")


class DBModel(ABC):
    DB_COLUMNS: ClassVar[List[str]]

    @abstractmethod
    def insert_values(self) -> List[Any]:
        pass

    @abstractmethod
    def to_json(self) -> Dict[str, Any]:
        pass


class Deserializable(ABC):
    @staticmethod
    @abstractmethod
    def from_json(obj: Dict[str, Any]) -> T:  # type: ignore
        pass


class TextObject(DBModel, ABC):
    def to_string(
        self, ignore_stopwords=False, lemmatize=False, lowercase=False
    ) -> str:
        output = []
        for token in self.tokens:
            token_str = token.text
            if ignore_stopwords and token.is_stopword:
                continue
            if lemmatize:
                token_str = token.metadata[Metadata.LEMMA.value]
            if lowercase:
                token_str = token_str.lower()
            output.append(token_str)
        return " ".join(output)

    @property
    @abstractmethod
    def embedding(self) -> Optional[NDArray[np.floating]]:
        pass

    @embedding.setter
    @abstractmethod
    def embedding(self, value: NDArray[np.floating]):
        pass

    def interleave(self, interleaved: str) -> List["TextAnnotation"]:
        items = []
        annotations = self.annotations_of_type(interleaved)
        if len(annotations) == 0:
            return self.tokens
        annotations = sorted(annotations, key=lambda a: (a.start, a.end))
        tokens = sorted(self.tokens, key=lambda a: (a.start, a.end))
        ti = ai = 0
        na, nt = len(annotations), len(tokens)
        while ti < nt or ai < na:
            if ai >= na:
                items.extend(tokens[ti:])
                break
            token = tokens[ti]
            annotation = annotations[ai]
            if annotation.start <= token.start:
                items.append(annotation)
                ai += 1
                while ti < nt and tokens[ti].start < annotation.end:
                    ti += 1
            else:
                items.append(token)
                ti += 1

        return items

    @property
    @abstractmethod
    def is_stopword(self) -> bool:
        pass

    @property
    @abstractmethod
    def doc_id(self) -> str:
        pass

    @property
    @abstractmethod
    def start(self) -> int:
        pass

    @property
    @abstractmethod
    def end(self) -> int:
        pass

    @property
    @abstractmethod
    def sentences(self) -> List["TextAnnotation"]:
        pass

    @property
    @abstractmethod
    def tokens(self) -> List["TextAnnotation"]:
        pass

    @property
    def entities(self) -> List["TextAnnotation"]:
        return self.annotations_of_type(AnnotationTypes.ENTITY.value)

    @property
    def noun_chunks(self) -> List["TextAnnotation"]:
        return self.annotations_of_type(AnnotationTypes.NOUN_CHUNK.value)

    @property
    @abstractmethod
    def owner(self) -> "Text":
        pass

    @abstractmethod
    def __getitem__(self, name: str) -> Optional[Any]:
        pass

    @property
    def events(self) -> List["Event"]:
        event_list = []
        for trigger in self.annotations_of_type(AnnotationTypes.EVENT.value):
            A0 = trigger["A0"]
            if A0 is None:
                A0 = []
            A1 = trigger["A1"]
            if A1 is None:
                A1 = []

            LOC = self.owner.get_annotation(trigger["LOC"])
            TIME = self.owner.get_annotation(trigger["TIME"])
            event_list.append(
                Event(
                    trigger=trigger,
                    value=trigger.value,
                    A0=filter_none(
                        self.owner.get_annotation(aid) for aid in A0
                    ),
                    A1=filter_none(
                        self.owner.get_annotation(aid) for aid in A1
                    ),
                    TIME=TIME,
                    LOC=LOC,
                )
            )
        return event_list

    def overlaps(self, other: "TextObject") -> bool:
        if self.doc_id != other.doc_id:
            return False
        return self.start < other.end and self.end > other.start

    @abstractmethod
    def annotations_of_type(self, type: str) -> List["TextAnnotation"]:
        pass


class TextAnnotation(TextObject):
    __slots__ = (
        "id",
        "_owner",
        "text",
        "_start",
        "_end",
        "type",
        "sentence_id",
        "value",
        "_embedding",
        "metadata",
        "_tokens",
    )
    DB_COLUMNS = [
        "id",
        "text_id",
        "doc_id",
        "start",
        "end",
        "sentence_id",
        "type",
        "value",
        "text",
        "clean_text",
        "mapping",
        "embedding",
        "full_embedding",
        "metadata",
    ]

    def __init__(
        self,
        id: str,
        owner: "Text",
        text: str,
        start: int,
        end: int,
        sentence_id: int,
        type: str,
        value: str,
        embedding: Optional[NDArray[np.floating]] = None,
        metadata: Dict[str, str] | None = None,
    ):
        self.id = id
        self.text: str = text
        self._start: int = start
        self._end: int = end
        self.type: str = type
        self.sentence_id: int = sentence_id
        self.value: str = value
        self._embedding: NDArray[np.floating] = (
            embedding if embedding is not None else np.zeros(1)
        )
        self.metadata: Dict[str, Any] = metadata if metadata is not None else {}
        self._owner: "Text" = owner

    @property
    def owner(self) -> "Text":
        return self._owner

    @override
    def __getitem__(self, name: str) -> Optional[Any]:
        return self.metadata.get(name, None)

    @property
    def lemma(self):
        if Metadata.LEMMA.value in self.metadata:
            return self.metadata[Metadata.LEMMA.value]
        return " ".join(t.lemma for t in self.tokens)

    @property
    @override
    def embedding(self) -> NDArray[np.floating]:
        return self._embedding

    @embedding.setter
    @override
    def embedding(self, value: NDArray[np.floating]):
        self._embedding = value

    @property
    @override
    def doc_id(self) -> str:
        return self._owner.doc_id

    @property
    @override
    def is_stopword(self) -> bool:
        return self.metadata.get(
            Metadata.IS_STOPWORD.value,
            all(t.is_stopword for t in self.tokens)
            if self.type != AnnotationTypes.TOKEN.value
            else False,
        )

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return self.text

    @property
    def parent(self) -> Optional["TextAnnotation"]:
        if self.type == "token":
            head = self.metadata[Metadata.HEAD.value]
            if head == self.start:
                return None
            return self._owner.tokens[head]

        span_set = set((token.start for token in self.tokens))
        for token in self.tokens:
            head = token.metadata[Metadata.HEAD.value]
            if head not in span_set or head == token.start:
                return self._owner.tokens[head]

        return None

    def __eq__(self, other):
        if not isinstance(other, TextAnnotation):
            return NotImplemented
        return self.id == other.id

    def __hash__(self):
        # A common approach is to hash a tuple of the relevant attributes
        return hash(self.id)

    @property
    def subtree(self) -> List["TextAnnotation"]:
        ancestors = set()
        visited = set()
        horizon: List["TextAnnotation"] = [self]
        while len(horizon) > 0:
            n = horizon.pop()
            if n.start not in visited:
                children = n.children
                ancestors.update(children)
                horizon.extend(children)
                visited.add(n.start)
        return list(ancestors)

    @property
    def children(self) -> List["TextAnnotation"]:
        if self.type == "token":
            children = []
            for token in self._owner.tokens:
                if token.metadata[Metadata.HEAD.value] == self.start:
                    children.append(token)
            return children
        children = []
        for token in self.tokens:
            children.extend(token.children)
        return children

    @property
    def coref(self) -> "TextAnnotation":
        coref_id = self.metadata.get("coref", None)
        if coref_id is None:
            return self
        return first(
            filter(lambda x: x.id == coref_id, self._owner.annotations), self
        )

    @property
    @override
    def start(self) -> int:
        return self._start

    @property
    @override
    def end(self) -> int:
        return self._end

    @override
    def insert_values(self):
        return [
            self.id,
            self._owner.id,
            self._owner.doc_id,
            self._start,
            self._end,
            self.sentence_id,
            self.type,
            self.value,
            self.text,
            self.to_string(True, True, True),
            f"{self.type}:{self.value}"
            if self.type not in ["sentence", "noun_chunk"]
            else None,
            "".join(
                (str(i) for i in (self._embedding > 0).astype(int).tolist())
            ),
            self._embedding,
            Jsonb(self.metadata),
        ]

    @property
    def dep(self):
        if self.type == "token":
            return self.metadata[Metadata.RELATION.value]
        parent = self.parent
        if parent is None:
            return "ROOT"
        return parent.metadata[Metadata.RELATION.value]

    @property
    @override
    def tokens(self) -> List["TextAnnotation"]:
        if self.type == "token":
            return [self]
        return [a for a in self._owner.tokens[self.start : self.end]]

    @override
    def annotations_of_type(self, type: str) -> List["TextAnnotation"]:
        return [
            a
            for a in self._owner.annotations
            if a.type == type and self.overlaps(a)
        ]

    @property
    def sentence(self) -> "TextAnnotation":
        for s in self._owner.sentences:
            if s.start < self.end and s.end > self.start:
                return s
        raise Exception("No sentence found")

    @property
    @override
    def sentences(self) -> List["TextAnnotation"]:
        return [self.sentence]

    @override
    def to_json(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "type": self.type,
            "value": self.value,
            "sentence_id": self.sentence_id,
            "embedding": self._embedding.tolist()
            if self._embedding is not None
            else None,
            "metadata": self.metadata,
        }


class Text(TextObject, Deserializable):
    __slots__ = (
        "id",
        "text",
        "_doc_id",
        "metadata",
        "_embedding",
        "annotations",
        "tokens",
        "sentences",
    )
    DB_COLUMNS = [
        "id",
        "text",
        "doc_id",
        "embedding",
        "full_embedding",
        "metadata",
    ]

    def __init__(
        self,
        doc_id: str,
        content: str,
        id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[NDArray[np.floating]] = None,
    ):
        self.text = content
        self.id = id or shortuuid.uuid()
        self._doc_id = doc_id
        self._embedding: NDArray[np.floating] = (
            embedding if embedding is not None else np.zeros(0)
        )
        self.metadata: Dict[str, Any] = metadata or {}
        self.annotations: List[TextAnnotation] = []
        self.tokens: List[TextAnnotation] = []
        self.sentences: List[TextAnnotation] = []

    def get_annotation(self, id: Optional[str]) -> Optional[TextAnnotation]:
        if id is None:
            return None
        return first(filter(lambda a: a.id == id, self.all_annotations), None)

    @property
    @override
    def embedding(self) -> NDArray[np.floating]:
        return self._embedding

    @embedding.setter
    @override
    def embedding(self, value: NDArray[np.floating]):
        self._embedding = value

    @property
    @override
    def is_stopword(self) -> bool:
        return False

    @property
    @override
    def doc_id(self) -> str:
        return self._doc_id

    @property
    def all_annotations(self):
        return list(
            itertools.chain.from_iterable(
                [self.tokens, self.sentences, self.annotations]
            )
        )

    @override
    def __getitem__(self, name: str) -> Optional[Any]:
        return self.metadata.get(name, None)

    def tag_data(
        self,
    ) -> Tuple[
        List[TextAnnotation], List[List[TextAnnotation]], List[List[str]]
    ]:
        tokens = []
        sentences = []
        token_strs = []
        for sentence in self.sentences:
            sentences.append(sentence)
            tokens.append(sentence.tokens)
            token_strs.append([token.text for token in sentence.tokens])
        return sentences, tokens, token_strs

    @property
    @override
    def owner(self) -> "Text":
        return self

    @property
    @override
    def start(self):
        return self.tokens[0].start

    @property
    @override
    def end(self):
        return self.tokens[-1].end

    @override
    def insert_values(self):
        return [
            self.id,
            self.text,
            self._doc_id,
            "".join(
                (str(i) for i in (self._embedding > 0).astype(int).tolist())
            ),
            self._embedding,
            Jsonb(self.metadata),
        ]

    def annotations_of_type(self, annotation_type: str) -> List[TextAnnotation]:
        return [
            entity
            for entity in filter(
                lambda a: a.type == annotation_type, self.annotations
            )
        ]

    @override
    def to_json(self):
        return {
            "id": self.id,
            "text": self.text,
            "embedding": self.embedding.tolist(),
            "metadata": self.metadata,
            "annotations": list(
                a.to_json()
                for a in itertools.chain.from_iterable(
                    [self.tokens, self.sentences, self.annotations]
                )
            ),
        }

    @staticmethod
    @override
    def from_json(obj: Dict[str, Any]) -> "Text":
        text_dict = obj["text"]

        embedding = text_dict["embedding"]
        if isinstance(embedding, str):
            embedding = np.array(json.loads(embedding))
        if isinstance(embedding, list):
            embedding = np.array(embedding)

        text = Text(
            id=text_dict["id"],
            metadata=text_dict.get("metadata", {}),
            content=text_dict["text"],
            doc_id=obj["id"],
            embedding=embedding,
        )

        for annotation in text_dict["annotations"]:
            embedding = annotation["embedding"]
            if embedding is not None:
                if isinstance(embedding, str):
                    embedding = np.array(
                        json.loads(embedding), dtype=np.float16
                    )
                if isinstance(embedding, list):
                    embedding = np.array(embedding, dtype=np.float16)
            text.add_annotation(
                id=annotation["id"],
                text=annotation["text"],
                start=annotation["start"],
                end=annotation["end"],
                sentence_id=annotation["sentence_id"],
                type=annotation["type"],
                value=annotation["value"],
                embedding=embedding,
                metadata=annotation.get("metadata", {}),
            )
        text.tokens = sorted(text.tokens, key=lambda token: token.start)
        text.sentences = sorted(
            text.sentences, key=lambda sentences: sentences.start
        )
        return text

    def add_annotation(
        self,
        text: str,
        start: int,
        end: int,
        sentence_id: int,
        type: str,
        value: str,
        id: Optional[str] = None,
        embedding: Optional[NDArray[np.floating]] = None,
        metadata: Dict[str, Any] | None = None,
    ) -> TextAnnotation:
        annotation = TextAnnotation(
            id=id if id is not None else shortuuid.uuid(),
            owner=self,
            text=text,
            start=start,
            end=end,
            sentence_id=sentence_id,
            type=type,
            value=value,
            embedding=embedding,
            metadata=metadata,
        )
        if annotation.type == AnnotationTypes.TOKEN.value:
            self.tokens.append(annotation)
        elif annotation.type == AnnotationTypes.SENTENCE.value:
            self.sentences.append(annotation)
        else:
            self.annotations.append(annotation)
        return annotation

    def attach_annotation(self, annotation: TextAnnotation):
        if self.get_annotation(annotation.id) is not None:
            return
        if annotation.type == AnnotationTypes.TOKEN.value:
            self.tokens.append(annotation)
        elif annotation.type == AnnotationTypes.SENTENCE.value:
            self.sentences.append(annotation)
        else:
            self.annotations.append(annotation)
        return annotation

    def create_span(
        self,
        start: int,
        end: int,
        type: Optional[str] = None,
        value: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TextAnnotation:
        annotation = TextAnnotation(
            id=shortuuid.uuid(),
            owner=self,
            text=" ".join((t.text for t in self.tokens[start:end])),
            start=start,
            end=end,
            sentence_id=min((t.sentence_id for t in self.tokens[start:end])),
            type=type or "span",
            value=value or "",
            metadata=metadata,
        )
        return annotation


class Document(DBModel, Deserializable):
    __slots__ = ("id", "title", "text", "metadata")
    DB_COLUMNS = ["id", "title", "metadata"]

    def __init__(
        self,
        doc_id: str,
        title: str,
        text: Text,
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        self.text = text
        self.title = title
        self.id = doc_id
        self.metadata: Dict[str, Any] = {}
        if metadata is not None:
            self.metadata.update(metadata)

    @override
    def to_json(self):
        return {
            "id": self.id,
            "title": self.title,
            "metadata": self.metadata,
            "text": self.text.to_json(),
        }

    @staticmethod
    @override
    def from_json(obj: Dict[str, Any]) -> "Document":
        return Document(
            doc_id=obj["id"],
            title=obj["title"],
            metadata=obj.get("metadata", {}),
            text=Text.from_json(obj),
        )

    @override
    def insert_values(self):
        return [self.id, self.title, Jsonb(self.metadata)]

    @property
    def language(self):
        return self.metadata.get(Metadata.LANGUAGE.value, "en")


class Event:
    def __init__(
        self,
        trigger: TextAnnotation,
        value: str,
        A0: Optional[List[TextAnnotation]] = None,
        A1: Optional[List[TextAnnotation]] = None,
        TIME: Optional[TextAnnotation] = None,
        LOC: Optional[TextAnnotation] = None,
    ) -> None:
        self.trigger = trigger
        self.value = value
        self.A0: List[TextAnnotation] = A0 or []
        self.A1: List[TextAnnotation] = A1 or []
        self.TIME: Optional[TextAnnotation] = TIME
        self.LOC: Optional[TextAnnotation] = LOC

    def __str__(self) -> str:
        out_a0 = [
            f"{a0.text}"
            if a0.coref is None or a0.coref == a0
            else f"{a0.text} ({a0.coref.text})"
            for a0 in self.A0
        ]
        out_a1 = [
            f"{a1.text}"
            if a1.coref is None or a1.coref == a1
            else f"{a1.text} ({a1.coref.text})"
            for a1 in self.A1
        ]
        out_TIME = self.TIME
        if self.TIME is not None and self.TIME.coref != self.TIME:
            out_TIME = f"{self.TIME.text} ({self.TIME.coref.text})"
        out_LOC = self.LOC
        if self.LOC is not None and self.LOC.coref != self.LOC:
            out_LOC = f"{self.LOC.text} ({self.LOC.coref.text})"
        return f"Event(\n  trigger={self.trigger}\n  A0={out_a0}\n  A1={out_a1},\n  TIME={out_TIME}\n  LOC={out_LOC}\n)"

    def __repr__(self) -> str:
        return str(self)
