import io
import logging
import time
from typing import Iterable, List, NamedTuple

import numpy as np
import requests

from lang3s import config
from lang3s.nlp.shared_types import Document
from lang3s.services.api.topics import TopicData

logger = logging.getLogger("TopicModelClient")


class Status(NamedTuple):
    status: str
    pending_tasks: int


TOPIC_MODEL_HOST = f"http://localhost:{config.FASTAPI_PORT}/topics"


class TopicModelClient:
    def partial_fit(self, docs: Iterable[Document]) -> Status:
        with requests.Session() as session:
            for i, doc in enumerate(docs):
                current_batch = [
                    s.embedding
                    for s in doc.text.sentences
                    if not s.is_stopword and s.embedding is not None
                ]

                if not current_batch:
                    continue

                embeddings = np.stack(current_batch)

                with io.BytesIO() as buf:
                    np.save(buf, embeddings)
                    buf.seek(0)

                    response = None
                    try:
                        response = session.post(
                            TOPIC_MODEL_HOST,
                            files={
                                "file": ("array.npy", buf, "application/octet-stream")
                            },
                            timeout=30,
                        )
                        response.raise_for_status()
                    except Exception as e:
                        logger.error(f"Failed to post doc {i}: {e}")
                        raise e
                    finally:
                        if response:
                            response.close()
                        buf.close()
                        del buf

                del embeddings
                del current_batch

            response = None
            try:
                response = session.get(f"{TOPIC_MODEL_HOST}/status")
                status_data = response.json()
            finally:
                response.close()

        return Status(**status_data)

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
