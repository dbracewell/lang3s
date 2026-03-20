import re
from typing import Any, Literal

from joblib import Parallel, delayed
from jsonlines import Writer, jsonlines
from pydantic import BaseModel
from tqdm import tqdm

from lang3s.data.io.serialization import deserialize
from lang3s.llm import LLMClient, Message
from lang3s.nlp.shared_types import Document

EXTRACTION_SYSTEM_PROMPT = """You are a precise information extraction engine. Your task is to identify a single, specific claim from a target sentence.
                            Extraction Rules:
                                Quantity: Extract EXACTLY ONE claim or ZERO claims.
                                Format: Output ONLY the requested fields. Do not provide reasoning, intro, or outro.
                                Normalization: Replace all pronouns (he, she, they, it) and vague references with specific entities found in the "Before" or "After" context.
                                Attribution: Identify the individual or group making the claim. Do not include this person in the CLAIM text itself.
                                Shorten: Claims must be 10 words or fewer.

                                Definitions:
                                OBJECTIVE: A statement that can be verified with data or evidence.
                                SUBJECTIVE: An opinion, belief, or viewpoint.
                                NO_CLAIM: Use if the target contains no clear assertion.
"""

JUDGMENT_SYSTEM_PROMPT = """You are an NLP expert annotator. Your task is to judge an claim extraction annotation.
                            You should answer only with TRUE (the annotation is correct) or FALSE (the annotation is incorrect).
                            Do not provide reasoning, intro, or outro.
                            
                            Judgment Rules:
                                Examine the BEFORE and AFTER context to determine if the CLAIM extracted from the TARGET
                                along with its LABEL and source are correct.

                                Claim Definition:
                                A short concise statement.
                                Claims can either be:
                                    SUBJECTIVE: A verifiable statement that can be proven FACTUAL or NOT FACTUAL.
                                    OBJECTIVE: An opinion, belief, stance, or viewpoint about topic, physical entity (person, product, etc.), social situation, etc.
                            
                                Label Definitions:
                                OBJECTIVE: A statement that can be verified with data or evidence.
                                SUBJECTIVE: An opinion, belief, or viewpoint.
                                NO_CLAIM: Use if the target contains no clear assertion.
"""

EXTRACTION_PROMPT_TEMPLATE = """
Example:
Before: It is expecting annual sales growth of between 1% and 3% for the month. Consumer confidence figures are considered a key economic indicator because consumer spending accounts for about two thirds of all economic activity in the United States.
Target: "The continuing economic expansion, combined with job growth, has consumers ending this year on a high note," said Lynn Franco, director of the Conference Board's consumer research centre.
After: "And consumers' outlook suggests that the economy will continue to expand in the first half of next year."
The overall US economy has performed strongly in recent months, prompting the Federal Reserve to increase interest rates five times since June.

CLAIM: Economic expansion and job growth causes increase in consumer confidence.
LABEL: OBJECTIVE
SOURCE: Lynn Franco

Example:
Before: My friend and I were meeting for happy hour after work, I got there early to grab seats at the bar and the attractive female bartender standing in front of where I sat down walked away to let the male bartender take my order.
Target:  My conventionally attractive friend entered about 2 minutes later and the female bartender came back to take his order the rest of the night.
After: It didn’t feel great but my male bartender never left me waiting for a drink so I can’t complain too much.

CLAIM: 
LABEL: NO_CLAIM
SOURCE: AUTHOR

Example:
Before: I'd prefer not to share a CNN story, but it does address an important divide in terms of the states that want to "tax the rich", i.e. soak the rich, versus those that don't. Can you guess how that split is determined?
Target:  Yes, if it's a blue state, they want to keep on spending plenty and soak the rich to pay for that, and red states seem to generally be in better fiscal shape, and would prefer not to have confiscatory taxation on their highest wage earners/richest residents.
After: God forbid we address budget deficits by cutting spending. No, instead let's make those "greedy" rich people pay for it. No, don't tax me more, get that rich guy over there! He's also evil btw, because he's successful and rich, and of course that kind of success needs to be punished, and the fruits of those ill-gotten gains should be confiscated by the state.

CLAIM: Blue states overspend and ask the rich to pay for it.
LABEL: SUBJECTIVE
SOURCE: AUTHOR


Task:
Before: {BEFORE}
Target: {TARGET}
After: {AFTER}

Output:
CLAIM: [Concise statement or EMPTY]
LABEL: [SUBJECTIVE / OBJECTIVE / NO_CLAIM]
SOURCE: [Entity name, AUTHOR or UNKNOWN]
"""


JUDGMENT_PROMPT_TEMPLATE = """
Before: {BEFORE}
Target: {TARGET}
AFTER: {AFTER}

CLAIM: {CLAIM}
LABEL: {LABEL}
SOURCE: {SOURCE}
"""


class ClaimGeneration(BaseModel):
    claim: str
    label: Literal["SUBJECTIVE", "OBJECTIVE", "NO_CLAIM"]
    source: str | None = None


def generate(
    client: LLMClient,
    system_prompt: str,
    prompt: str,
    response_model: ClaimGeneration = None,
):
    response = client.sync_chat_completion_last_event(
        messages=[
            Message.system(system_prompt),
            Message.user(prompt),
        ],
        response_model=response_model,
    )
    return response


def process_data(path: str, writer: Writer, max_documents: int = 700):
    doc: Document
    client = LLMClient(model_name="qwen/qwen3-4b-2507")
    processed = 0
    for doc in tqdm.tqdm(deserialize(path)):
        sentences = doc.text.sentences
        prompts = []
        for i in range(len(sentences)):
            before = []
            for j in range(max(0, i - 2), i):
                before.append(sentences[j].text_with_coref())

            after = []
            for j in range(i + 1, min(i + 3, len(sentences))):
                after.append(sentences[j].text_with_coref())

            active_prompt = EXTRACTION_PROMPT_TEMPLATE.format(
                BEFORE="\n".join(before),
                AFTER="\n".join(after),
                TARGET=sentences[i].text_with_coref(),
            )

            prompts.append(
                (
                    before,
                    after,
                    sentences[i].text_with_coref(),
                    active_prompt,
                )
            )

        with Parallel(n_jobs=-1, backend="threading") as parallel:
            responses = parallel(
                delayed(generate)(
                    client, EXTRACTION_SYSTEM_PROMPT, data[-1], ClaimGeneration
                )
                for data in prompts
            )

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
                        "label": response.parsed.label,
                        "claim": response.parsed.claim,
                        "source": response.parsed.source,
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
    # with jsonlines.open("/Users/ik/prj/data/claim_extraction.jsonl", "w") as writer:
    #     process_data("/Users/ik/prj/data/reddit_style_corpus.docs", writer)
    #     process_data("/Users/ik/prj/data/news.docs", writer)

    judge = LLMClient(model_name="nvidia/nemotron-3-nano")
    skip = 3840
    with jsonlines.open(
        "/Users/ik/prj/data/claim_extraction_adjudicated.jsonl", "a"
    ) as writer:
        with tqdm(
            jsonlines.open("/Users/ik/prj/data/claim_extraction.jsonl")
        ) as reader:
            for example in reader:
                skip -= 1
                if skip >= 0:
                    continue
                is_valid = judge_example(example, judge)
                if not is_valid:
                    example["label"] = "NO_CLAIM"
                writer.write(example)


if __name__ == "__main__":
    main()
