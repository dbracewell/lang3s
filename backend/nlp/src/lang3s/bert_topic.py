import itertools
import logging
from typing import List

from datasets import load_dataset
from lang3s_job_service import File
from pydantic import BaseModel

from lang3s.clients.topic_model_client import TopicModelClient
from lang3s.db import TextDatabase
from lang3s.pipeline import pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

text_db = TextDatabase()

if False:
    dataset = load_dataset("SurAyush/News_Summary_Dataset")
    files = [
        File(
            content=data["article"],
        )
        for data in itertools.chain.from_iterable([dataset["train"]])
    ]
    docs = pipeline(files[:2000], write_to_db=True, tasks=set())


class AddRequest(BaseModel):
    embeddings: List[List[float]]


client = TopicModelClient()


for doc in text_db.get_documents(offset=501, limit=500):
    client.partial_fit(doc)
client.finalize()
client.wait(timeout=10)

print(client.num_topics())
for topic in client.get_topics():
    print(topic.id, topic.name, topic.support)
