from enum import StrEnum
from typing import Any, List, Literal

from pydantic import BaseModel, Field

from lang3s.data.db.query_template import QueryTemplateEngine


class AnnotationCountsRequest(BaseModel):
    mappings: List[str]
    page: int
    page_size: int
    filter: str | None = Field(default=None)
    order_by: Literal[
        "mention_count", "document_count", "mentions_per_document", "sentence_count"
    ] = Field(default="mention_count")


class AnnotationCoOccurrenceRequest(BaseModel):
    entity: str
    value: str
    targets: List[str]


class AnnotationEventRequest(BaseModel):
    entity: str
    value: str


class AnnotationMetricRequest(BaseModel):
    values: List[str]


class AnnotationCohortInformationRequest(BaseModel):
    ids: List[str]
