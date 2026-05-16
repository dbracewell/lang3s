import os

from jsonlines import jsonlines
from lang3s.llm import LLMClient, Message
from pydantic import BaseModel


def create_prompt(claim_type: str, writing_style: str) -> str:
    return """
Generate 50 example sentences that contain a claim of {claim_type}.
The sentences should read/sound like it was written in/on {writing_style}.
For each sentence generate 2 non-claim examples discussing the same topic, concept, or entity.

Answer as follows:
{{
  "claims": [ str, str, ...]
  "non_claims": [ str, str, ...]"
}}
""".format(claim_type=claim_type, writing_style=writing_style).strip()


class Answer(BaseModel):
    claims: list[str]
    non_claims: list[str]


def main():
    client = LLMClient(model_name="gemma-4-26b-a4b-it")
    with jsonlines.open(
        os.path.expanduser(
            "~/prj/data/claims/claims_synthetic_classifier_dataset.jsonl"
        ),
        "w",
    ) as writer:
        for claim_type in [
            "fact",
            "definition",
            "value",
            "policy",
            "causation",
            "comparison",
            "contingency",
        ]:
            for writing_style in [
                "news",
                "twitter",
                "reddit",
                "facebook",
                "an email",
                "a scientific journal",
                "a blog",
            ]:
                for _ in range(5):
                    r = client.sync_chat_completion_last_event(
                        messages=[
                            Message.user(
                                create_prompt(
                                    claim_type,
                                    writing_style,
                                )
                            )
                        ],
                        temperature=1.0,
                        response_model=Answer,
                    )
                    if r.exception:
                        print(r.exception)
                    if r.parsed:
                        for claim in r.parsed.claims:
                            writer.write(
                                {
                                    "sentence": claim,
                                    "claim": True,
                                }
                            )
                        for claim in r.parsed.non_claims:
                            writer.write(
                                {
                                    "sentence": claim,
                                    "claim": False,
                                }
                            )


if __name__ == "__main__":
    main()
