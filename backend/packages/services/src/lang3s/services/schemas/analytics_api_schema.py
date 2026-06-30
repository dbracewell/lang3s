from typing import Annotated, List, Literal

from pydantic import BaseModel, Field, RootModel, WithJsonSchema

from lang3s.data.schemas.common import PaginatedResponse


class AnnotationCountsRequest(BaseModel):
    mappings: List[str]
    page: int
    page_size: int
    filter: Annotated[
        str | None, WithJsonSchema({"type": "string", "nullable": True})
    ] = None
    order_by: Literal[
        "mention_count", "document_count", "mentions_per_document", "sentence_count"
    ] = Field(default="mention_count")


class AnnotationCount(BaseModel):
    content: str
    value: str
    path: str
    mention_count: int
    document_count: int
    sentence_count: int
    mentions_per_document: float


class AnnotationCountsResult(PaginatedResponse[AnnotationCount]):
    pass


class AnnotationCoOccurrenceRequest(BaseModel):
    entity: str
    value: str
    targets: List[str]


class AnnotationCoOccurrence(BaseModel):
    e2: str
    e2Type: str
    count: float


class AnnotationCoOccurrenceResult(RootModel[List[AnnotationCoOccurrence]]):
    pass


class AnnotationEvent(BaseModel):
    text: str
    sentence: str
    value: str
    A0: list[str]
    A1: list[str]
    TIME: Annotated[
        str | None, WithJsonSchema({"type": "string", "nullable": True})
    ] = None
    LOC: Annotated[str | None, WithJsonSchema({"type": "string", "nullable": True})] = (
        None
    )


class AnnotationEventByType(BaseModel):
    value: str
    count: int
    events: list[AnnotationEvent]


class AnnotationEventResult(RootModel[List[AnnotationEventByType]]):
    pass


class AnnotationEventRequest(BaseModel):
    entity: str
    value: str


class AnnotationMetricRequest(BaseModel):
    values: List[str]


class AnnotationMetric(BaseModel):
    entityId: str
    entityType: str
    normScore: float
    rawScore: float
    category: str


class AnnotationMetricResult(RootModel[List[AnnotationMetric]]):
    pass


class AnnotationCohortInformationRequest(BaseModel):
    ids: List[str]


class CohortNode(BaseModel):
    id: str
    text: str
    display: str
    value: float
    r: int
    color: str
    cid: str


class CohortClusterEntry(BaseModel):
    id: str
    name: str
    type: str
    color: str


class CohortClusterSimilarity(BaseModel):
    id1: str
    id2: str
    target: str
    source: str
    source_document_count: int
    target_document_count: int
    similarity: float


class CohortClustering(BaseModel):
    similarities: list[CohortClusterSimilarity]
    points: list[CohortNode]
    clusters: list[list[CohortClusterEntry]]


class CohortInformationEdge(BaseModel):
    source: str
    sourceId: str
    target: str
    targetId: str
    documentCount: int
    sentenceCount: int


class CohortInformationRank(BaseModel):
    id: str
    value: int


class CohortInformationResult(BaseModel):
    edges: list[CohortInformationEdge]
    ranked: list[CohortInformationRank]
