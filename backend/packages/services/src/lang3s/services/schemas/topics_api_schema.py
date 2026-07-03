from typing import Any, NamedTuple, Optional

from pydantic import BaseModel, Field


class TopicData(BaseModel):
    id: str
    name: str
    support: int


class Task(BaseModel):
    method: str
    id: str
    data: Any


class TopicUpdateRequest(BaseModel):
    name: Optional[str]
    is_fixed: Optional[bool]


class TopicNode(BaseModel):
    id: str
    text: str
    display: str
    value: float
    type: str = "topic"
    subvalues: dict[str, int] = Field(default_factory=dict)


class TopicSimilarity(BaseModel):
    id1: str
    id2: str
    similarity: float


class TopicGraph(BaseModel):
    nodes: list[TopicNode]
    similarities: list[TopicSimilarity]
