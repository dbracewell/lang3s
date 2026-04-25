from __future__ import annotations

from pydantic import BaseModel


class ClaimExample(BaseModel):
    claim: str
    type: str
    source: str
    target: str
    sentiment: str


class DocumentClaims(BaseModel):
    claims: list[ClaimExample]


class DocumentClaimRequest(BaseModel):
    documentId: str
    sentences: list[str]
