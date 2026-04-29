import random
import re
from typing import Literal

from jsonlines import jsonlines
from lang3s.data.io.serialization import deserialize
from lang3s.llm import LLMClient, Message
from lang3s.nlp.shared_types import Document
from lang3s.parallel.core import Engine
from lang3s.parallel.manager import TaskManager
from pydantic import BaseModel, Field
from tqdm import tqdm


def is_question(text: str) -> bool:
    return "?" in text.strip()


def is_personal_action(text: str) -> bool:
    return bool(
        re.match(
            r"^\s*(I|we)\s+(am|was|were|feel|felt|went|did|have|had|wonder)\b",
            text.lower(),
        )
    )


def create_prompt(sentence: str):
    return """
Classify whether this sentence contains a claim.

A CLAIM is any sentence that asserts or reports a statement about the world that could be true or false.

This includes:
- Direct statements (e.g., "X is true")
- Reported statements (e.g., "People say X", "We were told X")
- Hedged statements (e.g., "Apparently X", "It seems X")

If a sentence reports what someone said, wrote, believed, or mentioned,
it IS a claim if it contains a factual statement about the world.

Rules:
- If It does not assert any proposition about the world it is NOT a claim.
- Questions are NOT claims
- Commands, instructions, and requests are NOT claims.
- Statements about trying, asking, wondering, or figuring something out are NOT claims.
- Statements that only describe the speaker (identity, background, feelings, activities) are NOT claims.
- If a sentence reports what someone said AND includes a factual statement, it IS a claim
- Incomplete sentences or fragments are NOT claims

If the sentence contains verbs like:
"said", "stated", "claimed", "announced", "reported", "according to"

Then it is VERY LIKELY a claim unless it is clearly only about the speaker’s action with no content.

Example:
"I went to the store" → false
"We were told the Ottoman Empire benefited from trade" → true
"Economic indicators show the economy is improving" → true
"Wal-Mart is reportin better than expected sales" → true
"I would like ..." → false
"I would be intersted in ..." → false

Return:
{{ "label": boolean, "confidence": "low|medium|high" }}

Does this sentence contain ANY proposition (claim) about the world, even indirectly?
{sentence}    
""".format(sentence=sentence).strip()


class Answer(BaseModel):
    label: bool
    confidence: Literal["low", "medium", "high"]


def random_sample(
    path: str,
    sample_size: int,
):
    doc: Document
    sample = []
    for doc in tqdm(deserialize(path)):
        for sentence in doc.text.sentences:
            if sentence.is_stopword:
                continue
            if is_question(sentence.text):
                continue
            if is_personal_action(sentence.text):
                pass

            if random.randint(0, 100) <= 20:
                sample.append((sentence.text, create_prompt(sentence.text)))
                break

        if len(sample) == sample_size:
            return sample

    return sample


def load_sentences(path: str):
    doc: Document
    sentences = []
    for doc in tqdm(deserialize(path)):
        for sentence in doc.text.sentences:
            if not sentence.is_stopword:
                sentences.append(sentence.text)
    return sentences


def process_task(obj):
    client = LLMClient(
        # model_name="gemma-4-26b-a4b-it-4bit",
        # api_key="1234",
        # llm_host="http://192.168.0.81:8000",
    )
    sentence, prompt = obj.data
    response = client.sync_chat_completion_last_event(
        messages=[Message.user(sentence)],
        response_model=Answer,
        top_p=0.1,
        temperature=0,
        max_tokens=200,
    )
    if response.exception:
        print(response.exception)
        return None
    elif response.parsed:
        answer = response.parsed
        return {
            "text": sentence,
            "label": answer.label,
            "confidence": answer.confidence,
        }
    return None


def main():
    with jsonlines.open(
        "/Users/ik/prj/data/document_claim_classifier.jsonl", "w"
    ) as writer:
        data = []
        # data.extend(load_sentences("/Users/ik/prj/data/reddit_style_corpus.docs"))
        # data.extend(load_sentences("/Users/ik/prj/data/news.docs"))
        # data.extend(load_sentences("/Users/ik/prj/data/kant.docs"))
        data.extend(random_sample("/Users/ik/prj/data/reddit_style_corpus.docs", 500))
        data.extend(random_sample("/Users/ik/prj/data/news.docs", 2_000))
        data.extend(random_sample("/Users/ik/prj/data/kant.docs", 2_000))
        random.shuffle(data)
        # data = data[:30_000]
        with TaskManager(engine=Engine.THREADING, workers=5) as runner:
            for obj in runner.map(process_task, data):
                if obj:
                    writer.write(obj)


if __name__ == "__main__":
    main()
