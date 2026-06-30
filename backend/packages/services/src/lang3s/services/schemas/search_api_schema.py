from typing import Annotated

import numpy as np
from pydantic import BaseModel, ConfigDict, WithJsonSchema

from lang3s.data.schemas.common import PaginatedQuery, PaginatedResponse


class EffectiveSearchParams(PaginatedQuery):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    q: str | None = None
    embedding: np.ndarray | None = None
    is_strict: bool = False


class SearchParams(PaginatedQuery):
    q: Annotated[
        str | None,
        WithJsonSchema({"nullable": True, "type": "string"}),
    ] = None
    aid: Annotated[
        list[str] | None,
        WithJsonSchema(
            {"nullable": True, "type": "array", "items": {"type": "string"}}
        ),
    ] = None
    sid: Annotated[
        list[str] | None,
        WithJsonSchema(
            {"nullable": True, "type": "array", "items": {"type": "string"}}
        ),
    ] = None
    tid: Annotated[
        list[int] | None,
        WithJsonSchema(
            {"nullable": True, "type": "array", "items": {"type": "integer"}}
        ),
    ] = None
    is_strict: Annotated[
        bool,
        WithJsonSchema({"nullable": False, "type": "boolean", "default": False}),
    ]


class Highlight(BaseModel):
    document_id: str
    sentence_id: str
    text: str


class SearchResults[T](BaseModel):
    next_cursor: Annotated[
        int | None,
        WithJsonSchema({"nullable": True, "type": "integer"}),
    ]
    results: list[T]
    total: int


class DocumentSearchResult(BaseModel):
    document_id: str
    document_title: str
    highlights: list[Highlight]


class TopicSearchResult(BaseModel):
    id: int
    name: str
    highlights: list[Highlight]


class AnnotationHighlight(BaseModel):
    id: str
    sentence_id: str
    annotation: str
    sentence: str


class AnnotationDocResult(BaseModel):
    document_id: str
    document_title: str
    highlights: list[AnnotationHighlight]


class AnnotationSearchResult(BaseModel):
    name: str
    path: str
    docs: list[AnnotationDocResult]


class DocumentSearchResults(SearchResults[DocumentSearchResult]):
    pass


class TopicSearchResults(SearchResults[TopicSearchResult]):
    pass


class AnnotationSearchResults(SearchResults[AnnotationSearchResult]):
    pass
