import logging

import jsonlines
from lang3s_job_service import File

from lang3s.clients.topic_model_client import TopicModelClient
from lang3s.db import TextDatabase
from lang3s.pipeline import pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


if True:
    with jsonlines.open("news.jsonl", mode="r") as reader:
        files = (File.model_validate(doc) for doc in reader)
        docs = pipeline(
            files,
            write_to_db=True,
            tasks=set(),
        )
    exit()


text_db = TextDatabase()
client = TopicModelClient()
total_docs = text_db.doc_count
limit = 50
for i in range(0, total_docs, limit):
    client.partial_fit(text_db.get_documents(offset=i, limit=limit))
    break

client.finalize()
client.wait(timeout=10)

print(client.num_topics())
for topic in client.get_topics():
    print(topic.id, topic.name, topic.support)
