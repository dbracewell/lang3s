from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from lang3s.nlp.shared_types import Document


class Claim(BaseModel):
    text: str
    # target: str
    # stance: str
    # time: str | None
    # cause: str | None
    type: Literal[
        "fact",
        "definition",
        "value",
        "policy",
        "causation",
        "comparison",
        "contingency",
    ]
    # type_confidence: Literal["low", "medium", "high"]
    sentiment: Literal["positive", "negative", "neutral"]


class ClaimList(BaseModel):
    claims: list[Claim]


class DocumentClaimRequest(BaseModel):
    documentId: str
    sentences: list[str]


def create_claim_request(document: Document) -> DocumentClaimRequest:
    claim_sentences = []
    doc_sentences = document.text.sentences
    for i in range(len(doc_sentences)):
        sentence = doc_sentences[i]
        if sentence.is_stopword or sentence.text.endswith("?"):
            continue

        claim_metadata = sentence["claim"]
        # if claim_metadata is None:
        #     continue

        # is_claim = claim_metadata["value"]
        # claim_confidence = claim_metadata["confidence"]
        # if not is_claim or claim_confidence <= 0.9:
        #     continue

        context = " ".join(s.text for s in doc_sentences[i - 2 : i])
        claim_sentences.append(f"CONTEXT: {context}\nSENTENCE: {sentence.text}")

    return DocumentClaimRequest(documentId=document.id, sentences=claim_sentences)
