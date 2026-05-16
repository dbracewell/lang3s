import argparse
import json
import os
import re
import shutil
from random import shuffle

from jsonlines import jsonlines
from lang3s.data.parsers.text.common import normalize_text
from lang3s.llm import LLMClient, Message
from lang3s.llm.batch import create_batch_job_file
from openai import OpenAI

PROMPT = """
Claim Extraction Prompt

# Claim Extraction Task

You are an expert claim extraction system.

Your task is to extract ALL actionable claims from the provided text and context.

A CLAIM is any assertion, allegation, statement, judgment, prediction, recommendation, definition, comparison, or causal statement about the world that could theoretically be analyzed, verified, debated, supported, or contradicted.

---

# Claim Types

Classify each claim into EXACTLY ONE of the following types:

| Claim Type | Description |
|---|---|
| Fact | Asserts something true or false |
| Definition | Defines or categorizes something |
| Value | Expresses worth, morality, desirability, or judgment |
| Policy | Recommends an action or change |
| Causation | Asserts cause and effect |
| Comparison | Compares entities, situations, or ideas |
| Contingency | Conditional or hypothetical claims |

---

# Extraction Rules

- Extract explicit claims.
- Extract implied claims ONLY when strongly supported by the text.
- Ignore greetings, jokes, rhetorical fillers, and pure questions unless they contain an embedded assertion.
- Preserve the original meaning.
- Do NOT remove important qualifiers or hedging language.
- Handle negation carefully.
- Preserve uncertainty and modality words such as:
  - may
  - might
  - likely
  - possibly
  - should
  - must
- Split compound statements into separate claims when appropriate.
- Distinguish between:
  - author claims
  - quoted claims
  - reported claims
- Use the provided context to resolve pronouns and ambiguity.
- Do NOT invent unsupported information.
- Replace all pronouns (it, he, they, this, etc.) and vague references with the specific named entities they refer to from the CONTEXT.
- The extracted claim(s) must be completely understandable to a reader who has not seen the original text.
- If a sentence makes multiple distinct factual assertions, separate them into a numbered list of individual claims.
-  Claims should be no more than 15 words. 
- Do not hallucinate or add outside knowledge. Only use facts present in the document.



---

# Components To Extract

For each claim extract the following fields:

| Field | Description |
|---|---|
| source | Who or what makes the claim |
| claim_text | Concise normalized statement of the claim |
| claim_type | One allowed claim type |
| subject | Primary entity/topic |
| predicate | Asserted relation/action/state |
| object | Entity/outcome affected by the predicate |
| stance | supports, opposes, affirms, denies, neutral |
| certainty | certain, probable, possible, speculative, unknown |
| modality | factual, normative, hypothetical, conditional, predictive |
| negation | true or false |
| condition | Condition/precondition if present |
| time | Temporal reference if present |
| location | Geographic reference if present |
| evidence | Supporting evidence if explicitly cited |
| sentiment | positive, negative, neutral if applicable |
| keywords | One or more generic keywords covering the topic of the claim |
---

Do NOT extract:
- pure narrative events
- descriptions of actions taken by the speaker
- observations without broader propositional significance
- procedural statements
- experiential narration

Extract only claims that assert meaningful information, judgments, causation, recommendations, or externally relevant facts.

---

# Output Requirements

- Return ONLY valid JSON.
- Output a JSON array.
- One object per claim.
- Use `null` when information is missing.
- Do NOT include explanations outside the JSON.

---

# Example

## Input

> WHO researchers stated that smoking likely increases lung cancer risk in adults.

## Output

```json
[
  {
    "source": "WHO researchers",
    "claim_text": "Smoking increases lung cancer risk in adults.",
    "claim_type": "Causation",
    "subject": "smoking",
    "predicate": "increases risk of",
    "object": "lung cancer",
    "stance": "affirms",
    "certainty": "probable",
    "modality": "factual",
    "negation": false,
    "condition": null,
    "time": null,
    "location": null,
    "evidence": null,
    "sentiment": "negative",
    "keywords": ["health", "smoking", "cancer"]
  }
]
```

"""


def change_model(file: str, model_name: str = "gpt-5-mini"):
    backup_file = f"{file}.backup"
    if os.path.exists(backup_file):
        return
    combined_docs = []
    with jsonlines.open(file) as reader:
        for doc in reader:
            combined_docs.append(doc)
    shutil.move(file, backup_file)
    with jsonlines.open(file, "w") as writer:
        for doc in combined_docs:
            doc["body"]["model"] = model_name
            writer.write(doc)


def create_dataset(batch_input_file: str, num_batches: int, batch_size: int):
    combined_docs = []
    with jsonlines.open(os.path.expanduser("~/prj/data/base_corpus.jsonl")) as reader:
        for doc in reader:
            combined_docs.append(normalize_text(doc["content"]))
    shuffle(combined_docs)
    shuffle(combined_docs)
    shuffle(combined_docs)
    output_files = []
    for batch in range(num_batches):
        messages = []
        start = batch * batch_size
        end = (batch + 1) * batch_size
        for doc in combined_docs[start:end]:
            messages.append([Message.user(PROMPT + doc)])

        file = f"{batch_input_file}_{batch + 1}.jsonl"
        output_files.append(file)
        create_batch_job_file(
            messages,
            "gpt-5.4-mini",
            file,
        )

    return output_files


def submit_batch_job_file(batch_input_file):
    client = OpenAI()
    batch_file = client.files.create(
        file=open(
            batch_input_file,
            "rb",
        ),
        purpose="batch",
    )
    batch_job = client.batches.create(
        input_file_id=batch_file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
    )

    print(f"Batch Job ID: {batch_job.id}")


def fix_unescaped_json(bad_json: str) -> str:
    """
    Fixes unescaped double quotes inside JSON string values generated by LLMs.
    Works best on pretty-printed JSON (one key-value pair per line).
    """

    # Regex breakdown:
    # ^(\s*".+?"\s*:\s*")  -> Group 1: Matches the start of the line, the key, the colon, and opening quote
    # (.*)                 -> Group 2: Matches the actual string content (greedy, up to the last quote)
    # ("\s*,?\s*)$         -> Group 3: Matches the closing quote, optional comma, and trailing spaces
    pattern = re.compile(r'^(\s*".+?"\s*:\s*")(.*)("\s*,?\s*)$', re.MULTILINE)

    def replacer(match):
        start_format = match.group(1)
        inner_content = match.group(2)
        end_format = match.group(3)

        # 1. Temporarily unescape any quotes that the LLM *did* manage to escape
        #    This prevents double-escaping (turning \" into \\\")
        inner_content = inner_content.replace('\\"', '"')

        # 2. Escape all double quotes properly
        inner_content = inner_content.replace('"', '\\"')

        # 3. Reconstruct the line
        return start_format + inner_content + end_format

    # Apply the regex substitution
    return pattern.sub(replacer, bad_json)


def parse_batch_response(batch_input_file: str, batch_response_file: str):
    requests_ids = {}
    with jsonlines.open(batch_input_file) as reader:
        for doc in reader:
            request_id = doc["custom_id"]
            full_prompt = doc["body"]["messages"][0]["content"]
            document_text = full_prompt[len(PROMPT) :].strip()
            requests_ids[request_id] = document_text
    data = []
    with jsonlines.open(batch_response_file) as reader:
        for doc in reader:
            request_id = doc["custom_id"]
            response = doc["response"]["body"]["choices"][0]["message"]["content"]
            response = re.sub(r"```json\s+", "", response, re.MULTILINE)
            response = re.sub(r"```", "", response, re.MULTILINE)
            response = re.sub(r"\\'", "'", response, re.MULTILINE)
            response = fix_unescaped_json(response)
            try:
                response = json.loads(response)
                new_document = {
                    "messages": [
                        Message.user(
                            f"Extract claims from: {requests_ids[request_id]}"
                        ).to_dict(),
                        Message.assistant(json.dumps(response)).to_dict(),
                    ]
                }
                data.append(new_document)
            except Exception as e:
                print(response)
                print(e)

    return data


def create_final_file(
    batch_input_file: str, batch_response_file: str, num_batches: int
):
    combined_data = []
    for index in range(num_batches):
        if not os.path.exists(f"{batch_response_file}_{index + 1}.jsonl"):
            continue
        combined_data.extend(
            parse_batch_response(
                batch_input_file=f"{batch_input_file}_{index + 1}.jsonl",
                batch_response_file=f"{batch_response_file}_{index + 1}.jsonl",
            )
        )
    with jsonlines.open(
        os.path.expanduser("~/prj/data/claims/gpt-5.4-combined-claims.jsonl"), "w"
    ) as writer:
        for data in combined_data:
            writer.write(data)


if __name__ == "__main__":
    batch_input_file = os.path.expanduser(
        "~/prj/data/claims/GPT-Batch-Requests/claims_generation_dataset_v3"
    )
    batch_response_file = os.path.expanduser("~/prj/data/claims/GPT-Responses/batch")
    num_batches = 30
    batch_size = 1000
    batch_files = create_dataset(
        batch_input_file, num_batches=num_batches, batch_size=batch_size
    )
    # file_index = 4
    # change_model(f"{batch_input_file}_{file_index}.jsonl")
    # submit_batch_job_file(f"{batch_input_file}_{file_index}.jsonl")
    # create_final_file(batch_input_file, batch_response_file, num_batches)
