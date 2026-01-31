from typing import List, Literal

from pydantic import BaseModel, Field


class CountsRequest(BaseModel):
    mappings: List[str]
    page: int
    page_size: int
    filter: str | None = Field(default=None)
    order_by: Literal["mentions", "docs", "mentionsPerDoc"] = Field(default="mentions")


class CoOccurrenceRequest(BaseModel):
    entity: str
    value: str
    targets: List[str]


class EventRequest(BaseModel):
    entity: str
    value: str


class AnnotationLonersRequest(BaseModel):
    values: List[str]


class AffinityRequest(BaseModel):
    values: List[str]


class CohortInformationRequest(BaseModel):
    ids: List[str]
