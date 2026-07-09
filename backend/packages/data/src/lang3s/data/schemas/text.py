from __future__ import annotations

import abc
import itertools
import weakref
from collections import defaultdict
from typing import Any, Optional

import numpy as np
import shortuuid
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

from lang3s.core import config
from lang3s.core.collections_extras import binary_search
from lang3s.core.itertools_extras import filter_none
from lang3s.data.language import get_language
from lang3s.data.models import Document as DocumentModel
from lang3s.data.models import Text as TextModel
from lang3s.data.models import TextAnnotation as TextAnnotationModel
from lang3s.data.schemas.validators import NumpyArray

from .annotation_types import AnnotationTypes
from .common import PaginatedResponse
from .metadata import Metadata


def _token_offset_match(target: int, low: int, high: int) -> int:
    if low <= target < high:
        return 0
    return -1 if target < low else 1


def start_end_key(a) -> tuple[int, int]:
    return a.start, a.end


class Document(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    text: Text
    title: str
    id: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    def __contains__(self, item: str):
        return item in self.metadata_json

    def __setitem__(self, key: str, value: Any):
        self.metadata_json[key] = value

    def __delitem__(self, key: str):
        if key in self.metadata_json:
            del self.metadata_json[key]

    def __getitem__(self, key: str):
        return self.metadata_json.get(key, None)

    def __str__(self):
        return f"Document(id={self.id}, title={self.title})"

    def __repr__(self):
        return f"Document(id={self.id}, title={self.title})"

    def get(self, key: str, default: Any = None) -> Any:
        return self.metadata_json.get(key, default)

    @model_validator(mode="after")
    def wire_up_children(self) -> Document:
        self.text.document_ref = weakref.ref(self)
        for annotation in self.text.annotations:
            annotation.document_ref = weakref.ref(self)
        return self

    @property
    def language(self) -> str:
        return self.metadata_json.get("language", "en")

    @staticmethod
    def from_database(document: DocumentModel):
        text: Text = Text(
            id=document.text.id,
            document_id=document.text.document_id,
            content=document.text.content,
            embedding=document.text.embedding.to_numpy(),
            metadata_json=document.text.metadata_json,
            end=0,
            start=0,
        )
        new_doc = Document(
            id=document.id,
            title=document.title,
            metadata_json=document.metadata_json,
            text=text,
        )
        text.document_ref = weakref.ref(new_doc)
        for ta_model in document.text.annotations:
            text.add_annotation(
                id=ta_model.id,
                start=ta_model.start,
                end=ta_model.end,
                embedding=ta_model.embedding.to_numpy(),
                metadata_json=ta_model.metadata_json,
                content=ta_model.content,
                value=ta_model.value,
                type_=ta_model.type_,
                source=ta_model.source,
                sentence_index=ta_model.sentence_index,
            )
        return new_doc

    @staticmethod
    def create_text_document(
        *,
        document_id: str,
        document_title: str,
        document_metadata: dict[str, Any] | None = None,
        text_content: str,
        text_metadata: dict[str, Any] | None = None,
    ) -> Document:
        text_object = Text(
            id=shortuuid.uuid(),
            start=0,
            end=0,
            document_id=document_id,
            content=text_content,
            metadata_json=text_metadata or {},
            embedding=np.zeros(config.SEMANTIC_EMBEDDING_DIMENSION),
        )
        document = Document(
            id=document_id,
            title=document_title,
            metadata_json=document_metadata or {},
            text=text_object,
        )
        text_object.document_ref = weakref.ref(document)
        return document

    def to_database(self) -> DocumentModel:
        text = TextModel(
            **self.text.model_dump(
                exclude_unset=True,
                exclude={"start", "end"},
            )
        )
        for annotation in self.text.annotations:
            text.annotations.append(
                TextAnnotationModel(
                    **annotation.model_dump(exclude_unset=True),
                    cleaned=annotation.cleaned,
                    normalized=annotation.normalized,
                    mapping=annotation.mapping,
                    sentence_id=annotation.sentence_id,
                    is_stopword=annotation.is_stopword,
                )
            )
        # Make the tokens at the end to avoid foreign-key violations
        text.annotations.sort(key=lambda x: 999 if x.type_ == "token" else 0)
        return DocumentModel(
            id=self.id,
            title=self.title,
            metadata_json=self.metadata_json,
            text=text,
        )

    def detach(self):
        if self.text is not None:
            self.text.detach()
            del self.text
        self.text = None  # type: ignore
        self.metadata_json.clear()


class TextObject(BaseModel, metaclass=abc.ABCMeta):
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)
    id: str = Field(default_factory=lambda: str(shortuuid.uuid()))
    start: int
    end: int
    content: str
    document_id: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    document_ref: Optional[weakref.ReferenceType[Document]] = Field(
        default=None, exclude=True
    )

    @property
    def owner(self) -> Text:
        return self.document.text

    @property
    def document(self) -> Document:
        if self.document_ref is not None:
            owner_obj = self.document_ref()
            if owner_obj is not None:
                return owner_obj
        raise AttributeError("Document reference not found.")

    def __str__(self):
        return self.content

    def __repr__(self):
        return self.content

    def __hash__(self):
        return hash(self.id)

    def __contains__(self, item: str):
        return item in self.metadata_json

    def __setitem__(self, key: str, value: Any):
        self.metadata_json[key] = value

    def __delitem__(self, key: str):
        if key in self.metadata_json:
            del self.metadata_json[key]

    def __getitem__(self, key: str):
        return self.metadata_json.get(key, None)

    def get(self, key: str, default: Any = None) -> Any:
        return self.metadata_json.get(key, default)

    @property
    def tokens(self) -> list[TextAnnotation]:
        return self.annotations_of_type(AnnotationTypes.TOKEN)

    @property
    def sentences(self) -> list[TextAnnotation]:
        return self.annotations_of_type(AnnotationTypes.SENTENCE)

    @property
    def sentence(self) -> TextAnnotation:
        sentences = self.annotations_of_type(AnnotationTypes.SENTENCE)
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
    def entities(self) -> list[TextAnnotation]:
        return self.annotations_of_type(AnnotationTypes.ENTITY)

    @property
    def noun_chunks(self) -> list[TextAnnotation]:
        return self.annotations_of_type(AnnotationTypes.NOUN_CHUNK)

    @abc.abstractmethod
    def annotations_of_type(self, annotation_type: str) -> list[TextAnnotation]:
        raise NotImplementedError()

    def interleave(self, annotation_type: str) -> list[TextAnnotation]:
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
        if self.document_id != other.document_id:
            return False
        return self.start < other.end and self.end > other.start

    def to_string(
        self,
        *,
        ignore_stopwords: bool = False,
        lemmatize: bool = True,
        lowercase: bool = True,
    ):
        output = []
        for token in self.tokens:  # type:ignore
            token_str = token.content
            if ignore_stopwords and token.is_stopword:
                continue
            if lemmatize:
                token_str = token[Metadata.LEMMA]
            if lowercase:
                token_str = token_str.lower()
            output.append(token_str)
        return " ".join(output)

    @property
    def frames(self) -> list[Event]:
        events = []
        if getattr(self, "is_eventive", False):
            triggers = [self]
        else:
            triggers = [a for a in self.annotations if a.is_eventive]  # type: ignore

        for trigger in triggers:
            a0 = trigger[Metadata.A0] or []
            a1 = trigger[Metadata.A1] or []
            loc = self.owner.get_annotation(trigger[Metadata.LOC])
            time = self.owner.get_annotation(trigger[Metadata.TIME])
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


class Text(TextObject):
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)
    embedding: NumpyArray = Field(
        default_factory=lambda: np.zeros(config.SEMANTIC_EMBEDDING_DIMENSION)
    )
    annotations: list[TextAnnotation] = Field(default_factory=list)
    _tokens: list[TextAnnotation] = PrivateAttr(default_factory=list)
    _sentences: list[TextAnnotation] = PrivateAttr(default_factory=list)

    def create_span(
        self,
        start: int,
        end: int,
        source: str,
        type_: str = "span",
        value: str = "",
        metadata_json: dict[str, Any] | None = None,
    ) -> TextAnnotation:
        """
        Create a new span annotation covering tokens[start:end].
        Span is NOT automatically added to self.annotations.
        """
        span_tokens = self.tokens[start:end]
        return TextAnnotation(
            id=shortuuid.uuid(),
            start=start,
            end=end,
            content=self.content[
                span_tokens[0]["start_char"] : span_tokens[-1]["end_char"]
            ],
            sentence_index=min((t.sentence_index for t in span_tokens)),
            type_=type_,
            value=value,
            source=source,
            metadata_json=metadata_json or {},
            embedding=np.mean([t.embedding for t in span_tokens], axis=0),
            document_ref=weakref.ref(self.document),
            document_id=self.document_id,
        )

    def add_annotation(
        self,
        *,
        id: str | None = None,
        content: str,
        start: int,
        end: int,
        sentence_index: int,
        type_: str,
        value: str,
        source: str,
        embedding: np.ndarray | None = None,
        metadata_json: dict[str, Any] | None = None,
        mark_dirty: bool = False,
    ) -> TextAnnotation:
        new_annotation = TextAnnotation(
            id=id or shortuuid.uuid(),
            start=start,
            end=end,
            content=content,
            sentence_index=sentence_index,
            type_=type_,
            value=value,
            source=source,
            metadata_json=metadata_json or {},
            embedding=embedding
            if embedding is not None
            else np.zeros(config.SEMANTIC_EMBEDDING_DIMENSION),
            document_ref=weakref.ref(self.document),
            document_id=self.document_id,
        )
        return self.attach_annotation(new_annotation, mark_dirty)

    @property
    def tokens(self) -> list[TextAnnotation]:
        if not self._tokens:
            self._tokens = [
                annotation
                for annotation in self.annotations
                if annotation.type_ == AnnotationTypes.TOKEN
            ]
        return self._tokens

    @property
    def sentences(self) -> list[TextAnnotation]:
        if not self._sentences:
            self._sentences = [
                annotation
                for annotation in self.annotations
                if annotation.type_ == AnnotationTypes.SENTENCE
            ]
        return self._sentences

    @property
    def sentence(self) -> TextAnnotation:
        return self.sentences[0]

    def get_annotation(self, annotation_id: str | None) -> "TextAnnotation | None":
        """
        Return the first annotation (token, sentence, or other) with the given id.
        """
        if not annotation_id:
            return None
        for a in self.annotations:
            if a.id == annotation_id:
                return a
        return None

    @property
    def is_stopword(self) -> bool:
        return False

    @property
    def owner(self) -> Text:
        return self

    @property
    def lemma(self) -> str:
        return " ".join(t.lemma for t in self.tokens)

    def annotations_of_type(self, annotation_type: str) -> list[TextAnnotation]:
        if annotation_type == AnnotationTypes.TOKEN:
            return self.tokens
        elif annotation_type == AnnotationTypes.SENTENCE:
            return self.sentences

        return [a for a in self.annotations if a.type_ == annotation_type]

    def remove_annotations(
        self,
        sources: list[str] | None = None,
        types: list[str] | None = None,
    ) -> None:
        source_set = set(sources or [])
        types_set = set(types or [])
        remaining: list[TextAnnotation] = []
        for ann in self.annotations:
            if ann.source in source_set or ann.type_ in types_set:
                ann.detach()
                del ann
            else:
                remaining.append(ann)
        self.annotations = remaining
        self._tokens.clear()
        self._sentences.clear()
        for ann in self.annotations:
            ann._annotations = defaultdict(list)
            ann._tokens = []

    def detach(self):
        for annotation in self.annotations:
            annotation.detach()
            del annotation
        self._tokens.clear()
        self._sentences.clear()
        self.annotations.clear()
        self.embedding = None  # type:ignore
        self.metadata_json.clear()

    def tag_data(self):
        sentences = []
        tokens = []
        token_strs = []

        for sent in self._sentences:
            sentences.append(sent)
            tokens.append(sent.tokens)
            token_strs.append([tok.text for tok in sent.tokens])  # type: ignore

        return sentences, tokens, token_strs

    def get_token_for_char_offset(self, char_offset: int) -> TextAnnotation:
        def match_fn(token):
            return _token_offset_match(
                char_offset, token["start_char"], token["end_char"]
            )

        index = binary_search(
            self.tokens,
            match_fn,
        )
        return self.tokens[index]

    def clear_cache(self):
        for token in self._tokens:
            token.clear_cache()

    def attach_annotation(
        self,
        annotation: TextAnnotation,
        mark_dirty: bool = False,
    ) -> TextAnnotation:
        """
        Attach an existing TextAnnotation if not already present.
        """
        self.annotations.append(annotation)
        if annotation.type_ == AnnotationTypes.TOKEN:
            self._tokens.append(annotation)
            self.end = len(self._tokens)
        elif annotation.type_ == AnnotationTypes.SENTENCE:
            self._sentences.append(annotation)

        if mark_dirty:
            for token in annotation.tokens:
                token.clear_cache()

        return annotation

    def find(self, text: str, start: int = 0):
        try:
            index = self.content.index(text, start)
            start_token = self.get_token_for_char_offset(index)
            end_token = self.get_token_for_char_offset(index + len(text) + 1)
            return self.create_span(
                start_token.start,
                end_token.end,
                "find",
                "span",
                metadata_json={"SEARCH": text},
            )
        except ValueError:
            return None

    def get_annotation_sources(self):
        sources = set()
        sources.add(self._tokens[0].source)
        for a in self.annotations:
            sources.add(a.source)
        return sources


class TextAnnotation(TextObject):
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)
    start: int
    end: int
    sentence_index: int
    type_: str
    value: str
    source: str

    _tokens: list[TextAnnotation] = PrivateAttr(default_factory=list)
    _annotations: dict[str, list[TextAnnotation]] = PrivateAttr(default_factory=dict)

    embedding: NumpyArray = Field(
        default_factory=lambda: np.zeros(config.SEMANTIC_EMBEDDING_DIMENSION)
    )

    def __ensure_tokens(self):
        if not self._tokens:
            self._tokens = []
            self._tokens.extend(self.owner.tokens[self.start : self.end])

    def __ensure_annotations(self):
        if not self._annotations:
            self._annotations = defaultdict(list)
            owner = self.owner
            for annotation in owner.annotations:
                if self.overlaps(annotation):
                    self._annotations[annotation.type_].append(annotation)

    @property
    def annotations(self) -> list[TextAnnotation]:
        self.__ensure_annotations()
        return list(itertools.chain.from_iterable((self._annotations.values())))

    @property
    def tokens(self) -> list[TextAnnotation]:
        if self.type_ == AnnotationTypes.TOKEN:
            return [self]
        self.__ensure_tokens()
        return self._tokens

    def annotations_of_type(self, annotation_type: str) -> list[TextAnnotation]:
        if annotation_type == AnnotationTypes.TOKEN:
            return self.tokens
        self.__ensure_annotations()
        return self._annotations.get(annotation_type, [])

    def clear_cache(self):
        if self.type_ == AnnotationTypes.TOKEN:
            if self._annotations:
                for other in itertools.chain.from_iterable(self._annotations.values()):
                    other.clear_cache()
        self._tokens = []
        self._annotations = defaultdict(list)

    def text_with_coref(self):
        parts = ""
        last_start = self.tokens[0]["start_char"]
        need_whitespace = get_language(self.document.language).uses_whitespace()
        for token in self.tokens:
            coref = token.coref
            if need_whitespace:
                parts += " " * (token["start_char"] - last_start)
                last_start = token["end_char"]
            parts += coref.content

        return parts.strip()

    @property
    def is_eventive(self):
        return len(self.get(Metadata.A1, [])) > 0 or len(self.get(Metadata.A0, [])) > 0

    @property
    def dep(self):
        if self.type_ == AnnotationTypes.TOKEN:
            return self.get(Metadata.RELATION, "ROOT")
        parent = self.parent
        if parent is None:
            return "ROOT"
        return parent.get(Metadata.RELATION, "ROOT")

    @property
    def parent(self) -> Optional[TextAnnotation]:
        if self.type_ == AnnotationTypes.TOKEN:
            head: int | None = self.get(Metadata.HEAD, None)
            if head is None or head == self.start:
                return None
            return self.owner.tokens[head]  # type: ignore

        span_set = set((token.start for token in self.tokens))
        for token in self.tokens:
            head: int | None = token.get(Metadata.HEAD, None)
            if head is not None and (head not in span_set or head == token.start):
                return self.owner.tokens[head]
        return None

    def detach(self):
        self.embedding = None  # type:ignore
        self.metadata_json.clear()

    @property
    def head(self) -> TextAnnotation:
        if self.type_ == AnnotationTypes.TOKEN:
            return self

        span_set = set((token.start for token in self.tokens))
        for token in self.tokens:
            head = token.get(Metadata.HEAD, None)
            if head is not None and (head not in span_set or head == token.start):
                return token
        return self.tokens[-1]

    @property
    def children(self) -> list[TextAnnotation]:
        children: list[TextAnnotation] = []
        if self.type_ == AnnotationTypes.TOKEN:
            for token in self.sentence.tokens:
                if token[Metadata.HEAD] == self.start and token.id != self.id:
                    children.append(token)
        else:
            for token in self.tokens:
                children.extend(token.children)

        return children

    @property
    def subtree(self) -> list[TextAnnotation]:
        out: set[TextAnnotation] = set()
        stack: list[TextAnnotation] = [self]
        visited: set[int] = set()

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
        coref_id = self.get(Metadata.COREF)
        if coref_id is None:
            return self
        for ann in self.owner.annotations:
            if ann.id == coref_id:
                return ann
        return self

    @property
    def sentence_id(self) -> str:
        return self.sentence.id

    @property
    def lemma(self) -> str:
        lemma_str = self.get(Metadata.LEMMA, None)
        if lemma_str is None:
            if self.type_ == AnnotationTypes.TOKEN:
                return self.content.lower()
            lemma_str = " ".join(t.lemma for t in self.tokens)
        return lemma_str.lower()

    @property
    def is_stopword(self) -> bool:
        v = self.get(Metadata.IS_STOPWORD, None)
        if v is not None:
            return v
        elif (
            self.type_ == AnnotationTypes.TOKEN
            or self.type_ == AnnotationTypes.SENTENCE
        ):
            return False

        return all(t.is_stopword for t in self.tokens)

    @property
    def mapping(self) -> str:
        return f"{self.type_}:{self.value}"

    @property
    def normalized(self) -> str:
        if self.type_ == AnnotationTypes.SENTENCE:
            return self.content.upper()
        return self.coref.content.upper()

    def previous_token(self) -> Optional[TextAnnotation]:
        if self.start == 0:
            return None
        return self.owner.tokens[self.start - 1]

    def next_token(self) -> Optional[TextAnnotation]:
        if self.end == len(self.owner.tokens):
            return None
        return self.owner.tokens[self.end]

    @property
    def cleaned(self) -> str:
        return self.to_string(
            ignore_stopwords=True,
            lemmatize=True,
            lowercase=True,
        )


class Event(BaseModel):
    trigger: TextAnnotation
    a0: list[TextAnnotation] = Field(default_factory=list)
    a1: list[TextAnnotation] = Field(default_factory=list)
    time: TextAnnotation | None = None
    loc: TextAnnotation | None = None

    def __str__(self) -> str:
        out_a0 = [
            f"{a0.content}" if a0.coref == a0 else f"{a0.content} ({a0.coref.content})"
            for a0 in self.a0
        ]
        out_a1 = [
            f"{a1.content}" if a1.coref == a1 else f"{a1.content} ({a1.coref.content})"
            for a1 in self.a1
        ]
        out_time = self.time
        if self.time is not None and self.time.coref != self.time:
            out_time = f"{self.time.content} ({self.time.coref.content})"
        out_loc = self.loc
        if self.loc is not None and self.loc.coref != self.loc:
            out_loc = f"{self.loc.content} ({self.loc.coref.content})"
        return (
            f"Event(value='{self.trigger.value}', trigger='{self.trigger}', "
            f"A0={out_a0}, A1={out_a1}, TIME={out_time},LOC={out_loc})"
        )

    def __repr__(self) -> str:
        return str(self)


class DocumentInfo(BaseModel):
    id: str
    title: str
    snippet: str


class DocumentListResponse(PaginatedResponse[DocumentInfo]):
    pass
