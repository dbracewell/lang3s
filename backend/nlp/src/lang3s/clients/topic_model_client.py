import logging
import time
from typing import Iterable, List, NamedTuple

import requests

from lang3s.config import FASTAPI_PORT
from lang3s.services.topics import TopicData
from lang3s.shared_types import Document

logger = logging.getLogger("TopicModelClient")


class Status(NamedTuple):
    status: str
    pending_tasks: int


TOPIC_MODEL_HOST = f"http://localhost:{FASTAPI_PORT}/topics"


class TopicModelClient:
    def partial_fit(self, docs: Iterable[Document]) -> Status:
        for doc in docs:
            embeddings = [
                s.embedding.tolist()
                for s in doc.text.sentences
                if not s.is_stopword and s.embedding is not None
            ]
            response = requests.post(
                TOPIC_MODEL_HOST, json={"embeddings": embeddings}
            )
            response.raise_for_status()
        response = requests.get(f"{TOPIC_MODEL_HOST}/status")
        return Status(**response.json())

    def get_topics(self) -> List[TopicData]:
        response = requests.get(TOPIC_MODEL_HOST)
        response.raise_for_status()
        return [TopicData.model_validate(e) for e in response.json()]

    def get_topic(self, topic_id: str) -> TopicData:
        response = requests.get(f"{TOPIC_MODEL_HOST}/{topic_id}")
        response.raise_for_status()
        return TopicData.model_validate(response.json())

    def finalize(self) -> Status:
        response = requests.put(f"{TOPIC_MODEL_HOST}/finalize")
        response.raise_for_status()
        return Status(**response.json())

    def merge(self) -> Status:
        response = requests.put(f"{TOPIC_MODEL_HOST}/merge")
        response.raise_for_status()
        return Status(**response.json())

    def num_topics(self) -> int:
        response = requests.get(f"{TOPIC_MODEL_HOST}/count")
        response.raise_for_status()
        return response.json()

    def label(self) -> Status:
        response = requests.put(f"{TOPIC_MODEL_HOST}/label")
        response.raise_for_status()
        return Status(**response.json())

    def wait(self, timeout: int = 5):
        while True:
            response = requests.get(f"{TOPIC_MODEL_HOST}/status")
            pending = 0
            if response.ok:
                r = response.json()
                status = r["status"]
                pending = r["pending_tasks"]
                if status == "idle":
                    break
            logger.info(f"Waiting: Pending Tasks={pending}")
            time.sleep(timeout)
