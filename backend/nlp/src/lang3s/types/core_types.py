import itertools
import json
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Dict, List, Optional, Tuple, TypeVar, override

import numpy as np
import shortuuid
from numpy.typing import NDArray
from psycopg.types.json import Jsonb

from lang3s.config import EMBEDDING_DIMENSIONS
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
        annotations = self.annotations(interleaved)
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

    def overlaps(self, other: "TextObject") -> bool:
        if self.doc_id != other.doc_id:
            return False
        return self.start < other.end and self.end > other.start

    @abstractmethod
    def annotations(self, type: str) -> List["TextAnnotation"]:
        pass


class TextAnnotation(TextObject):
    __slots__ = (
        "owner",
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
        "text_id",
        "doc_id",
        "start",
        "end",
        "sentence_id",
        "type",
        "value",
        "text",
        "embedding",
        "metadata",
    ]

    def __init__(
        self,
        owner: "Text",
        text: str,
        start: int,
        end: int,
        sentence_id: int,
        type: str,
        value: str,
        embedding: Optional[NDArray[np.float32]] = None,
        metadata: Dict[str, str] | None = None,
    ):
        self.text: str = text
        self._start: int = start
        self._end: int = end
        self.type: str = type
        self.sentence_id: int = sentence_id
        self.value: str = value
        self._embedding: Optional[NDArray[np.float32]] = embedding
        self.metadata: Dict[str, Any] = metadata if metadata is not None else {}
        self.owner: "Text" = owner

    @property
    @override
    def embedding(self) -> Optional[NDArray[np.floating]]:
        return self._embedding

    @embedding.setter
    @override
    def embedding(self, value: NDArray[np.floating]):
        self._embedding = value

    @property
    @override
    def doc_id(self) -> str:
        return self.owner.doc_id

    @property
    @override
    def is_stopword(self) -> bool:
        return self.metadata.get(
            Metadata.IS_STOPWORD.value,
            all(t.is_stopword for t in self.tokens)
            if self.type != AnnotationTypes.TOKEN.value
            else False,
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
            self.owner.id,
            self.owner.doc_id,
            self._start,
            self._end,
            self.sentence_id,
            self.type,
            self.value,
            self.text,
            self._embedding,
            Jsonb(self.metadata),
        ]

    @property
    @override
    def tokens(self) -> List["TextAnnotation"]:
        return [a for a in self.owner.tokens[self.start : self.end]]

    @override
    def annotations(self, type: str) -> List["TextAnnotation"]:
        return [
            a
            for a in self.owner.annotations
            if a.type == type and self.overlaps(a)
        ]

    @property
    def sentence(self) -> "TextAnnotation":
        for s in self.owner.sentences:
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
    DB_COLUMNS = ["id", "text", "doc_id", "embedding", "metadata"]

    def __init__(self, doc_id: str, content: str):
        self.text = content
        self.id = shortuuid.uuid()
        self._doc_id = doc_id
        self._embedding: NDArray[np.float32] = np.zeros(
            EMBEDDING_DIMENSIONS, dtype=np.float32
        )
        self.metadata: Dict[str, Any] = {}
        self.annotations: List[TextAnnotation] = []
        self.tokens: List[TextAnnotation] = []
        self.sentences: List[TextAnnotation] = []

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
            self._embedding,
            Jsonb(self.metadata),
        ]

    @property
    def entities(self) -> List[TextAnnotation]:
        return [
            entity
            for entity in filter(
                lambda a: a.type == AnnotationTypes.ENTITY, self.annotations
            )
        ]

    @property
    def phrase_chunks(self) -> List[TextAnnotation]:
        return [
            chunk
            for chunk in filter(
                lambda a: a.type == AnnotationTypes.PHRASE_CHUNK,
                self.annotations,
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
        text = Text(
            content=text_dict["text"],
            doc_id=obj["id"],
        )
        text.id = text_dict["id"]
        text.metadata = text_dict.get("metadata", {})
        embedding = text_dict["embedding"]
        if isinstance(embedding, str):
            embedding = np.array(json.loads(embedding))
        if isinstance(embedding, list):
            embedding = np.array(embedding)
        text.embedding = embedding
        for annotation in text_dict["annotations"]:
            embedding = annotation["embedding"]
            if embedding is not None:
                if isinstance(embedding, str):
                    embedding = np.array(json.loads(embedding))
                if isinstance(embedding, list):
                    embedding = np.array(embedding)
            text.add_annotation(
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
        embedding: Optional[NDArray[np.float32]] = None,
        metadata: Dict[str, Any] | None = None,
    ):
        annotation = TextAnnotation(
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
