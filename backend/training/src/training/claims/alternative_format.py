import json
import os.path

from jsonlines import jsonlines

with jsonlines.open(
    os.path.expanduser("~/prj/data/claims/alternative_format.jsonl"), "w"
) as writer:
    with jsonlines.open(
        os.path.expanduser("~/prj/data/claims/gpt-5.4-combined-claims.jsonl")
    ) as reader:
        for doc in reader:
            prompt, response = doc["messages"]
            parsed_response = json.loads(response["content"])
            alt_response = []
            for claim in parsed_response:
                alt_response.append(
                    f"SUBJ: {claim['subject']} PRED: {claim['predicate']} OBJ: {claim['object']} STANCE: {claim['stance']} MOD: {claim['modality']} NEG: {claim['negation']} CERTAIN: {claim['certainty']} TIME: {claim.get('time', '-')} LOC: {claim['location']} SOURCE: {claim['source']} KW: {json.dumps(claim['keywords'])}"
                )
            writer.write(
                {
                    "messages": [
                        prompt,
                        {
                            "role": "assistant",
                            "content": "\n".join(alt_response),
                        },
                    ]
                }
            )
