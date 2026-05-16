import random
from random import shuffle

from jsonlines import jsonlines
from lang3s.data.io.serialization import deserialize
from lang3s.llm import LLMClient, Message
from lang3s.nlp.shared_types import Document
from pydantic import BaseModel
from tqdm import tqdm


class ClaimExample(BaseModel):
    claim: str
    type: str
    source: str
    target: str
    sentiment: str


class DocumentClaims(BaseModel):
    claims: list[ClaimExample]


EXTRACTION_SYSTEM_PROMPT = """
You are an expert analytical engine specialized in extracting structured claims from text. Your task is to analyze the provided document and extract all distinct, meaningful claims made by the author or entities mentioned within the text.

### DEFINITIONS
A "CLAIM" is a specific point of view, assertion, or stance about an entity, concept, or topic. 
* Do NOT extract general actions, social interactions, or fleeting emotional states (e.g., "The speaker was chatting with someone," "He felt tired," or "They vibed"). 

Claims fall into two strict categories:

1. OBJECTIVE CLAIMS
* Verifiable statements
* Reported facts (even if disputed or historically inaccurate)
* Statements about events or actions
* Predictions stated as fact
* Example: "Leading indicators show the economy is weakening."

2. SUBJECTIVE CLAIMS
* Personal points of view, assertions, or stances about SPECIFIC entities, concepts, or topics. 
* Example: "The price of living is too high."

### WHAT IS NOT A CLAIM (CRITICAL)
* Actions taken by the author (e.g. Author wore only shorts, jacket, beanie, and gloves.)
* Author state (e.g. Author's leggings revealed her underwear)
* Examples:
* Author was late for work after oversleeping
* The author is screwed for the midterm.
* The author hates ADHD meds.

### EXTRACTION RULES
1. ATOMIC & CONCISE: Every extracted claim must be a single, self-contained idea. Paraphrase or condense the text so that the claim is strictly 15 words/tokens or fewer. AVOID "Author ..."
2. SOURCE NORMALIZATION: Identify exactly who is making the claim. If it is the writer of the document, use "Author". If it is a person or organization mentioned in the text, normalize their name (e.g., use "Federal Reserve" instead of "they" or "the Fed").
3. TARGET IDENTIFICATION: Identify the primary entity, concept, or topic the claim is directed at (e.g., "Cost of Living", "US Economy", "Acme Corp").
4. SENTIMENT RULES: Evaluate the sentiment of the claim as Positive, Negative, or Neutral. 
   * CRITICAL: If a claim is classified as "Objective", its sentiment MUST be strictly "Neutral". Subjective claims can be Positive, Negative, or Neutral.

### OUTPUT FORMAT
You must respond ONLY with a valid JSON array of objects, using the following schema. Do not include markdown formatting like ```json, just output the raw JSON array.

[
  {
    "claim": "String (<= 15 tokens, atomic and concise)",
    "source": "String (Normalized entity name or 'Author')",
    "target": "String (Who/what the claim is about)",
    "type": "String (Must be exactly 'Objective' or 'Subjective')",
    "sentiment": "String (Must be 'Positive', 'Negative', or 'Neutral'. MUST be 'Neutral' if type is 'Objective')"
  }
]

### INPUT TEXT
{USER_INPUT_TEXT_HERE}
""".strip()


def create_prompt(
    system_prompt: str,
    prompt: str,
):
    active_prompt = system_prompt.replace("{USER_INPUT_TEXT_HERE}", prompt)
    return prompt, [Message.user(active_prompt)]


def random_sample(
    path: str,
    sample_size: int,
):
    doc: Document
    sample = []
    for doc in tqdm(deserialize(path)):
        text = doc.text.text
        if random.randint(0, 100) < 30:
            sample.append(create_prompt(EXTRACTION_SYSTEM_PROMPT, text))

        if len(sample) == sample_size:
            return sample

    return sample


def main():
    client = LLMClient(
        model_name="gpt-5.4-mini",
        api_key="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",
        llm_host="https://api.openai.com",
    )
    with jsonlines.open(
        "/Users/ik/prj/data/document_claim_extraction_v3.jsonl", "w"
    ) as writer:
        data = []
        data.extend(random_sample("/Users/ik/prj/data/reddit_style_corpus.docs", 500))
        data.extend(random_sample("/Users/ik/prj/data/news.docs", 500))
        data.extend(random_sample("/Users/ik/prj/data/kant.docs", 500))
        shuffle(data)
        for text, messages in data:
            response = client.sync_chat_completion_last_event(
                messages=messages, response_model=DocumentClaims
            )
            if response.exception:
                print(response.exception)
            elif response.parsed:
                writer.write({"input": text, "claims": response.parsed.model_dump()})


#

main()
