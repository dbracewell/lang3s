from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..models.claim import Certainty, ClaimType, Modality, Sentiment
from .validators import NumpyArray

if TYPE_CHECKING:
    from .text import Document


class Claim(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)
    id: Optional[uuid.UUID] = Field(default=None)
    document_id: str
    claim: str
    type_: ClaimType
    source: str
    subject: str
    predicate: str
    object: str
    stance: str
    certainty: Certainty
    modality: Modality
    negation: bool
    condition: Optional[str] = Field(default=None)
    time: Optional[str] = Field(default=None)
    location: Optional[str] = Field(default=None)
    evidence: Optional[str] = Field(default=None)
    sentiment: Sentiment
    keywords: list[str]
    embedding: NumpyArray


class ClaimList(BaseModel):
    claims: list[Claim]


class DocumentClaimRequest(BaseModel):
    documentId: str
    sentences: list[str]

    @classmethod
    def create(cls, document: Document) -> DocumentClaimRequest:
        return cls(
            documentId=document.id,
            sentences=[s.content for s in document.text.sentences],
        )
