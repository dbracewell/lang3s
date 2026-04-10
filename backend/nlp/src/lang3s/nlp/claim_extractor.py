from __future__ import annotations

from pydantic import BaseModel, Field

from lang3s.llm import Message
from lang3s.nlp.shared_types import Document
from lang3s.services.client.local_llm_client import LocalLLMClient


class ClaimDocument(BaseModel):
    document_id: str
    sentences: list[SentenceContext] = Field(default_factory=list)


class SentenceContext(BaseModel):
    sentence_aid: str
    text: str


class ClaimExample(BaseModel):
    claim: str
    confidence: float
    source: str | None = None


class DocumentClaims(BaseModel):
    claims: list[ClaimExample]


class DocumentClaimRequest(BaseModel):
    documentId: str
    text: str


def create_sentence_context(document: Document) -> ClaimDocument:
    return ClaimDocument(
        document_id=document.id,
        sentences=[
            SentenceContext(sentence_aid=s.id, text=s.text_with_coref())
            for s in document.text.sentences
        ],
    )


def extract_claims(client: LocalLLMClient, document: str) -> DocumentClaims:
    return client.generate(
        messages=[Message.user(f"Extract claims from: {document}")],
        adapter_name="claim",
        temperature=0.0,
        response_model=DocumentClaims,
    )
