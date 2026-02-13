from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from lang3s.llm.chat_model import ChatModel
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
    type: Literal["CLAIM", "SOURCE", "META"]
    source: str | None = Field(default=None)
    entities: list[str] = Field(default_factory=list)


class ClaimExtraction(BaseModel):
    claims: list[Claim]


__SYSTEM_PROMPT__ = """
    You are an expert Knowledge Graph engineer. Your goal is to extract atomic facts from text for a database.

    Follow these strict rules:
    1. **SPLIT**: Break complex sentences into atomic, independent statements.
    2. **RESOLVE**: Replace ALL pronouns ("It", "They", "He") with the specific entity names. Make SURE TO USE information from other sentences to resolve the entity names. ALL SENTENCES PROVIDED ARE FROM THE SAME DOCUMENT.
       - BAD: "It is expecting growth."
       - GOOD: "Wal-Mart is expecting growth."
    3. **CLASSIFY**:
       - `CLAIM`: Real-world events, actions, forecasts, or findings (e.g., "Prices rose", "Fed increased rates"). This should NOT include source statements like "Lynn said", "said by Lynn", "Lynn responded", etc.
       - `SOURCE`: Pure attribution or metadata (e.g., "The survey said", "According to data", "Joe said", "Bush speculates").
       - `META`: Text structure (e.g., "See Table 1").     
    4. **ATTRIBUTE**:
       - State the source of the claim.
       - If NO source can be attributed, reply with null 
    5. **EXTRACT**:
       - Extract the entities involved in the claim.

    Output a JSON list of objects.  
"""

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


def _get_prompt_and_examples() -> list[dict[str, Any]]:
    messages = [
        {"role": "system", "content": __SYSTEM_PROMPT__},
    ]
    for user, assistant in __EXAMPLES:
        messages.append(
            {
                "role": "user",
                "content": json.dumps(user),
            }
        )
        messages.append(
            {
                "role": "assistant",
                "content": assistant.model_dump_json(),
            }
        )
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


def extract_claims(client: ChatModel, document: ClaimDocument) -> list[Claim]:
    messages = _base_messages.copy()
    messages.append(
        {
            "role": "user",
            "content": json.dumps([s.model_dump_json() for s in document.sentences]),
        }
    )
    response = client.chat(messages=messages, response_model=ClaimExtraction)
    return [claim for claim in response.parsed.claims if claim.type == "CLAIM"]
