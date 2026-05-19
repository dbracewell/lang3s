from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from lang3s.nlp.shared_types import Document


class Claim(BaseModel):
    claim_text: str
    claim_type: Literal[
        "Fact",
        "Definition",
        "Value",
        "Policy",
        "Causation",
        "Comparison",
        "Contingency",
    ]
    source: str
    subject: str
    predicate: str
    object: str
    stance: str
    certainty: Literal[
        "certain",
        "probable",
        "possible",
        "speculative",
        "unknown",
    ]
    modality: Literal[
        "factual",
        "normative",
        "hypothetical",
        "conditional",
        "predictive",
    ]
    negation: bool
    condition: str | None
    time: str | None
    location: str | None
    evidence: str | None
    sentiment: Literal["positive", "negative", "neutral"] | None
    keywords: list[str]


class ClaimList(BaseModel):
    claims: list[Claim]


class DocumentClaimRequest(BaseModel):
    documentId: str
    sentences: list[str]


def create_claim_request(document: Document) -> DocumentClaimRequest:
    return DocumentClaimRequest(
        documentId=document.id,
        sentences=[s.text for s in document.text.sentences],
    )
