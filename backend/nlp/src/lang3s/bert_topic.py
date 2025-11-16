import logging

import jsonlines

from lang3s.clients.topic_model_client import TopicModelClient
from lang3s.db import TextDatabase
from lang3s.pipeline import pipeline
from lang3s_job_service import File

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

if True:
    with jsonlines.open("/Users/ik/prj/Lang3s/news.jsonl", mode="r") as reader:
        files = (File.model_validate(doc) for doc in reader)
        docs = pipeline(
            list(files),
            write_to_db=True,
            # tasks=set()
        )
    exit()

exit()
text_db = TextDatabase()
client = TopicModelClient()
total_docs = text_db.doc_count
limit = 500
for i in range(0, total_docs, limit):
    client.partial_fit(text_db.get_documents(offset=i, limit=limit))
    break

client.finalize()
client.wait(timeout=10)

print(client.num_topics())
for topic in client.get_topics():
    print(topic.id, topic.name, topic.support)
