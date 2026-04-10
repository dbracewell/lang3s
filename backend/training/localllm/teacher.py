import json

from openai import OpenAI

client = OpenAI(api_key="YOUR_OPENAI_API_KEY")

# 1. THE TEACHER PROMPT
# This defines the "Gold Standard" behavior you want Qwen to inherit.
SYSTEM_PROMPT = """You are a master data annotator. 
Extract EXACTLY ONE claim and its SOURCE from the text.
RULES:
- CLAIM must be an assertive statement (e.g., use 'mirrors' or 'is comparable to' instead of 'compared to').
- Never use meta-verbs like 'said', 'claimed', or 'compared'.
- SOURCE must be the entity name, AUTHOR, or UNKNOWN.
- Max 15 words.
- Format: CLAIM: [Text] SOURCE: [Entity]"""


def create_batch_file(raw_data_list, output_file="batch_input.jsonl"):
    with open(output_file, "w") as f:
        for i, text in enumerate(raw_data_list):
            # We wrap the request in the format required by OpenAI's Batch API
            task = {
                "custom_id": f"task_{i}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": "gpt-4o-mini",  # Use gpt-4o-mini for 10x lower cost
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0.0,
                },
            }
            f.write(json.dumps(task) + "\n")
    print(f"Batch file created: {output_file}")


# 2. SUBMIT TO OPENAI
def submit_batch(file_path):
    batch_file = client.files.create(file=open(file_path, "rb"), purpose="batch")
    batch_job = client.batches.create(
        input_file_id=batch_file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
    )
    print(f"Batch Job Created! ID: {batch_job.id}")
    return batch_job.id


# Example usage with your raw text snippets
raw_texts = [
    "He detailed iconoclast violence and compared it to Islamic countries.",
    "The expansion of the economy led Lynn Franco to report higher confidence.",
    # ... add your thousands of rows here
]

# create_batch_file(raw_texts)
# submit_batch("batch_input.jsonl")
