import logging
import time
from typing import Iterable, List, NamedTuple

import requests

from lang3s.config import PYTHON_BACKEND
from lang3s.services.topics import TopicData
from lang3s.types import Document

logger = logging.getLogger("TopicModelClient")


class Status(NamedTuple):
    status: str
    pending_tasks: int


class TopicModelClient:
    def partial_fit(self, docs: Iterable[Document]) -> Status:
        for doc in docs:
            embeddings = [
                s.embedding.tolist()
                for s in doc.text.sentences
                if not s.is_stopword and s.embedding is not None
            ]
            response = requests.post(
                PYTHON_BACKEND + "/topics", json={"embeddings": embeddings}
            )
            response.raise_for_status()
        response = requests.get(PYTHON_BACKEND + "/topics/status")
        return Status(**response.json())

    def get_topics(self) -> List[TopicData]:
        response = requests.get(PYTHON_BACKEND + "/topics")
        response.raise_for_status()
        return [TopicData.model_validate(e) for e in response.json()]

    def get_topic(self, topic_id: str) -> TopicData:
        response = requests.get(PYTHON_BACKEND + f"/topics/{topic_id}")
        response.raise_for_status()
        return TopicData.model_validate(response.json())

    def finalize(self) -> Status:
        response = requests.put(PYTHON_BACKEND + "/topics/finalize")
        response.raise_for_status()
        return Status(**response.json())

    def merge(self) -> Status:
        response = requests.put(PYTHON_BACKEND + "/topics/merge")
        response.raise_for_status()
        return Status(**response.json())

    def num_topics(self) -> int:
        response = requests.get(PYTHON_BACKEND + "/topics/count")
        response.raise_for_status()
        return response.json()

    def label(self) -> Status:
        response = requests.put(PYTHON_BACKEND + "/topics/label")
        response.raise_for_status()
        return Status(**response.json())

    def wait(self, timeout: int = 5):
        while True:
            response = requests.get(PYTHON_BACKEND + "/topics/status")
            pending = 0
            if response.ok:
                r = response.json()
                status = r["status"]
                pending = r["pending_tasks"]
                if status == "idle":
                    break
            logger.info(f"Waiting: Pending Tasks={pending}")
            time.sleep(timeout)
