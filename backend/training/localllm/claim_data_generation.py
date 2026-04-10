import random
import re
from typing import Any

from joblib import Parallel, delayed
from jsonlines import Writer, jsonlines
from lang3s.data.io.serialization import deserialize
from lang3s.llm import LLMClient, LLMEvent, Message
from lang3s.nlp.shared_types import Document
from pydantic import BaseModel
from tqdm import tqdm

EXTRACTION_SYSTEM_PROMPT = """
You are a precise information extraction engine. 
Your task is to extract a single, independent, verifiable CLAIM from the target sentence.

A CLAIM must be a statement of fact or a specific assertion about the world. It must not describe the act of speaking or comparing (e.g., avoid "X compared Y to Z" or "X said Y is like Z").

Extraction Rules:
1. Quantity: Extract EXACTLY ZERO or ONE claims.
2. Format: Output ONLY the requested fields. No reasoning or conversational filler.
3. Assertive Reconstruction: Rewrite the claim as a direct assertion. 
   - BAD: "The guide compared Protestant Europe to the Taliban."
   - GOOD: "Protestant Europe's religious violence is comparable to the modern Taliban."
4. Normalization: Replace all pronouns and vague references with specific entities using the context.
5. Attribution: Identify the individual making the claim as the SOURCE. The SOURCE should be an ENTITY (resolve pronouns using the context), AUTHOR. or UNKNOWN. 
6. Constraints: Maximum 15 words.

Validation Rules:
- If no verifiable assertion exists, leave CLAIM and SOURCE empty.
- Avoid meta-commentary (e.g., "The author believes...", "A comparison was made...").

Output the result in JSON format with the following keys:
1. claim: [The assertion]
2. source: [The entity]
3. confidence: [A float between 0.0 and 1.0]
4. reasoning: [Briefly why you gave this score]

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


EXTRACTION_PROMPT_TEMPLATE = """
### Examples

Example 1: Formal News (Direct Attribution)
Target: "The continuing economic expansion, combined with job growth, has consumers ending this year on a high note," said Lynn Franco, director of the Conference Board's consumer research centre.
The overall US economy has performed strongly in recent months, prompting the Federal Reserve to increase interest rates five times since June.

CLAIM: Economic expansion and job growth are driving high US consumer confidence.
SOURCE: Lynn Franco

---

Example 2: Informal Social Media (Implicit Assertion)
Target: He also detailed iconoclast violence and the regression of women's rights in the early modern era and compared it to women's rights in fundamentalist Islamic countries and the destruction of Palmyra.

CLAIM: Early modern Protestantism involved extreme iconoclast violence and the regression of women's rights.
SOURCE: TOUR GUIDE

---

Example 3: Author's Belief
Target:  Yes, if it's a blue state, they want to keep on spending plenty and soak the rich to pay for that, and red states seem to generally be in better fiscal shape, and would prefer not to have confiscatory taxation on their highest wage earners/richest residents.

CLAIM: Blue states overspend and ask the rich to pay for it.
SOURCE: AUTHOR

---

Example 4: No Verifiable Claim
Target:  My conventionally attractive friend entered about 2 minutes later and the female bartender came back to take his order the rest of the night.

CLAIM: 
SOURCE: 

---

Example 5: No Verifiable Claim
Target:  Can anyone confirm whether his comparison stands?

CLAIM: 
SOURCE: 

--

### Task
Target: {TARGET}

Output:
CLAIM:
SOURCE:
""".strip()


JUDGMENT_PROMPT_TEMPLATE = """
Before: {BEFORE}
Target: {TARGET}
AFTER: {AFTER}

CLAIM: {CLAIM}
SOURCE: {SOURCE}
"""


class ClaimGeneration(BaseModel):
    claim: str
    confidence: float
    reasoning: str
    source: str | None = None


def generate(
    client: LLMClient,
    system_prompt: str,
    prompt: str,
    response_model: type[ClaimGeneration] | None = None,
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
    max_examples_per_document: int = 5,
):
    doc: Document
    client = LLMClient()
    processed = 0
    for doc in tqdm(deserialize(path)):
        sentences = doc.text.sentences
        prompts = []
        for i in range(len(sentences)):
            if sentences[i].is_stopword:
                continue

            before = []
            for j in range(max(0, i - 2), i):
                before.append(sentences[j].text_with_coref())

            after = []
            for j in range(i + 1, min(i + 3, len(sentences))):
                after.append(sentences[j].text_with_coref())

            # active_prompt = EXTRACTION_PROMPT_TEMPLATE.format(
            #     TARGET=sentences[i].text_with_coref(),
            # )

            active_prompt = f"CONTEXT: {' '.join(before)} SENTENCE: {sentences[i].text_with_coref()}"

            prompts.append(
                (
                    before,
                    after,
                    sentences[i].text_with_coref(),
                    active_prompt,
                )
            )

        random.shuffle(prompts)
        prompts = prompts[: max(1, max_examples_per_document)]
        with Parallel(n_jobs=3, backend="threading") as parallel:
            responses = parallel(
                delayed(generate)(
                    client,
                    EXTRACTION_SYSTEM_PROMPT,
                    data[-1],
                    ClaimGeneration,
                )
                for data in prompts
            )

        response: LLMEvent[ClaimGeneration]
        for response, data in zip(responses, prompts):
            (
                before,
                after,
                target,
                active_prompt,
            ) = data
            if response.exception:
                print(response.exception)
            else:
                writer.write(
                    {
                        "input": {
                            "before_text": " ".join(before),
                            "after_text": " ".join(after),
                            "target_text": target,
                        },
                        "claim": response.parsed.claim,
                        "source": response.parsed.source,
                        "confidence": response.parsed.confidence,
                        "reasoning": response.parsed.reasoning,
                    }
                )

        processed += 1
        if processed >= max_documents:
            return


def judge_example(example: dict[str, Any], judge: LLMClient):
    active_prompt = JUDGMENT_PROMPT_TEMPLATE.format(
        BEFORE=example["input"]["before_text"],
        AFTER=example["input"]["after_text"],
        TARGET=example["input"]["target_text"],
        CLAIM=example["claim"],
        LABEL=example["label"],
        SOURCE=example["source"],
    )
    result = generate(judge, JUDGMENT_SYSTEM_PROMPT, active_prompt)
    if not result.exception:
        answer = (
            re.sub(r"<think>.*?</think>", "", result.content, flags=re.DOTALL)
            .strip()
            .upper()
        )
        return answer == "TRUE"
    return False


def main():
    # with jsonlines.open("/Users/ik/prj/data/claim_extraction_2.jsonl", "w") as writer:
    #     process_data(
    #         "/Users/ik/prj/data/reddit_style_corpus.docs",
    #         writer,
    #         max_documents=1000,
    #     )
    #     process_data(
    #         "/Users/ik/prj/data/news.docs",
    #         writer,
    #         max_documents=2000,
    #     )
    #     process_data(
    #         "/Users/ik/prj/data/kant.docs",
    #         writer,
    #         max_documents=2000,
    #     )

    with jsonlines.open(
        "/Users/ik/prj/data/claim_extraction_final.jsonl", "w"
    ) as writer:
        with jsonlines.open("/Users/ik/prj/data/claim_extraction_gpt.jsonl") as reader:
            for example in reader:
                claim = example["claim"]
                confidence = example["confidence"]
                if confidence < 0.8 and claim.strip():
                    print(confidence, claim)
                    continue
                writer.write(example)

    # judge = LLMClient(model_name="nvidia/nemotron-3-nano")
    # skip = 3840
    # with jsonlines.open(
    #     "/Users/ik/prj/data/claim_extraction_adjudicated.jsonl", "a"
    # ) as writer:
    #     with tqdm(
    #         jsonlines.open("/Users/ik/prj/data/claim_extraction.jsonl")
    #     ) as reader:
    #         for example in reader:
    #             skip -= 1
    #             if skip >= 0:
    #                 continue
    #             is_valid = judge_example(example, judge)
    #             if not is_valid:
    #                 example["label"] = "NO_CLAIM"
    #             writer.write(example)


if __name__ == "__main__":
    main()
