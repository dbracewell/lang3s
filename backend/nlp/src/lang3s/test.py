import base64
import os
import time
from pprint import pprint
from random import shuffle
from typing import Annotated, Literal

import torch
import transformers
from joblib import Parallel, delayed
from pydantic import BaseModel
from sqlalchemy import select
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

import lang3s.data.db.database as db
from lang3s.app import Application
from lang3s.cluster.online import DefaultOnlineClusterer
from lang3s.data.db.models import ClaimsTable
from lang3s.data.io.serialization import deserialize
from lang3s.llm import LLMClient, Message, tool
from lang3s.llm.local_llm import LocalLLM
from lang3s.llm.messages import Content
from lang3s.nlp.claim_extractor import (
    ClaimExtractor,
    DocumentClaimContext,
    DocumentClaimRequest,
    SentenceContext,
)
from lang3s.services.client.local_llm_client import LocalLLMClient
from lang3s.services.client.redis_client import CLAIM_EXTRACT_QUEUE_NAME, RedisClient
from lang3s.services.worker.annotation_worker import init_worker

llm = LocalLLMClient()


class ClaimClusterLabel(BaseModel):
    title: str
    coherence: int
    factuality: int


class Gender(BaseModel):
    sex: Literal["male", "female"]


class Joke(BaseModel):
    joke: str


@tool(name="weather_tool", description="A tool to get weather data from NLP API.")
def weather_tool(
    location: Annotated[str, "The location to get the weather data from."],
):
    return "46F"


class ClaimExample(BaseModel):
    claim: str
    confidence: float
    source: str | None = None


class DocumentClaims(BaseModel):
    claims: list[ClaimExample]


def encode_image(image_path):
    """Encodes a local image into a base64 string."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


class ObjectDescription(BaseModel):
    object: str
    parts: list[str]


class AttributeDescription(BaseModel):
    object: str
    attributes: list[str]


class RelationshipDescription(BaseModel):
    subject: str
    relationship: str
    object: str


class ImageDescription(BaseModel):
    objects: list[ObjectDescription]
    attributes: list[AttributeDescription]
    relationships: list[RelationshipDescription]


class Wrapped:
    """A callable object that pretends to do some work and records how many
    times it has been called."""

    def __init__(self):
        self.counter = 0
        print(f"[{os.getpid()}] Wrapped created")

    def __call__(self, *args, **kwargs):
        """Simulate a heavyweight operation and return (pid, call count)."""
        self.counter += 1  # <-- update the counter
        time.sleep(0.5)  # shorter sleep for demo
        return os.getpid(), self.counter


class Test(Application):
    def run(self):
        redis_client = RedisClient()
        for doc in deserialize("/Users/ik/prj/data/news.docs"):
            redis_client.enqueue(
                CLAIM_EXTRACT_QUEUE_NAME,
                DocumentClaimRequest(
                    documentId=doc.id, text=doc.text.text
                ).model_dump(),
            )

        return
        client = LLMClient("google/gemma-3-4b")
        base64_image = encode_image("/Users/ik/Downloads/Pictures/traffic.jpg")
        prompt = """
For the given image extract all objects (wholes and parts), attributes of those objects, and relationships between objects visible in the image.

Example Object:
Car : front wheel, back wheel, undercarriage, windshield, ...   

Example Attributes:
Car : silver, sedan, black and blue, ...

Example Relationships:
subject: person relationship: next to object: car  
subject: car relationship: in front of object: car
subject: trees relationship: surrounds object: highway   
        """
        r = client.sync_chat_completion_last_event(
            messages=[
                Message.user(
                    content=[
                        Content(type="text", text=prompt),
                        Content(
                            type="image_url",
                            image_url={"url": f"data:image/jpeg;base64,{base64_image}"},
                        ),
                    ]
                )
            ],
            response_model=ImageDescription,
        )
        print("# Objects")
        for o in r.parsed.objects:
            print(o)
        print("# Attributes")
        for o in r.parsed.attributes:
            print(o)
        print("# Relationships")
        for o in r.parsed.relationships:
            print(o)
        return
        # redis_client = RedisClient()
        # for doc in deserialize("/Users/ik/prj/data/news.docs"):
        #     redis_client.enqueue(
        #         CLAIM_EXTRACT_QUEUE_NAME,
        #         DocumentClaimContext(
        #             documentId=doc.id,
        #             sentences=[
        #                 SentenceContext(sentenceAid=s.id, text=s.text)
        #                 for s in doc.text.sentences
        #             ],
        #         ).model_dump(),
        #     )
        # return
        # client = LocalLLM()
        # for doc in deserialize("/Users/ik/prj/data/news.docs"):
        #     text = doc.text.text
        #     prompt = [Message.user(f"Extract claims from: {text}")]
        #     response = client.generate(
        #         messages=prompt,
        #         temperature=0,
        #         adapter_name="claim",
        #         response_model=DocumentClaims,
        #     )
        #     for claim in response.claims:
        #         print(claim)
        #     print()
        # return
        all_claims = []
        with db.get_session() as session:
            for claim in session.scalars(select(ClaimsTable)).all():
                all_claims.append(claim)
                session.expunge(claim)

        clusterer = DefaultOnlineClusterer[ClaimsTable](min_cluster_size=10)
        clusters = clusterer.fit(
            all_claims, [c.embedding.to_numpy() for c in all_claims]
        )
        for cluster in clusters:
            print(cluster.cluster_id, [c.content for c in cluster.items[0:2]])
            print()

        return
        client = LocalLLM()
        for label, claims in clusters.items():
            shuffle(claims)
            ex = "\n".join([c.content for c in claims[:25]])
            response = client.generate(
                messages=[
                    Message.user(
                        f"""Given the set of claims generate a title (simple noun phrase) that describes the claims, a coherence score from 1 to 4 on the quality of the cluster (1 being not coherent or describing many topics, 4 being coherent on a focused topic), and a factuality score that rates the overall set of claims on a scale of 1 to 4 (1 being the claims cannot be proven factual or nonfactual, 4 being the claims are obviously something that can be proven factual or not factual). 
                            Only give the title, coherence score, and factuality score do not give other information. 
                            Do not use 'The claims describe'.
                            Do not generate a list of concepts.
                            
                            Claims
                            {ex}
                        """
                    )
                ],
                response_model=ClaimClusterLabel,
                temperature=0.0,
                max_tokens=100,
            )
            print(response)

        # docs = []
        # for doc in deserialize("/Users/ik/prj/data/kant.docs"):
        #     docs.append(doc)
        #     if len(docs) > 100:
        #         break
        #
        # from joblib import Parallel, delayed
        #
        # with Parallel(
        #     n_jobs=5,
        # ) as parallel:
        #     tasks = [delayed(caller)(create_sentence_context(doc)) for doc in docs]
        #     results = parallel(tasks)
        #
        # for result in results:
        #     print(result)

        # rte = []
        # sentence_pairs = []
        # for i in range(len(claims)):
        #     for j in range(i + 1, min(len(claims), i + 4)):
        #         rte.append(
        #             [
        #                 {
        #                     "role": "system",
        #                     "content": "You are a rigid logic engine. You MUST output raw JSON. You MUST provide a step-by-step 'reasoning' string BEFORE providing the final 'result'.",
        #                 },
        #                 {
        #                     "role": "user",
        #                     "content": f"Do the following two sentences show ENTAILMENT, CONTRADICTION, or NEITHER?  {claims[i]} and {claims[j]}",
        #                 },
        #             ]
        #         )
        #         sentence_pairs.append((claims[i], claims[j]))
        #
        # results = locallm.generate(messages=rte, response_model=RTEResponse)
        # for ex, r in zip(sentence_pairs, results):
        #     print(r, ex)


def sam(image, label):
    pass


def gemma():
    client = LLMClient("google/gemma-3-4b")
    base64_image = encode_image("/Users/ik/Downloads/Pictures/traffic.jpg")
    prompt = """
    For the given image extract all objects (wholes and parts), attributes of those objects, and relationships between objects visible in the image.

    Example Object:
    Car : front wheel, back wheel, undercarriage, windshield, ...   

    Example Attributes:
    Car : silver, sedan, black and blue, ...

    Example Relationships:
    subject: person relationship: next to object: car  
    subject: car relationship: in front of object: car
    subject: trees relationship: surrounds object: highway   
            """
    r = client.sync_chat_completion_last_event(
        messages=[
            Message.user(
                content=[
                    Content(type="text", text=prompt),
                    Content(
                        type="image_url",
                        image_url={"url": f"data:image/jpeg;base64,{base64_image}"},
                    ),
                ]
            )
        ],
        response_model=ImageDescription,
    )

    print("# Objects")
    for o in r.parsed.objects:
        print(o)
    print("# Attributes")
    for o in r.parsed.attributes:
        print(o)
    print("# Relationships")
    for o in r.parsed.relationships:
        print(o)


if __name__ == "__main__":
    Test().run()
