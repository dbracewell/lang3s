import uuid
from typing import Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from lang3s.core import config

from .validators import NumpyArray


class Topic(BaseModel):
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
    id: Optional[int] = None
    name: str
    is_fixed: bool = False
    embedding: NumpyArray = Field(
        default_factory=lambda: np.zeros(config.SEMANTIC_EMBEDDING_DIMENSION)
    )
    sentence_count: int = 0
    document_count: int = 0

    def __repr__(self):
        return f"Topic(id={self.id}, name={self.name})"


class TopicSimilarSentence(BaseModel):
    sentence_id: str
    document_id: str
    similarity: float
    content: str


class TopicEntity(BaseModel):
    entity: str
    type: str
    count: float


class TopicFrontendResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    is_fixed: bool
    sentence_count: int
    document_count: int
    sentences: list[TopicSimilarSentence]
    entities: list[TopicEntity]
    keywords: list[str]
