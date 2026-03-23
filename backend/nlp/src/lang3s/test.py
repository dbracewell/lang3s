from typing import Literal

from pydantic import BaseModel, Field

from lang3s.app import Application
from lang3s.data.io.serialization import deserialize
from lang3s.llm.local_llm import LocalLLM


class RTEResponse(BaseModel):
    reasoning: str = Field(description="Why did you choose this label?")
    result: Literal["ENTAILMENT", "CONTRADICTION", "NEITHER"]


class Test(Application):
    def run(self):
        locallm = LocalLLM()
        for doc in deserialize("/Users/ik/prj/data/kant.docs"):
            claims = locallm.extract_claims(doc)
            print(claims)
            rte = []
            sentence_pairs = []
            for i in range(len(claims)):
                for j in range(i + 1, min(len(claims), i + 4)):
                    rte.append(
                        [
                            {
                                "role": "system",
                                "content": "You are a rigid logic engine. You MUST output raw JSON. You MUST provide a step-by-step 'reasoning' string BEFORE providing the final 'result'.",
                            },
                            {
                                "role": "user",
                                "content": f"Do the following two sentences show ENTAILMENT, CONTRADICTION, or NEITHER?  {claims[i]} and {claims[j]}",
                            },
                        ]
                    )
                    sentence_pairs.append((claims[i], claims[j]))

            results = locallm.generate(messages=rte, response_model=RTEResponse)
            for ex, r in zip(sentence_pairs, results):
                print(r, ex)


if __name__ == "__main__":
    Test.from_cli().run()
