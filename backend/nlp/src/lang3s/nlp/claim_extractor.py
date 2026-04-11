from __future__ import annotations

from pydantic import BaseModel


class ClaimExample(BaseModel):
    claim: str
    source: str | None = None


class DocumentClaims(BaseModel):
    claims: list[ClaimExample]


class DocumentClaimRequest(BaseModel):
    documentId: str
    text: str
