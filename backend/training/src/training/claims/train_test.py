import json
import os.path
from collections import defaultdict
from random import shuffle

from jsonlines import jsonlines


def to_text_annotation(claim):
    document = claim[0]["content"].replace("Extract claims from: ", "").strip()
    claims = json.loads(claim[1]["content"])
    output = f"#BEGIN DOCUMENT\n{document}\n"
    for claim in claims:
        claim_type = claim["claim_type"]
        if claim_type not in (
            "Fact",
            "Definition",
            "Value",
            "Policy",
            "Causation",
            "Comparison",
            "Contingency",
        ):
            claim_type = "Fact"
        line1 = f"#Annotation TYPE:{claim_type} MODALITY:{claim['modality']} CERTAINTY:{claim['certainty']} SUBJECT:{claim['subject']} PREDICATE:{claim['predicate']} OBJECT:{claim['object']}"
        line2 = f"TYPE:{claim_type}\nMODALITY:{claim['modality']}\nCERTAINTY:{claim['certainty']}\nSUBJECT:{claim['subject']}\nPREDICATE:{claim['predicate']}\nOBJECT:{claim['object']}"
        output += f"\n{line1}\n{line2}\n"
    return f"{output}\n#END DOCUMENT\n\n"


with jsonlines.open(
    os.path.expanduser("~/prj/data/claims/gpt-5.4-combined-claims.jsonl")
) as reader:
    all_claims = {}
    idx = 0
    for obj in reader:
        all_claims[idx] = obj
        idx += 1

type_stratification = defaultdict(set)
for idx, message in all_claims.items():
    claims = json.loads(message["messages"][1]["content"])
    for claim in claims:
        claim_type = claim["claim_type"]
        if claim_type not in (
            "Fact",
            "Definition",
            "Value",
            "Policy",
            "Causation",
            "Comparison",
            "Contingency",
        ):
            claim_type = "Fact"
            claim["claim_type"] = claim_type
        type_stratification[claim_type].add(idx)

for claim_type, idxs in type_stratification.items():
    print(claim_type, len(idxs))

print()
id_list = list(all_claims.keys())
shuffle(id_list)
test_strat = defaultdict(set)
with (
    jsonlines.open(
        os.path.expanduser("~/prj/data/claims/claims_test.jsonl"), "w"
    ) as writer,
    open(os.path.expanduser("~/prj/data/claims/claims_test.txt"), "w") as text_writer,
):
    for idx in id_list[:200]:
        claims = json.loads(all_claims[idx]["messages"][1]["content"])
        for claim in claims:
            claim_type = claim["claim_type"]
            if claim_type not in (
                "Fact",
                "Definition",
                "Value",
                "Policy",
                "Causation",
                "Comparison",
                "Contingency",
            ):
                claim_type = "Fact"
                claim["claim_type"] = claim_type
            test_strat[claim_type].add(idx)
        all_claims[idx]["messages"][1]["content"] = json.dumps(claims)
        writer.write(all_claims[idx])
        text_writer.write(to_text_annotation(all_claims[idx]["messages"]))

train_strat = defaultdict(set)
with jsonlines.open(
    os.path.expanduser("~/prj/data/claims/claims_train.jsonl"), "w"
) as writer:
    for idx in id_list[200:]:
        claims = json.loads(all_claims[idx]["messages"][1]["content"])
        for claim in claims:
            claim_type = claim["claim_type"]
            if claim_type not in (
                "Fact",
                "Definition",
                "Value",
                "Policy",
                "Causation",
                "Comparison",
                "Contingency",
            ):
                claim_type = "Fact"
                claim["claim_type"] = claim_type
            train_strat[claim_type].add(idx)
        all_claims[idx]["messages"][1]["content"] = json.dumps(claims)
        writer.write(all_claims[idx])

print("TEST")
for claim_type, idxs in test_strat.items():
    print(claim_type, len(idxs))

print("TRAIN")
for claim_type, idxs in train_strat.items():
    print(claim_type, len(idxs))
