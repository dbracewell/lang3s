from typing import Any, Dict, List, Optional, Tuple

import shortuuid

from lang3s.core.metadata import AnnotationTypes, Metadata


class TextAnnotation:
    __slots__ = (
        "owner",
        "text",
        "doc_id",
        "start",
        "end",
        "type",
        "value",
        "embedding",
        "metadata",
        "tokens",
    )

    def __init__(
        self,
        owner: "Text",
        text: str,
        start: int,
        end: int,
        type: str,
        value: str,
        embedding: Optional[List[float]] = None,
        metadata: Dict[str, str] | None = None,
    ):
        self.doc_id: str = owner.doc_id
        self.text: str = text
        self.start: int = start
        self.end: int = end
        self.type: str = type
        self.value: str = value
        self.embedding: List[float] | None = embedding
        self.metadata: Dict[str, Any] = metadata if metadata is not None else {}
        self.owner: "Text" = owner
        self.tokens = [a for a in owner.tokens[start:end]]

    def overlaps(self, other: "TextAnnotation") -> bool:
        if self.doc_id != other.doc_id:
            return False

        return self.start < other.end and self.end > other.start

    def annotations(self, type: str) -> List["TextAnnotation"]:
        return [
            a for a in self.owner.annotations if a.type == type and self.overlaps(a)
        ]

    def sentence(self) -> "TextAnnotation":
        for s in self.owner.sentences:
            if s.start < self.end and s.end > self.start:
                return s
        raise Exception("No sentence found")


class Text:
    __slots__ = (
        "id",
        "text",
        "doc_id",
        "metadata",
        "embedding",
        "annotations",
        "tokens",
        "sentences",
    )

    def __init__(self, doc_id: str, content: str):
        self.text = content
        self.id = shortuuid.uuid()
        self.doc_id = doc_id
        self.embedding: List[float] = []
        self.metadata: Dict[str, Any] = {}
        self.annotations: List[TextAnnotation] = []
        self.tokens: List[TextAnnotation] = []
        self.sentences: List[TextAnnotation] = []

    def tag_data(
        self,
    ) -> Tuple[List[TextAnnotation], List[List[TextAnnotation]], List[List[str]]]:
        tokens = []
        sentences = []
        token_strs = []
        for sentence in self.sentences:
            sentences.append(sentence)
            tokens.append(sentence.tokens)
            token_strs.append([token.text for token in sentence.tokens])
        return sentences, tokens, token_strs

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
                lambda a: a.type == AnnotationTypes.PHRASE_CHUNK, self.annotations
            )
        ]

    def add_annotation(
        self,
        text: str,
        start: int,
        end: int,
        type: str,
        value: str,
        embedding: List[float] | None = None,
        metadata: Dict[str, Any] | None = None,
    ):
        annotation = TextAnnotation(
            owner=self,
            text=text,
            start=start,
            end=end,
            type=type,
            value=value,
            embedding=embedding,
            metadata=metadata,
        )
        if annotation.type == AnnotationTypes.TOKEN:
            self.tokens.append(annotation)
        elif annotation.type == AnnotationTypes.SENTENCE:
            self.sentences.append(annotation)
        else:
            self.annotations.append(annotation)


class Document:
    __slots__ = ("id", "title", "text", "metadata")

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

    @property
    def language(self):
        return self.metadata.get(Metadata.LANGUAGE.value, "en")
