from __future__ import annotations

import json
import os.path
import re
from typing import Literal

from pydantic import BaseModel, Field

from lang3s import config
from lang3s.llm import LLMClient, Message
from lang3s.models.text_generator import FineTunedLongT5
from lang3s.nlp.shared_types import Document


class ClaimDocument(BaseModel):
    document_id: str
    sentences: list[SentenceContext] = Field(default_factory=list)


class SentenceContext(BaseModel):
    sentence_aid: str
    text: str


class Claim(BaseModel):
    sentence_aid: str
    text: str
    type: Literal["OBJECTIVE", "SUBJECTIVE", "CLAIM", "META"]
    source: str | None = Field(default=None)
    entities: list[str] = Field(default_factory=list)


class ClaimExtraction(BaseModel):
    claims: list[Claim]


__SYSTEM_PROMPT__ = """
Please break down the following text into simple, self-contained propositions. Ensure that each proposition meets the following criteria:

1. Express a Single Fact: Each proposition should state one specific fact or claim.
2. Be Understandable Without Context: The proposition should be self-contained, meaning it can be understood without needing additional context.
3. Use Full Names, Not Pronouns: Avoid pronouns or ambiguous references; use full entity names.
4. Include Relevant Dates/Qualifiers: If applicable, include necessary dates, times, and qualifiers to make the fact precise.
5. Contain One Subject-Predicate Relationship: Focus on a single subject and its corresponding action or attribute, without conjunctions or multiple clauses.
6. Do not output communication statements, like X said Y, X reported Y, X reported by Y. INSTEAD output X as the claim and Y as the source of the claim.
"""

__EXAMPLES = [
    (
        [
            {
                "sentence_aid": "abc567",
                "text": "In 1969, Neil Armstrong became the first person to walk on the Moon during the Apollo 11 mission.",
            },
        ],
        ClaimExtraction(
            claims=[
                Claim(
                    sentence_aid="abc567",
                    text="Neil Armstrong was an astronaut.",
                    type="CLAIM",
                    source=None,
                    entities=["Neil Armstrong", "astronaut"],
                ),
                Claim(
                    sentence_aid="abc567",
                    text="Neil Armstrong walked on the Moon in 1969.",
                    type="CLAIM",
                    source=None,
                    entities=["Neil Armstrong", "Moon", "1969"],
                ),
                Claim(
                    sentence_aid="abc567",
                    text="Neil Armstrong was the first person to walk on the Moon.",
                    type="CLAIM",
                    source=None,
                    entities=["Neil Armstrong", "person", "Moon"],
                ),
                Claim(
                    sentence_aid="abc567",
                    text="Neil Armstrong walked on the Moon during the Apollo 11 mission.",
                    type="CLAIM",
                    source=None,
                    entities=["Neil Armstrong", "Moon", "Apollo 11"],
                ),
                Claim(
                    sentence_aid="abc567",
                    text="The Apollo 11 mission occurred in 1969.",
                    type="CLAIM",
                    source=None,
                    entities=["Apollo 11", "1969"],
                ),
            ]
        ),
    ),
    (
        [
            {
                "sentence_aid": "abc567",
                "text": "As reported by Reuters, the President has ordered troops into Iraq to combat ISIS.",
            },
        ],
        ClaimExtraction(
            claims=[
                Claim(
                    sentence_aid="abc567",
                    text="The President has ordered troops into Iraq.",
                    type="CLAIM",
                    source="Reuters",
                    entities=["President", "troops", "Iraq"],
                ),
                Claim(
                    sentence_aid="abc567",
                    text="Troops will combat ISIS in Iraq.",
                    type="CLAIM",
                    source="Reuters",
                    entities=["troops", "ISIS", "Iraq"],
                ),
            ]
        ),
    ),
]


def _get_prompt_and_examples() -> list[Message]:
    messages = [Message.system(__SYSTEM_PROMPT__)]
    for user, assistant in __EXAMPLES:
        messages.append(Message.user(json.dumps(user)))
        messages.append(Message.assistant(json.dumps(assistant.model_dump_json())))
    return messages


_base_messages = _get_prompt_and_examples()


def create_sentence_context(document: Document) -> ClaimDocument:
    return ClaimDocument(
        document_id=document.id,
        sentences=[
            SentenceContext(sentence_aid=s.id, text=s.text_with_coref())
            for s in document.text.sentences
        ],
    )


def extract_claims(client: LLMClient, document: ClaimDocument) -> list[Claim]:
    messages = _base_messages.copy()
    messages.append(
        Message.user(json.dumps([s.model_dump_json() for s in document.sentences]))
    )

    final_claims = []
    x = []
    for i in range(len(document.sentences)):
        before_text = []
        for j in range(max(0, i - 2), i):
            before_text.append(document.sentences[j].text)
        after_text = []
        for j in range(i + 1, min(len(document.sentences), i + 3)):
            after_text.append(document.sentences[j].text)

        x.append(f"""Extract the claim from the TARGET given the TARGET and BEFORE and AFTER context:
                                                     BEFORE: {" ".join(before_text)}
                                                     TARGET: {document.sentences[i].text}
                                                     AFTER: {" ".join(after_text)}""")

    results = get_claim_model().generate(x)
    for response, sentence in zip(results, document.sentences):
        parts = [
            p.strip() for p in re.split(r"CLAIM:|LABEL:|SOURCE:", response) if p.strip()
        ]
        if len(parts) < 3:
            continue
        text, label, source = parts
        if label in ("SUBJECTIVE", "OBJECTIVE"):
            claim = Claim(
                sentence_aid=sentence.sentence_aid,
                text=text,
                type=label,
                source=source,
            )
            final_claims.append(claim)

    return final_claims

    # logger = get_logger("CLAIM_EXTRACTOR")
    # with try_catch(on_error=lambda e: logger.error(e)):
    #     response = client.sync_chat_completion_last_event(
    #         messages=messages,
    #         response_model=ClaimExtraction,
    #         max_tokens=4000,
    #     )
    #     return [
    #         claim
    #         for claim in response.parsed.claims
    #         if claim.type == "CLAIM" and claim.text.strip()
    #     ]
    # return []


_claim_model: FineTunedLongT5 | None = None


def get_claim_model():
    global _claim_model
    if _claim_model is None:
        _claim_model = FineTunedLongT5.load_model(
            os.path.join(config.MODELS_DIR, "long_t5")
        )
    return _claim_model
