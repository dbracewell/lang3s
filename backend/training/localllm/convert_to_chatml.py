import json

from jsonlines import Reader, Writer, jsonlines


def convert(input_filename, output_filename):
    reader: Reader
    writer: Writer
    with jsonlines.open(output_filename, "w") as writer:
        with jsonlines.open(input_filename, "r") as reader:
            for example in reader:
                text = example["input"]
                claims = example["claims"]
                writer.write(
                    {
                        "messages": [
                            {"role": "user", "content": f"Extract claims from: {text}"},
                            {"role": "assistant", "content": json.dumps(claims)},
                        ]
                    }
                )


convert(
    "/Users/ik/prj/data/document_claim_extraction.jsonl",
    "/Users/ik/prj/data/document_claim_extraction_chatml.jsonl",
)
