from jsonlines import Writer, jsonlines
from lang3s.data.io.serialization import deserialize
from lang3s.llm import LLMClient, Message
from lang3s.nlp.shared_types import Document
from pydantic import BaseModel
from tqdm import tqdm

EXTRACTION_SYSTEM_PROMPT = """
You are a precise information extraction engine. 
Your task is to extract zero or more CLAIMS from the target document.

A CLAIM must be a statement of fact or a specific assertion about the world. 
It must not describe the act of speaking or comparing (e.g., avoid "X compared Y to Z" or "X said Y is like Z").

Extraction Rules:
1. Format: Output ONLY the requested fields. No reasoning or conversational filler.
2. Assertive Reconstruction: Rewrite the claim as a direct assertion. 
   - BAD: "The guide compared Protestant Europe to the Taliban."
   - GOOD: "Protestant Europe's religious violence is comparable to the modern Taliban."
3. Normalization: Replace all pronouns and vague references with specific entities using the context.
4. Attribution: Identify the individual making the claim as the SOURCE. The SOURCE should be an ENTITY (resolve pronouns using the context), AUTHOR. or UNKNOWN. 
5. Constraints: Maximum 15 words per claim.

Validation Rules:
- Avoid meta-commentary (e.g., "The author believes...", "A comparison was made...").

Confidence Guidelines:
- 0.9+: Clear, declarative factual statement.
- 0.5-0.8: Ambiguous, requires context, or uses soft language.
- <0.5: Sarcasm, fragmented text, or subjective opinion.
""".strip()

JUDGMENT_SYSTEM_PROMPT = """You are an NLP expert annotator. Your task is to judge an claim extraction annotation.
                            You should answer only with TRUE (the annotation is correct) or FALSE (the annotation is incorrect).
                            Do not provide reasoning, intro, or outro.

                            Judgment Rules:
                                Examine the BEFORE and AFTER context to determine if the CLAIM extracted from the TARGET
                                along with its LABEL and source are correct.

                                Claim Definition: A short concise statement.
                                Claims can either be:
                                    OBJECTIVE: A verifiable statement that can be proven FACTUAL or NOT FACTUAL.
                                    SUBJECTIVE: An opinion, belief, stance, or viewpoint about topic, physical entity (person, product, etc.), social situation, etc.
                                    NO_CLAIM: Use if the target contains no clear assertion.

                                Label Definitions:
                                OBJECTIVE: A statement that can be verified with data or evidence.
                                SUBJECTIVE: An opinion, belief, or viewpoint.
                                NO_CLAIM: Use if the target contains no clear assertion.
"""


class ClaimExample(BaseModel):
    claim: str
    confidence: float
    reasoning: str
    source: str | None = None


class DocumentClaims(BaseModel):
    claims: list[ClaimExample]


def generate(
    client: LLMClient,
    system_prompt: str,
    prompt: str,
    response_model: type[DocumentClaims] | None = None,
):
    response = client.sync_chat_completion_last_event(
        messages=[
            Message.system(system_prompt),
            Message.user(prompt),
        ],
        response_model=response_model,
    )
    return response


def process_data(
    path: str,
    writer: Writer,
    max_documents: int = 1000,
):
    doc: Document
    client = LLMClient(model_name="openai/gpt-oss-20b")
    processed = 0
    for doc in tqdm(deserialize(path)):
        text = doc.text.text
        response = generate(client, EXTRACTION_SYSTEM_PROMPT, text, DocumentClaims)
        if response.exception:
            print(response.exception)
        elif response.parsed:
            writer.write({"input": text, "claims": response.parsed.model_dump()})

        processed += 1
        if processed >= max_documents:
            return


def main():
    with jsonlines.open(
        "/Users/ik/prj/data/document_claim_extraction.jsonl", "w"
    ) as writer:
        process_data(
            "/Users/ik/prj/data/reddit_style_corpus.docs",
            writer,
            max_documents=1000,
        )
        process_data(
            "/Users/ik/prj/data/news.docs",
            writer,
            max_documents=2000,
        )
        process_data(
            "/Users/ik/prj/data/kant.docs",
            writer,
            max_documents=2000,
        )


main()
